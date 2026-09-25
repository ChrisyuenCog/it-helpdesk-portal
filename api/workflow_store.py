"""
IT Helpdesk Portal â€” Workflow Store (HD-015 / HD-016, storage graduated in HD-002/003/005/006)
=================================================================================================
Defines the data model for workflow definitions and instances, plus a
storage abstraction that the generic Durable Functions orchestrator reads
from. This is the concrete implementation of the "configuration, not code"
principle from the MVP Specification: the orchestrator (in function_app.py)
contains zero category-specific logic â€” every workflow type (Hardware,
Tender, Incident, and this TEST definition) is just a different row of
data read through this same interface.

Storage backend history:
- HD-015/HD-016 (original): InMemoryWorkflowStore only. Proven the
  orchestrator pattern end-to-end, but data did not survive a Function App
  restart â€” an accepted, explicit limitation at the time.
- HD-002/HD-003/HD-005/HD-006 (this revision): get_store() now checks for
  the AZURE_SQL_SERVER app setting. If present, it returns a durable
  SqlWorkflowStore (see sql_workflow_store.py) backed by Azure SQL. If
  absent, it falls back to InMemoryWorkflowStore unchanged â€” so this change
  is safe to deploy even before the Azure SQL Database is provisioned; the
  app setting is simply not set yet, and behaviour stays identical.
"""
from __future__ import annotations
import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class WorkflowDefinition:
    workflow_def_id: str
    states: List[str]
    transitions: List[Dict[str, str]]  # [{"from": "Start", "to": "Middle", "action": "advance"}, ...]
    terminal_states: List[str]

    def next_state(self, current_state: str, action: str) -> Optional[str]:
        """Returns the resulting state for a given (current_state, action) pair,
        or None if that transition is not defined. This is the ONLY place
        state-machine logic lives â€” the orchestrator never hardcodes states."""
        for t in self.transitions:
            if t["from"] == current_state and t["action"] == action:
                return t["to"]
        return None

    def is_terminal(self, state: str) -> bool:
        return state in self.terminal_states

    def initial_state(self) -> str:
        return self.states[0]


@dataclass
class WorkflowInstance:
    instance_id: str
    workflow_def_id: str
    current_state: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    def record_transition(self, from_state: str, to_state: str, action: str) -> None:
        self.history.append({
            "from": from_state,
            "to": to_state,
            "action": action,
            "at": datetime.datetime.utcnow().isoformat(),
        })
        self.current_state = to_state
        self.updated_at = datetime.datetime.utcnow().isoformat()


class WorkflowStoreError(Exception):
    pass


class WorkflowStore:
    """Abstract interface. SqlWorkflowStore (backed by Azure SQL, per
    HD-002/003/005/006) implements this exact same interface â€” the
    orchestrator and API endpoints depend only on this contract, never on
    a specific storage technology."""

    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        raise NotImplementedError

    def create_instance(self, workflow_def_id: str) -> WorkflowInstance:
        raise NotImplementedError

    def get_instance(self, instance_id: str) -> WorkflowInstance:
        raise NotImplementedError

    def save_instance(self, instance: WorkflowInstance) -> None:
        raise NotImplementedError


class InMemoryWorkflowStore(WorkflowStore):
    """Original HD-015/HD-016 implementation. Data does not persist across
    Function App restarts. Retained as the safe fallback when Azure SQL is
    not yet configured (AZURE_SQL_SERVER app setting absent) â€” see get_store()
    below."""

    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._seed_test_definition()

    def _seed_test_definition(self) -> None:
        """HD-016: seed a single TEST workflow_definition with 3 trivial
        states (Start -> Middle -> End), matching the schema.sql seed exactly
        so behaviour is identical whether backed by memory or SQL."""
        self._definitions["TEST"] = WorkflowDefinition(
            workflow_def_id="TEST",
            states=["Start", "Middle", "End"],
            transitions=[
                {"from": "Start", "to": "Middle", "action": "advance"},
                {"from": "Middle", "to": "End", "action": "advance"},
            ],
            terminal_states=["End"],
        )

    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        if workflow_def_id not in self._definitions:
            raise WorkflowStoreError(f"Unknown workflow_def_id: {workflow_def_id}")
        return self._definitions[workflow_def_id]

    def create_instance(self, workflow_def_id: str) -> WorkflowInstance:
        definition = self.get_definition(workflow_def_id)  # raises if invalid â€” satisfies HD-017's 400 requirement upstream
        instance = WorkflowInstance(
            instance_id=str(uuid.uuid4()),
            workflow_def_id=workflow_def_id,
            current_state=definition.initial_state(),
        )
        self._instances[instance.instance_id] = instance
        return instance

    def get_instance(self, instance_id: str) -> WorkflowInstance:
        if instance_id not in self._instances:
            raise WorkflowStoreError(f"Unknown instance_id: {instance_id}")
        return self._instances[instance_id]

    def save_instance(self, instance: WorkflowInstance) -> None:
        self._instances[instance.instance_id] = instance


# Module-level singleton. NOTE: for InMemoryWorkflowStore, this is not
# reliable across concurrent Flex Consumption worker instances â€” this is why
# HD-002/003/005/006 exist. Once AZURE_SQL_SERVER is set, get_store() returns
# a SqlWorkflowStore instead, and this limitation no longer applies.
_store_instance: Optional[WorkflowStore] = None


def get_store() -> WorkflowStore:
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_workflow_store import SqlWorkflowStore
            _store_instance = SqlWorkflowStore()
            logging.info("get_store: using SqlWorkflowStore (AZURE_SQL_SERVER is set)")
            return _store_instance
        except Exception:
            # Fail safe, not silent: log loudly, then fall back to in-memory
            # rather than crashing the whole Function App if SQL is
            # misconfigured. This mirrors ai_summarizer.py's own graceful
            # degradation pattern elsewhere in this codebase.
            logging.exception(
                "get_store: AZURE_SQL_SERVER is set but SqlWorkflowStore failed to "
                "initialise. Falling back to InMemoryWorkflowStore. This means "
                "workflow data will NOT persist across restarts until the "
                "underlying SQL issue is fixed."
            )

    _store_instance = InMemoryWorkflowStore()
    return _store_instance