"""
IT Helpdesk Portal — Workflow Store
=====================================
HD-015/016: generic state machine + TEST definition.
HD-002/003/005/006: durable Azure SQL-backed storage, with safe in-memory fallback.
HD-018:
  - WorkflowDefinition.get_transition() — full transition lookup (including
    an optional 'requiredRole'), so role-gated actions can be checked
    against a definition without changing the existing next_state()
    contract used by the auto-advance orchestrator loop.
  - _compute_terminal_states() moved here from sql_workflow_store.py so
    BOTH the in-memory seed and the SQL row-parser compute terminal states
    the exact same way.
  - ApprovalChainEntry + WorkflowStore.append_approval_entry() /
    get_approval_chain() — HD-008's approval_chain table.
  - InMemoryWorkflowStore now also seeds TEST_APPROVAL alongside TEST.
HD-007: SlaClock dataclass + compute_sla_breached() (pure, offline-testable)
  + WorkflowStore.create_sla_clock() / get_sla_clock().
HD-028/029 (this revision):
  - WorkflowInstance gains requester_upn (Optional[str], defaults to None
    so every existing caller of create_instance()/WorkflowInstance(...)
    keeps working unchanged — this is an additive, backward-compatible
    field, not a breaking signature change).
  - WorkflowDefinition.roles_pending_from(state) — a small, pure helper:
    returns the sorted set of distinct 'requiredRole' values found on any
    transition whose 'from' is the given state. Used by
    get_instances_pending_role() below to answer "which instances are
    currently sitting in a state where THIS role could act on them?"
    without needing a separately-maintained 'pending approval' table.
    Design note (please read before assuming this should instead read
    approval_chain rows with status='Pending'): the MVP Build Backlog's
    literal wording for HD-029 ("...instances where an approval_chain row
    references them with status Pending") describes ServiceNow-style
    ticket ASSIGNMENT, which this MVP does not implement — approval_chain
    rows here are only ever written AFTER a decision is actioned (see
    workflow_action_api.py's determine_approval_status(), which maps
    action -> 'Approved'/'Rejected', never 'Pending'). Introducing
    'Pending' rows would require deciding who to name-assign a Pending row
    to at instance-creation time, which this MVP's role-based (not
    named-individual) approval model does not support. This revision
    therefore implements "awaiting my decision" as a DERIVED query — is
    this instance non-terminal, and does its current_state have an
    outgoing transition requiring my role — which is behaviourally
    equivalent (a manager sees exactly the instances they could act on
    right now) without requiring a schema change to add named assignment.
  - WorkflowStore.get_instances_by_requester() / get_instances_pending_role()
    — same "abstract interface + InMemoryWorkflowStore implementation"
    pattern already established for approval_chain/sla_clock.
"""
from __future__ import annotations
import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set


def compute_terminal_states(states: List[str], transitions: List[Dict[str, str]]) -> List[str]:
    """A state is terminal if no transition has it as a 'from'. Shared by
    both InMemoryWorkflowStore's seeding and SqlWorkflowStore's row parsing
    (see sql_workflow_store.py), so the two backends can never disagree on
    which states are terminal for the same definition."""
    states_with_outgoing = {t["from"] for t in transitions}
    return [s for s in states if s not in states_with_outgoing]


@dataclass
class WorkflowDefinition:
    workflow_def_id: str
    states: List[str]
    transitions: List[Dict[str, str]]  # each: {"from", "to", "action", "requiredRole"?}
    terminal_states: List[str]

    def get_transition(self, current_state: str, action: str) -> Optional[Dict[str, str]]:
        """Returns the FULL transition dict (including 'requiredRole' if
        present) for a given (current_state, action) pair, or None if
        undefined. This is the only place transition lookup logic lives —
        both next_state() and HD-018's role-checking logic go through this
        single method, so there is exactly one source of truth for 'what
        happens on this action from this state'."""
        for t in self.transitions:
            if t["from"] == current_state and t["action"] == action:
                return t
        return None

    def next_state(self, current_state: str, action: str) -> Optional[str]:
        """Unchanged contract from HD-015: returns just the resulting
        state, or None."""
        transition = self.get_transition(current_state, action)
        return transition["to"] if transition else None

    def is_terminal(self, state: str) -> bool:
        return state in self.terminal_states

    def initial_state(self) -> str:
        return self.states[0]

    def roles_pending_from(self, current_state: str) -> List[str]:
        """HD-029: returns the sorted, deduplicated list of 'requiredRole'
        values on any transition whose 'from' equals current_state.
        Transitions with no requiredRole (role-free, e.g. TEST's 'advance'
        transitions, or HARDWARE_REQUEST's 'submit') never contribute a
        role here — a role-free next step is not something any specific
        role is 'awaiting', it just auto-advances. Returns an empty list
        for a terminal state or a state with no role-gated outgoing
        transitions, e.g. a state where you'd expect nobody's myApprovals
        list to include this instance."""
        roles: Set[str] = set()
        for t in self.transitions:
            if t["from"] == current_state and t.get("requiredRole"):
                roles.add(t["requiredRole"])
        return sorted(roles)


@dataclass
class WorkflowInstance:
    instance_id: str
    workflow_def_id: str
    current_state: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    requester_upn: Optional[str] = None  # HD-028: who started this instance, for myRequests

    def record_transition(self, from_state: str, to_state: str, action: str) -> None:
        self.history.append({
            "from": from_state,
            "to": to_state,
            "action": action,
            "at": datetime.datetime.utcnow().isoformat(),
        })
        self.current_state = to_state
        self.updated_at = datetime.datetime.utcnow().isoformat()


@dataclass
class ApprovalChainEntry:
    """HD-008/HD-018: one row per approval decision taken against a
    workflow_instance. step_order lets a single instance accumulate
    multiple approval steps over time, ordered and auditable."""
    instance_id: str
    step_order: int
    approver_upn: Optional[str]
    status: str  # e.g. "Approved" | "Rejected"
    actioned_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


def compute_sla_breached(target_resolution_at) -> bool:
    """HD-007: pure, offline-testable function. An SLA is breached once
    the current UTC time has passed target_resolution_at. A None target
    is never breached. Deliberately a LIVE computation, not a stored bit
    a timer job must flip."""
    if not target_resolution_at:
        return False
    target = target_resolution_at
    if isinstance(target, str):
        target = datetime.datetime.fromisoformat(target.replace("Z", "+00:00"))
    if target.tzinfo is None:
        target = target.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc) > target


@dataclass
class SlaClock:
    """HD-007: one row per workflow_instance, tracking its SLA response/
    resolution targets. breached_flag is a computed property, not a stored
    field."""
    instance_id: str
    target_response_at: Optional[str]
    target_resolution_at: Optional[str]

    @property
    def breached_flag(self) -> bool:
        return compute_sla_breached(self.target_resolution_at)


class WorkflowStoreError(Exception):
    pass


class WorkflowStore:
    """Abstract interface. SqlWorkflowStore implements this exact same
    interface — the orchestrator and API endpoints depend only on this
    contract, never on a specific storage technology."""
    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        raise NotImplementedError

    def create_instance(self, workflow_def_id: str, requester_upn: Optional[str] = None) -> WorkflowInstance:
        raise NotImplementedError

    def get_instance(self, instance_id: str) -> WorkflowInstance:
        raise NotImplementedError

    def save_instance(self, instance: WorkflowInstance) -> None:
        raise NotImplementedError

    def append_approval_entry(
        self, instance_id: str, approver_upn: Optional[str], status: str
    ) -> ApprovalChainEntry:
        raise NotImplementedError

    def get_approval_chain(self, instance_id: str) -> List[ApprovalChainEntry]:
        raise NotImplementedError

    def create_sla_clock(
        self, instance_id: str, target_response_at: Optional[str], target_resolution_at: Optional[str]
    ) -> "SlaClock":
        raise NotImplementedError

    def get_sla_clock(self, instance_id: str) -> Optional["SlaClock"]:
        raise NotImplementedError

    def get_instances_by_requester(self, requester_upn: str) -> List[WorkflowInstance]:
        """HD-028. Returns all instances started by this requester_upn,
        most-recently-created first."""
        raise NotImplementedError

    def get_instances_pending_role(self, role: str) -> List[WorkflowInstance]:
        """HD-029. Returns all non-terminal instances whose current_state
        has at least one outgoing transition requiring this role. See this
        module's docstring for why this is a derived query rather than a
        stored 'Pending' approval_chain row."""
        raise NotImplementedError


class InMemoryWorkflowStore(WorkflowStore):
    """Original HD-015/HD-016 implementation. Data does not persist across
    Function App restarts. Safe fallback when Azure SQL is not configured."""
    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._approval_chains: Dict[str, List[ApprovalChainEntry]] = {}
        self._sla_clocks: Dict[str, SlaClock] = {}
        self._seed_test_definition()
        self._seed_test_approval_definition()

    def _seed_test_definition(self) -> None:
        states = ["Start", "Middle", "End"]
        transitions = [
            {"from": "Start", "to": "Middle", "action": "advance"},
            {"from": "Middle", "to": "End", "action": "advance"},
        ]
        self._definitions["TEST"] = WorkflowDefinition(
            workflow_def_id="TEST",
            states=states,
            transitions=transitions,
            terminal_states=compute_terminal_states(states, transitions),
        )

    def _seed_test_approval_definition(self) -> None:
        states = ["Start", "PendingApproval", "Approved", "Rejected"]
        transitions = [
            {"from": "Start", "to": "PendingApproval", "action": "submit"},
            {"from": "PendingApproval", "to": "Approved", "action": "approve", "requiredRole": "Approver"},
            {"from": "PendingApproval", "to": "Rejected", "action": "reject", "requiredRole": "Approver"},
        ]
        self._definitions["TEST_APPROVAL"] = WorkflowDefinition(
            workflow_def_id="TEST_APPROVAL",
            states=states,
            transitions=transitions,
            terminal_states=compute_terminal_states(states, transitions),
        )

    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        if workflow_def_id not in self._definitions:
            raise WorkflowStoreError(f"Unknown workflow_def_id: {workflow_def_id}")
        return self._definitions[workflow_def_id]

    def create_instance(self, workflow_def_id: str, requester_upn: Optional[str] = None) -> WorkflowInstance:
        definition = self.get_definition(workflow_def_id)
        instance = WorkflowInstance(
            instance_id=str(uuid.uuid4()),
            workflow_def_id=workflow_def_id,
            current_state=definition.initial_state(),
            requester_upn=requester_upn,
        )
        self._instances[instance.instance_id] = instance
        return instance

    def get_instance(self, instance_id: str) -> WorkflowInstance:
        if instance_id not in self._instances:
            raise WorkflowStoreError(f"Unknown instance_id: {instance_id}")
        return self._instances[instance_id]

    def save_instance(self, instance: WorkflowInstance) -> None:
        self._instances[instance.instance_id] = instance

    def append_approval_entry(
        self, instance_id: str, approver_upn: Optional[str], status: str
    ) -> ApprovalChainEntry:
        chain = self._approval_chains.setdefault(instance_id, [])
        entry = ApprovalChainEntry(
            instance_id=instance_id,
            step_order=len(chain) + 1,
            approver_upn=approver_upn,
            status=status,
        )
        chain.append(entry)
        return entry

    def get_approval_chain(self, instance_id: str) -> List[ApprovalChainEntry]:
        return list(self._approval_chains.get(instance_id, []))

    def create_sla_clock(
        self, instance_id: str, target_response_at: Optional[str], target_resolution_at: Optional[str]
    ) -> SlaClock:
        clock = SlaClock(
            instance_id=instance_id,
            target_response_at=target_response_at,
            target_resolution_at=target_resolution_at,
        )
        self._sla_clocks[instance_id] = clock
        return clock

    def get_sla_clock(self, instance_id: str) -> Optional[SlaClock]:
        return self._sla_clocks.get(instance_id)

    def get_instances_by_requester(self, requester_upn: str) -> List[WorkflowInstance]:
        matches = [i for i in self._instances.values() if i.requester_upn == requester_upn]
        return sorted(matches, key=lambda i: i.created_at, reverse=True)

    def get_instances_pending_role(self, role: str) -> List[WorkflowInstance]:
        matches = []
        for instance in self._instances.values():
            definition = self._definitions.get(instance.workflow_def_id)
            if definition is None:
                continue
            if definition.is_terminal(instance.current_state):
                continue
            if role in definition.roles_pending_from(instance.current_state):
                matches.append(instance)
        return sorted(matches, key=lambda i: i.created_at, reverse=True)


# Module-level singleton. NOTE: for InMemoryWorkflowStore, this is not
# reliable across concurrent Flex Consumption worker instances — this is why
# HD-002/003/005/006/008 exist. Once AZURE_SQL_SERVER is set, get_store()
# returns a SqlWorkflowStore instead.
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
            logging.exception(
                "get_store: AZURE_SQL_SERVER is set but SqlWorkflowStore failed to "
                "initialise. Falling back to InMemoryWorkflowStore."
            )
    _store_instance = InMemoryWorkflowStore()
    return _store_instance
