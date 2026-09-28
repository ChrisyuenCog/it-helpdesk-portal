"""
IT Helpdesk Portal — SQL-backed Workflow Store
=================================================
HD-002/003/005/006: durable Azure SQL-backed implementation of the
WorkflowStore interface. Drop-in replacement for InMemoryWorkflowStore —
the orchestrator and API endpoints never depend on a specific storage
technology.
HD-018: adds append_approval_entry() / get_approval_chain(), backed by
the new dbo.approval_chain table (see sql/schema_update_hd018.sql).
_compute_terminal_states() has moved to workflow_store.py (as
compute_terminal_states, now shared with InMemoryWorkflowStore's seeding) —
imported from there rather than redefined here, so the two backends can
never compute terminal states differently for the same definition.
HD-007 (this revision): adds create_sla_clock() / get_sla_clock(), backed
by the new dbo.sla_clock table (see sql/schema_update_hd007.sql). Mirrors
the approval_chain addition's shape exactly: a pure row_to_sla_clock()
helper (offline-testable, no DB needed) plus a thin connection-handling
method on the class. breachedFlag is intentionally NOT read as a stored
value from the row — SlaClock.breached_flag (in workflow_store.py) computes
it live from targetResolutionAt every time it's accessed, so a test can
insert a row with a past target and immediately observe breached=True
without needing a timer job to run in between. The stored breachedFlag
column still exists on the table for future indexing/filtering use, but
is not the source of truth read by this store.
Authentication: Managed Identity is the PRIMARY path. A Key Vault-backed SQL
authentication connection string is the FALLBACK path — see the "Known risk"
section of the original runbook regarding ODBC Driver 18 availability on
Flex Consumption.
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
    ApprovalChainEntry,
    SlaClock,
    compute_terminal_states,
)

SQL_COPT_SS_ACCESS_TOKEN = 1256  # pyodbc connection attribute for AAD access tokens

# ---------------------------------------------------------------------------
# Pure logic — no DB connection required. Tested offline in
# test_sql_workflow_store.py without needing pyodbc, azure-identity, or a
# live database.
# ---------------------------------------------------------------------------

def row_to_definition(row: tuple) -> WorkflowDefinition:
    """row: (workflowDefId, states_json, transitions_json, approvalRules_json, slaTargets_json)"""
    workflow_def_id, states_json, transitions_json, _approval_json, _sla_json = row
    states = json.loads(states_json)
    transitions = json.loads(transitions_json)
    terminal_states = compute_terminal_states(states, transitions)
    return WorkflowDefinition(
        workflow_def_id=workflow_def_id,
        states=states,
        transitions=transitions,
        terminal_states=terminal_states,
    )


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


def row_to_approval_entry(row: tuple) -> ApprovalChainEntry:
    """row: (instanceId, stepOrder, approverUpn, status, actionedAt)"""
    instance_id, step_order, approver_upn, status, actioned_at = row
    return ApprovalChainEntry(
        instance_id=str(instance_id),
        step_order=int(step_order),
        approver_upn=approver_upn,
        status=status,
        actioned_at=str(actioned_at),
    )


def row_to_sla_clock(row: tuple) -> SlaClock:
    """row: (instanceId, targetResponseAt, targetResolutionAt)
    Deliberately does not read/return a stored breachedFlag column — see
    module docstring. SlaClock.breached_flag computes it live instead."""
    instance_id, target_response_at, target_resolution_at = row
    return SlaClock(
        instance_id=str(instance_id),
        target_response_at=str(target_response_at) if target_response_at else None,
        target_resolution_at=str(target_resolution_at) if target_resolution_at else None,
    )


def build_insert_instance_params(workflow_def_id: str, initial_state: str) -> tuple:
    return (workflow_def_id, initial_state)


def build_update_instance_params(instance: WorkflowInstance) -> tuple:
    history_json = json.dumps(instance.history)
    return (instance.current_state, history_json, instance.instance_id)


def build_insert_approval_params(instance_id: str, step_order: int, approver_upn: Optional[str], status: str) -> tuple:
    """Isolated so the exact parameter tuple sent to SQL can be asserted in
    an offline test without a connection."""
    return (instance_id, step_order, approver_upn, status)


def build_insert_sla_params(
    instance_id: str, target_response_at: Optional[str], target_resolution_at: Optional[str]
) -> tuple:
    """Isolated so the exact parameter tuple sent to SQL can be asserted in
    an offline test without a connection, matching build_insert_approval_params's
    precedent."""
    return (instance_id, target_response_at, target_resolution_at)


# ---------------------------------------------------------------------------
# Connection handling — requires pyodbc + a reachable Azure SQL Database.
# ---------------------------------------------------------------------------

def _get_access_token_struct() -> bytes:
    from azure.identity import DefaultAzureCredential
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _build_connection():
    import pyodbc
    server = os.environ["AZURE_SQL_SERVER"]
    database = os.environ["AZURE_SQL_DATABASE"]
    use_managed_identity = os.environ.get("AZURE_SQL_USE_MANAGED_IDENTITY", "true").lower() == "true"
    driver = "{ODBC Driver 18 for SQL Server}"
    base_conn_str = (
        f"Driver={driver};Server=tcp:{server},1433;Database={database};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    if use_managed_identity:
        token_struct = _get_access_token_struct()
        return pyodbc.connect(base_conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
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
    by the tables created in sql/schema.sql plus sql/schema_update_hd018.sql
    and sql/schema_update_hd007.sql."""

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
        definition = self.get_definition(workflow_def_id)
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

    def append_approval_entry(
        self, instance_id: str, approver_upn: Optional[str], status: str
    ) -> ApprovalChainEntry:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ISNULL(MAX(stepOrder), 0) + 1 FROM dbo.approval_chain WHERE instanceId = ?",
                instance_id,
            )
            next_step_order = cursor.fetchone()[0]
            params = build_insert_approval_params(instance_id, next_step_order, approver_upn, status)
            cursor.execute(
                "INSERT INTO dbo.approval_chain (instanceId, stepOrder, approverUpn, status) "
                "OUTPUT INSERTED.instanceId, INSERTED.stepOrder, INSERTED.approverUpn, "
                "INSERTED.status, INSERTED.actionedAt "
                "VALUES (?, ?, ?, ?)",
                *params,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_approval_entry(tuple(row))
        finally:
            conn.close()

    def get_approval_chain(self, instance_id: str) -> List[ApprovalChainEntry]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT instanceId, stepOrder, approverUpn, status, actionedAt "
                "FROM dbo.approval_chain WHERE instanceId = ? ORDER BY stepOrder",
                instance_id,
            )
            rows = cursor.fetchall()
            return [row_to_approval_entry(tuple(r)) for r in rows]
        finally:
            conn.close()

    # -----------------------------------------------------------------
    # HD-007 — sla_clock (new in this revision)
    # -----------------------------------------------------------------

    def create_sla_clock(
        self, instance_id: str, target_response_at: Optional[str], target_resolution_at: Optional[str]
    ) -> SlaClock:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_insert_sla_params(instance_id, target_response_at, target_resolution_at)
            cursor.execute(
                "INSERT INTO dbo.sla_clock (instanceId, targetResponseAt, targetResolutionAt) "
                "OUTPUT INSERTED.instanceId, INSERTED.targetResponseAt, INSERTED.targetResolutionAt "
                "VALUES (?, ?, ?)",
                *params,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_sla_clock(tuple(row))
        finally:
            conn.close()

    def get_sla_clock(self, instance_id: str) -> Optional[SlaClock]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT instanceId, targetResponseAt, targetResolutionAt "
                "FROM dbo.sla_clock WHERE instanceId = ?",
                instance_id,
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return row_to_sla_clock(tuple(row))
        finally:
            conn.close()
