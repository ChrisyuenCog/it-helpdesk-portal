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
    the exact same way — previously this logic only existed on the SQL
    side, and in-memory definitions had terminal_states hardcoded
    separately, which could silently drift out of sync as definitions grew
    more complex (like this ticket's new TEST_APPROVAL).
  - ApprovalChainEntry + WorkflowStore.append_approval_entry() /
    get_approval_chain() — this is HD-008's approval_chain table,
    bundled into this ticket. Reason: HD-018's own acceptance criterion
    ("...appends to approval_chain where relevant") cannot be satisfied
    without it existing — building HD-018 without HD-008 would produce
    code that claims to do something it structurally cannot do.
  - InMemoryWorkflowStore now also seeds a second definition, TEST_APPROVAL,
    alongside the original TEST. TEST's transitions are all role-free
    (unchanged, zero regression risk); TEST_APPROVAL adds one role-gated
    'approve'/'reject' pair specifically so HD-018's role-check logic has
    something real to exercise, both in tests and in a live smoke test.
HD-007 (this revision):
  - SlaClock dataclass + compute_sla_breached() — a pure, offline-testable
    function. An SLA is breached once the current UTC time has passed
    target_resolution_at. A None target (matches HD-032's Procurement
    state, which the spec explicitly says has 'no fixed SLA target') is
    never breached. breached_flag is deliberately a LIVE computed property,
    not a stored bit a timer job must flip — this is what makes HD-007's
    acceptance criterion ("querying breachedFlag returns the expected
    boolean after the target time passes in a test") true without needing
    a background job to run between the insert and the query in a
    fast-running test.
  - WorkflowStore.create_sla_clock() / get_sla_clock() — same "abstract
    interface + InMemoryWorkflowStore implementation" pattern already
    established for approval_chain in HD-018. SqlWorkflowStore's matching
    implementation lives in sql_workflow_store.py, backed by the new
    dbo.sla_clock table (see sql/schema_update_hd007.sql).
"""
from __future__ import annotations
import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


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
        both next_state() (used by the auto-advance orchestrator loop) and
        HD-018's role-checking logic (workflow_action_api.py) go through
        this single method, so there is exactly one source of truth for
        'what happens on this action from this state'."""
        for t in self.transitions:
            if t["from"] == current_state and t["action"] == action:
                return t
        return None

    def next_state(self, current_state: str, action: str) -> Optional[str]:
        """Unchanged contract from HD-015: returns just the resulting
        state, or None. Reimplemented on top of get_transition() so there
        is no duplicate lookup logic to keep in sync."""
        transition = self.get_transition(current_state, action)
        return transition["to"] if transition else None

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


@dataclass
class ApprovalChainEntry:
    """HD-008/HD-018: one row per approval decision taken against a
    workflow_instance. step_order lets a single instance accumulate
    multiple approval steps over time (e.g. Manager approval, then IT
    approval, in a future multi-tier workflow), ordered and auditable."""
    instance_id: str
    step_order: int
    approver_upn: Optional[str]
    status: str  # e.g. "Approved" | "Rejected"
    actioned_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


def compute_sla_breached(target_resolution_at) -> bool:
    """HD-007: pure, offline-testable function (see test_sla_clock.py).
    An SLA is breached once the current UTC time has passed
    target_resolution_at. A None target (matches HD-032's Procurement
    state, which the spec explicitly says has 'no fixed SLA target') is
    never breached.

    Deliberately a LIVE computation rather than a stored bit that a timer
    job must flip — this is what makes HD-007's acceptance criterion
    ("querying breachedFlag returns the expected boolean after the
    target time passes in a test") true without needing a background
    job to run between the insert and the query in a fast-running test.

    Accepts either a datetime object or an ISO-format string (the latter
    is what SqlWorkflowStore's row parsing and InMemoryWorkflowStore's
    plain-string storage both produce), so callers never need to know
    which backend they're talking to."""
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
    field — see compute_sla_breached() for why."""
    instance_id: str
    target_response_at: Optional[str]
    target_resolution_at: Optional[str]

    @property
    def breached_flag(self) -> bool:
        return compute_sla_breached(self.target_resolution_at)


class WorkflowStoreError(Exception):
    pass


class WorkflowStore:
    """Abstract interface. SqlWorkflowStore (backed by Azure SQL) implements
    this exact same interface — the orchestrator and API endpoints depend
    only on this contract, never on a specific storage technology."""
    def get_definition(self, workflow_def_id: str) -> WorkflowDefinition:
        raise NotImplementedError

    def create_instance(self, workflow_def_id: str) -> WorkflowInstance:
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
        """HD-007. Implementations should insert (or upsert) a single
        sla_clock row for this instance_id and return it."""
        raise NotImplementedError

    def get_sla_clock(self, instance_id: str) -> Optional["SlaClock"]:
        """HD-007. Returns None if no sla_clock row exists for this
        instance_id yet (e.g. states like Procurement that have no fixed
        SLA target per the MVP spec)."""
        raise NotImplementedError


class InMemoryWorkflowStore(WorkflowStore):
    """Original HD-015/HD-016 implementation. Data does not persist across
    Function App restarts. Retained as the safe fallback when Azure SQL is
    not yet configured (AZURE_SQL_SERVER app setting absent) — see get_store()
    below."""
    def __init__(self):
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, WorkflowInstance] = {}
        self._approval_chains: Dict[str, List[ApprovalChainEntry]] = {}
        self._sla_clocks: Dict[str, SlaClock] = {}
        self._seed_test_definition()
        self._seed_test_approval_definition()

    def _seed_test_definition(self) -> None:
        """HD-016: unchanged. Start -> Middle -> End, all role-free, all
        action='advance'. Zero regression risk from HD-018's changes."""
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
        """HD-018: a second, minimal seed definition with exactly one
        role-gated decision point, so role-checking and approval_chain
        logic have something real to exercise end to end — both in the
        offline test suite and in a live smoke test — without touching or
        risking the original TEST definition's proven behaviour.
        Start -> PendingApproval (action=submit, no role required, any
        Requester can do this)
        PendingApproval -> Approved (action=approve, requiredRole=Approver)
        PendingApproval -> Rejected (action=reject, requiredRole=Approver)
        Note: this definition has NO 'advance'-action transitions, so the
        existing auto-advance orchestrator loop (which only ever tries
        action='advance') will find nothing to auto-advance and complete
        immediately after instance creation, leaving the instance sitting
        in 'Start' until a human calls POST /api/workflow/action. This is
        intentional — see function_app.py's module docstring for the full
        explanation of why HD-018 does not extend true Durable Functions
        external-event-waiting in this ticket."""
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

    def create_instance(self, workflow_def_id: str) -> WorkflowInstance:
        definition = self.get_definition(workflow_def_id)
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
        """HD-007. Same upsert-by-instance_id shape as a SQL PK on
        instanceId would enforce — calling this twice for the same
        instance_id replaces the previous clock rather than erroring or
        duplicating, matching SqlWorkflowStore's single-row-per-instance
        table design."""
        clock = SlaClock(
            instance_id=instance_id,
            target_response_at=target_response_at,
            target_resolution_at=target_resolution_at,
        )
        self._sla_clocks[instance_id] = clock
        return clock

    def get_sla_clock(self, instance_id: str) -> Optional[SlaClock]:
        return self._sla_clocks.get(instance_id)


# Module-level singleton. NOTE: for InMemoryWorkflowStore, this is not
# reliable across concurrent Flex Consumption worker instances — this is why
# HD-002/003/005/006/008 exist. Once AZURE_SQL_SERVER is set, get_store()
# returns a SqlWorkflowStore instead, and this limitation no longer applies.
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
                "initialise. Falling back to InMemoryWorkflowStore. This means "
                "workflow data will NOT persist across restarts until the "
                "underlying SQL issue is fixed."
            )
    _store_instance = InMemoryWorkflowStore()
    return _store_instance
