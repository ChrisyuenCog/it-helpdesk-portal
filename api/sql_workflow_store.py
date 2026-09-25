"""
IT Helpdesk Portal â€” SQL-backed Workflow Store (HD-002, HD-003, HD-005, HD-006)
=================================================================================
A durable, Azure SQL-backed implementation of the same WorkflowStore interface
already defined in workflow_store.py. This is a drop-in replacement for
InMemoryWorkflowStore â€” the orchestrator and activity functions in
function_app.py do not change at all when this is wired in, because they only
ever depend on the WorkflowStore interface, never on a specific storage
technology.

Authentication: Managed Identity is the PRIMARY path (no stored credentials,
consistent with every other CLG project this session). A Key Vault-backed SQL
authentication connection string is the FALLBACK path, used only if
AZURE_SQL_USE_MANAGED_IDENTITY is explicitly set to "false" â€” included because
pyodbc's Managed Identity token flow requires "ODBC Driver 18 for SQL Server"
to be present in the Function App's runtime, which cannot be confirmed until
the Function App itself is provisioned and deployed (see runbook.md, Section
"Known risk"). If the Managed Identity path fails at deploy time for that
reason, flipping one app setting switches to the fallback path with no code
change required.
"""
from __future__ import annotations
import os
import json
import struct
import logging
from typing import Optional, List, Dict, Any

from workflow_store import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStore,
    WorkflowStoreError,
)

SQL_COPT_SS_ACCESS_TOKEN = 1256  # pyodbc connection attribute for AAD access tokens


# ---------------------------------------------------------------------------
# Pure logic â€” no DB connection required. Tested offline in
# test_sql_workflow_store.py without needing pyodbc, azure-identity, or a
# live database.
# ---------------------------------------------------------------------------
def row_to_definition(row: tuple) -> WorkflowDefinition:
    """row: (workflowDefId, states_json, transitions_json, approvalRules_json, slaTargets_json)"""
    workflow_def_id, states_json, transitions_json, _approval_json, _sla_json = row
    states = json.loads(states_json)
    transitions = json.loads(transitions_json)
    terminal_states = _compute_terminal_states(states, transitions)
    return WorkflowDefinition(
        workflow_def_id=workflow_def_id,
        states=states,
        transitions=transitions,
        terminal_states=terminal_states,
    )


def _compute_terminal_states(states: List[str], transitions: List[Dict[str, str]]) -> List[str]:
    """A state is terminal if no transition has it as a 'from'. Computed rather
    than stored, so the schema doesn't need a separate terminal_states column
    that could drift out of sync with the transitions list."""
    states_with_outgoing = {t["from"] for t in transitions}
    return [s for s in states if s not in states_with_outgoing]


def row_to_instance(row: tuple) -> WorkflowInstance:
    """row: (instanceId, workflowDefId, currentState, historyJson, createdAt, updatedAt)"""
    instance_id, workflow_def_id, current_state, history_json, created_at, updated_at = row
    history = json.loads(history_json) if history_json else []
    instance = WorkflowInstance(
        instance_id=str(instance_id),
        workflow_def_id=workflow_def_id,
        current_state=current_state,
    )
    instance.history = history
    instance.created_at = str(created_at)
    instance.updated_at = str(updated_at)
    return instance


def build_insert_instance_params(workflow_def_id: str, initial_state: str) -> tuple:
    """Returns the parameter tuple for the INSERT statement, isolated so the
    exact values sent to SQL can be asserted in a test without a connection."""
    return (workflow_def_id, initial_state)


def build_update_instance_params(instance: WorkflowInstance) -> tuple:
    history_json = json.dumps(instance.history)
    return (instance.current_state, history_json, instance.instance_id)


# ---------------------------------------------------------------------------
# Connection handling â€” requires pyodbc + a reachable Azure SQL Database.
# Not exercised by offline tests; validated manually per runbook.md Section 5.
# ---------------------------------------------------------------------------
def _get_access_token_struct() -> bytes:
    """Acquires an Azure AD access token for the Function App's Managed
    Identity, scoped to Azure SQL, and packs it into the byte structure
    pyodbc's SQL_COPT_SS_ACCESS_TOKEN attribute expects."""
    from azure.identity import DefaultAzureCredential  # imported here so this
    # module can still be imported (and offline-tested) on a machine without
    # azure-identity installed â€” only this function needs it at call time.

    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _build_connection():
    import pyodbc  # deferred import, same reasoning as above

    server = os.environ["AZURE_SQL_SERVER"]        # e.g. sql-it-helpdesk-cmdb-srv.database.windows.net
    database = os.environ["AZURE_SQL_DATABASE"]     # e.g. it-helpdesk-cmdb
    use_managed_identity = os.environ.get("AZURE_SQL_USE_MANAGED_IDENTITY", "true").lower() == "true"

    driver = "{ODBC Driver 18 for SQL Server}"
    base_conn_str = (
        f"Driver={driver};Server=tcp:{server},1433;Database={database};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )

    if use_managed_identity:
        token_struct = _get_access_token_struct()
        return pyodbc.connect(base_conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

    # Fallback path: SQL authentication via a connection string stored in Key
    # Vault. Only used if AZURE_SQL_USE_MANAGED_IDENTITY=false.
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    vault_url = os.environ["HELPDESK_KEYVAULT_URL"]
    secret_name = os.environ.get("SQL_CONNECTION_STRING_SECRET_NAME", "SqlConnectionString")
    kv_credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=kv_credential)
    full_conn_str = client.get_secret(secret_name).value
    return pyodbc.connect(full_conn_str)


class SqlWorkflowStore(WorkflowStore):
    """Durable replacement for InMemoryWorkflowStore. Same interface, backed
    by the three tables created in sql/schema.sql."""

    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT workflowDefId, states, transitions, approvalRules, slaTargets "
                "FROM dbo.workflow_definition WHERE workflowDefId = ?",
                workflow_def_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise WorkflowStoreError(f"Unknown workflow_def_id: {workflow_def_id}")
            return row_to_definition(tuple(row))
        finally:
            conn.close()

    def create_instance(self, workflow_def_id: str) -> WorkflowInstance:
        definition = self.get_definition(workflow_def_id)  # raises if invalid, same as InMemory
        initial_state = definition.initial_state()
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.workflow_instance (workflowDefId, currentState, historyJson) "
                "OUTPUT INSERTED.instanceId, INSERTED.workflowDefId, INSERTED.currentState, "
                "INSERTED.historyJson, INSERTED.createdAt, INSERTED.updatedAt "
                "VALUES (?, ?, ?)",
                workflow_def_id, initial_state, json.dumps([]),
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_instance(tuple(row))
        finally:
            conn.close()

    def get_instance(self, instance_id: str) -> WorkflowInstance:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT instanceId, workflowDefId, currentState, historyJson, createdAt, updatedAt "
                "FROM dbo.workflow_instance WHERE instanceId = ?",
                instance_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise WorkflowStoreError(f"Unknown instance_id: {instance_id}")
            return row_to_instance(tuple(row))
        finally:
            conn.close()

    def save_instance(self, instance: WorkflowInstance) -> None:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_update_instance_params(instance)
            cursor.execute(
                "UPDATE dbo.workflow_instance SET currentState = ?, historyJson = ?, "
                "updatedAt = SYSUTCDATETIME() WHERE instanceId = ?",
                *params,
            )
            conn.commit()
        finally:
            conn.close()