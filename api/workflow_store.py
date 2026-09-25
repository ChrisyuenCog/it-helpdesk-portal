"""
IT Helpdesk Portal â€” Workflow Store (HD-015 / HD-016)
=======================================================
Defines the data model for workflow definitions and instances, plus a
storage abstraction that the generic Durable Functions orchestrator reads
from. This is the concrete implementation of the "configuration, not code"
principle from the MVP Specification: the orchestrator (in function_app.py)
contains zero category-specific logic â€” every workflow type (Hardware,
Tender, Incident, and this TEST definition) is just a different row of
data read through this same interface.

IMPORTANT â€” scope note for this ticket (HD-015/HD-016):
The MVP Specification's target data layer is Azure SQL (Section 7 of the
MVP spec: ci_base, workflow_definition, workflow_instance, etc.), but those
tables are provisioned under separate backlog items (HD-002 through
HD-008) which have not been built yet in this deployment. Rather than
block the orchestrator pattern on that infrastructure work, this ticket
proves the pattern against a WorkflowStore *interface*, with an in-memory
implementation for now. Swapping in a SqlWorkflowStore later (once HD-002
â€“HD-008 land) requires no change to the orchestrator itself â€” only a
different class satisfying the same interface. This mirrors the same
"reuse, don't duplicate" principle already applied to the CMDB design.
"""
from __future__ import annotations
import uuid
import datetime
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
    """Abstract interface. A future SqlWorkflowStore (backed by Azure SQL,
    per HD-002â€“HD-008) implements this exact same interface â€” the
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
    """Temporary implementation for HD-015/HD-016 only. Data does not
    persist across Function App restarts â€” this is expected and acceptable
    for this ticket's acceptance criteria, which only requires proving the
    orchestrator pattern end-to-end, not durable cross-restart storage.
    Durability across restarts arrives with the Azure SQL-backed store in
    a later ticket."""

    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._seed_test_definition()

    def _seed_test_definition(self) -> None:
        """HD-016: seed a single TEST workflow_definition with 3 trivial
        states (Start -> Middle -> End), matching this ticket's acceptance
        criteria exactly."""
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


# Module-level singleton for MVP simplicity. NOTE: since Flex Consumption
# can spin up multiple worker instances, this in-memory store is NOT
# reliable across concurrent requests in production â€” this is a known,
# accepted limitation of this ticket's scope (see class docstring above)
# and is exactly why HD-002â€“HD-008 (Azure SQL CMDB) must land before any
# real workflow type (Hardware, Tender, Incident) is built on top of this
# orchestrator skeleton.
_store_instance: Optional[WorkflowStore] = None


def get_store() -> WorkflowStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = InMemoryWorkflowStore()
    return _store_instance