"""
IT Helpdesk Portal — SQL-backed Workflow Store
=================================================
HD-002/003/005/006: durable Azure SQL-backed implementation of the
WorkflowStore interface.
HD-018: approval_chain support.
HD-007: sla_clock support.
HD-028/029 (this revision):
  - create_instance() now accepts and persists requester_upn (new
    requesterUpn column — see sql/schema_update_hd028.sql. Nullable, so
    existing rows created before this migration are unaffected and simply
    read back as requester_upn=None).
  - row_to_instance() updated for the new column (7th field).
  - get_instances_by_requester() — a direct, indexed-friendly WHERE clause.
  - get_instances_pending_role() — deliberately implemented as "fetch all
    non-terminal-looking instances joined with their definitions, then
    filter in Python using WorkflowDefinition.roles_pending_from()" rather
    than attempting to express "does this instance's current JSON
    transitions array contain an outgoing edge with this requiredRole"
    as a single SQL predicate. At MVP data volumes (a handful of workflow
    definitions, low hundreds of concurrent instances) this is simpler,
    more maintainable, and exactly as correct as a more complex SQL-side
    JSON query would be — the actual filtering LOGIC still lives in
    exactly one place (WorkflowDefinition.roles_pending_from in
    workflow_store.py), never duplicated in a SQL WHERE clause that could
    silently drift out of sync with the Python-side definition of
    'pending'. Revisit only if/when instance volume genuinely makes a
    full-table scan a real cost.
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
    """row: (instanceId, workflowDefId, currentState, historyJson, createdAt, updatedAt, requesterUpn)
    HD-028: requesterUpn is the 7th column, appended rather than inserted
    in the middle, so any caller still unpacking the pre-HD-028 6-tuple
    shape elsewhere would fail loudly (IndexError/unpack mismatch) rather
    than silently reading the wrong field — deliberately not a silent
    schema-compatible change."""
    instance_id, workflow_def_id, current_state, history_json, created_at, updated_at, requester_upn = row
    history = json.loads(history_json) if history_json else []
    instance = WorkflowInstance(
        instance_id=str(instance_id),
        workflow_def_id=workflow_def_id,
        current_state=current_state,
        requester_upn=requester_upn,
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
    """row: (instanceId, targetResponseAt, targetResolutionAt)"""
    instance_id, target_response_at, target_resolution_at = row
    return SlaClock(
        instance_id=str(instance_id),
        target_response_at=str(target_response_at) if target_response_at else None,
        target_resolution_at=str(target_resolution_at) if target_resolution_at else None,
    )


def build_insert_instance_params(workflow_def_id: str, initial_state: str, requester_upn: Optional[str]) -> tuple:
    """HD-028: now includes requester_upn as the third insert parameter."""
    return (workflow_def_id, initial_state, requester_upn)


def build_update_instance_params(instance: WorkflowInstance) -> tuple:
    history_json = json.dumps(instance.history)
    return (instance.current_state, history_json, instance.instance_id)


def build_insert_approval_params(instance_id: str, step_order: int, approver_upn: Optional[str], status: str) -> tuple:
    return (instance_id, step_order, approver_upn, status)


def build_insert_sla_params(
    instance_id: str, target_response_at: Optional[str], target_resolution_at: Optional[str]
) -> tuple:
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
    by dbo.workflow_definition, dbo.workflow_instance, dbo.approval_chain,
    dbo.sla_clock (see sql/schema*.sql files)."""

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

    def create_instance(self, workflow_def_id: str, requester_upn: Optional[str] = None) -> WorkflowInstance:
        definition = self.get_definition(workflow_def_id)
        initial_state = definition.initial_state()
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_insert_instance_params(workflow_def_id, initial_state, requester_upn)
            cursor.execute(
                "INSERT INTO dbo.workflow_instance (workflowDefId, currentState, historyJson, requesterUpn) "
                "OUTPUT INSERTED.instanceId, INSERTED.workflowDefId, INSERTED.currentState, "
                "INSERTED.historyJson, INSERTED.createdAt, INSERTED.updatedAt, INSERTED.requesterUpn "
                "VALUES (?, ?, ?, ?)",
                params[0], params[1], json.dumps([]), params[2],
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
                "SELECT instanceId, workflowDefId, currentState, historyJson, createdAt, updatedAt, requesterUpn "
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

    # -----------------------------------------------------------------
    # HD-028/029 — myRequests / myApprovals (new in this revision)
    # -----------------------------------------------------------------

    def get_instances_by_requester(self, requester_upn: str) -> List[WorkflowInstance]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT instanceId, workflowDefId, currentState, historyJson, createdAt, updatedAt, requesterUpn "
                "FROM dbo.workflow_instance WHERE requesterUpn = ? ORDER BY createdAt DESC",
                requester_upn,
            )
            rows = cursor.fetchall()
            return [row_to_instance(tuple(r)) for r in rows]
        finally:
            conn.close()

    def get_instances_pending_role(self, role: str) -> List[WorkflowInstance]:
        """See module docstring for why this fetches broadly and filters
        in Python rather than expressing the filter as SQL-side JSON
        logic."""
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT wi.instanceId, wi.workflowDefId, wi.currentState, wi.historyJson, "
                "wi.createdAt, wi.updatedAt, wi.requesterUpn, "
                "wd.states, wd.transitions, wd.approvalRules, wd.slaTargets "
                "FROM dbo.workflow_instance wi "
                "JOIN dbo.workflow_definition wd ON wd.workflowDefId = wi.workflowDefId "
                "ORDER BY wi.createdAt DESC",
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        definition_cache: Dict[str, WorkflowDefinition] = {}
        matches: List[WorkflowInstance] = []
        for row in rows:
            row = tuple(row)
            instance_row, definition_row = row[:7], row[7:]
            workflow_def_id = instance_row[1]
            if workflow_def_id not in definition_cache:
                definition_cache[workflow_def_id] = row_to_definition(
                    (workflow_def_id,) + tuple(definition_row)
                )
            definition = definition_cache[workflow_def_id]
            instance = row_to_instance(instance_row)
            if definition.is_terminal(instance.current_state):
                continue
            if role in definition.roles_pending_from(instance.current_state):
                matches.append(instance)
        return matches
