
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
HD-028/029:
  - WorkflowInstance gains requester_upn.
  - WorkflowDefinition.roles_pending_from(state) — derived query support.
  - WorkflowStore.get_instances_by_requester() / get_instances_pending_role().
HD-026/030/033/034 (this revision) — Hardware Request backend:
  - WorkflowDefinition transitions may now carry 'requiredRole' as EITHER a
    single string (unchanged, e.g. TEST_APPROVAL's "Approver") OR a list of
    acceptable roles (new, e.g. HARDWARE_REQUEST's ITApproval transitions,
    actionable by EITHER 'ITAgent' OR 'ITAdmin'). normalize_required_roles()
    is the single place that turns either shape into a flat list, used by
    BOTH roles_pending_from() below and workflow_action_api.py's
    check_role_permission(), so the two can never silently disagree on what
    "this transition requires role X" means.
  - WorkflowInstance.record_transition() gains two new OPTIONAL keyword
    arguments: 'fields' (a dict of caller-supplied data captured at this
    transition, e.g. {"serialNumber": "SN123"}) and 'expected_approver_upn'
    (the dynamically-resolved approver for a transition entering an
    approval state, e.g. via Graph manager lookup). CRITICAL DESIGN NOTE:
    neither is a new persisted database column. Both are embedded as
    OPTIONAL extra keys on the SAME history entry dict that already gets
    appended and round-tripped as JSON via the EXISTING historyJson column
    in both InMemoryWorkflowStore and SqlWorkflowStore. This deliberately
    avoids repeating the HD-028 regression (a persisted-column addition
    that changed row_to_instance's tuple shape from 6->7 and broke a test
    file that had never been reviewed for the change). Adding new JSON keys
    to an already-JSON column requires ZERO schema migration, ZERO change
    to row_to_instance/build_insert_instance_params/build_update_instance_params
    tuple shapes, and is fully backward compatible — old history entries
    simply don't have these keys, and the derived getters below return
    sensible defaults (empty dict / None) when they're absent.
  - WorkflowInstance.get_fields() — scans history in order, merging every
    entry's 'fields' dict (later entries win on key collision), giving a
    single flattened "current known field values" view with no new state
    to keep in sync.
  - WorkflowInstance.get_expected_approver_upn() — scans history in
    REVERSE, returning the most recent entry's 'expectedApproverUpn' if
    present, else None.
  - InMemoryWorkflowStore now also seeds HARDWARE_REQUEST (Section 4.1 of
    the MVP Specification) alongside TEST/TEST_APPROVAL, so the full state
    machine (including its list-form requiredRole transitions) is
    offline-testable without a live SQL Database. The equivalent live-SQL
    row is inserted via sql/seed_hardware_request_definition.sql (a manual,
    one-time data seed — same precedent as schema_hd003_hd004.sql — since
    workflow_definition rows are DATA, not application code, and this MVP
    has no admin UI/endpoint for authoring them yet, per the permissions
    matrix in the MVP Specification Section 3.2).
"""
from __future__ import annotations
import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Union


def compute_terminal_states(states: List[str], transitions: List[Dict[str, Any]]) -> List[str]:
    """A state is terminal if no transition has it as a 'from'. Shared by
    both InMemoryWorkflowStore's seeding and SqlWorkflowStore's row parsing
    (see sql_workflow_store.py), so the two backends can never disagree on
    which states are terminal for the same definition."""
    states_with_outgoing = {t["from"] for t in transitions}
    return [s for s in states if s not in states_with_outgoing]


def normalize_required_roles(required_role: Optional[Union[str, List[str]]]) -> List[str]:
    """HD-026/031: a transition's 'requiredRole' may be a single string
    (unchanged since HD-018, e.g. "Approver") OR a list of strings (new,
    e.g. ["ITAgent", "ITAdmin"] for HARDWARE_REQUEST's ITApproval state,
    which either role may action). This is the SINGLE place that flattens
    either shape into a plain list — both roles_pending_from() below and
    workflow_action_api.py's check_role_permission() call this, so the two
    can never silently drift out of sync on what "requires role X" means
    for a given transition. Returns an empty list for a role-free
    transition (requiredRole absent or None)."""
    if required_role is None:
        return []
    if isinstance(required_role, str):
        return [required_role]
    return list(required_role)


@dataclass
class WorkflowDefinition:
    workflow_def_id: str
    states: List[str]
    transitions: List[Dict[str, Any]]  # each: {"from", "to", "action", "requiredRole"?, "requiredFields"?, "resolveApprover"?, "onEnterEffects"?}
    terminal_states: List[str]

    def get_transition(self, current_state: str, action: str) -> Optional[Dict[str, Any]]:
        """Returns the FULL transition dict (including 'requiredRole',
        'requiredFields', 'resolveApprover', 'onEnterEffects' if present)
        for a given (current_state, action) pair, or None if undefined."""
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
        """HD-029, extended HD-026/031 for list-form requiredRole: returns
        the sorted, deduplicated list of every individual role that could
        action a transition out of current_state. A transition whose
        requiredRole is a list (e.g. ITApproval's ["ITAgent","ITAdmin"])
        contributes BOTH roles individually — so an ITAgent's myApprovals
        AND an ITAdmin's myApprovals both correctly include the same
        pending instance, exactly matching HARDWARE_REQUEST's "ITAgent or
        ITAdmin" design. Role-free transitions never contribute a role."""
        roles: Set[str] = set()
        for t in self.transitions:
            if t["from"] == current_state:
                roles.update(normalize_required_roles(t.get("requiredRole")))
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

    def record_transition(
        self,
        from_state: str,
        to_state: str,
        action: str,
        fields: Optional[Dict[str, Any]] = None,
        expected_approver_upn: Optional[str] = None,
        actor_upn: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        """HD-026/030/033: 'fields' and 'expected_approver_upn' are OPTIONAL
        and embedded directly in this history entry — see this module's
        docstring for why this is deliberately NOT a new persisted column.
        Both default to None/absent for every pre-existing caller, so this
        change is fully backward compatible with HD-015 through HD-029."""
        entry: Dict[str, Any] = {
            "from": from_state,
            "to": to_state,
            "action": action,
            "at": datetime.datetime.utcnow().isoformat(),
        }
        if fields:
            entry["fields"] = dict(fields)
        if expected_approver_upn is not None:
            entry["expectedApproverUpn"] = expected_approver_upn
        # Phase 1 audit trail: who took the step (from the sign-in token) and why.
        if actor_upn:
            entry["by"] = actor_upn
        if comment:
            entry["comment"] = comment
        self.history.append(entry)
        self.current_state = to_state
        self.updated_at = datetime.datetime.utcnow().isoformat()

    def get_fields(self) -> Dict[str, Any]:
        """HD-026/033: flattens every history entry's 'fields' dict, in
        chronological order (later entries win on key collision — e.g. a
        HARDWARE_REQUEST instance's 'itemDescription' captured at Submitted
        remains available all the way through Fulfilled, while a
        'serialNumber' captured later at AwaitingSerialCapture->Fulfilled
        is added without disturbing the earlier key)."""
        merged: Dict[str, Any] = {}
        for entry in self.history:
            if "fields" in entry:
                merged.update(entry["fields"])
        return merged

    def get_expected_approver_upn(self) -> Optional[str]:
        """HD-030: returns the most recently recorded expectedApproverUpn
        (scanning history in reverse), or None if this instance has never
        had one resolved — e.g. every existing TEST/TEST_APPROVAL instance,
        or a HARDWARE_REQUEST instance where Graph manager resolution
        wasn't yet available (HD-012 not yet provisioned) and gracefully
        returned nothing."""
        for entry in reversed(self.history):
            if "expectedApproverUpn" in entry:
                return entry["expectedApproverUpn"]
        return None


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
    is never breached."""
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
        raise NotImplementedError

    def get_instances_pending_role(self, role: str) -> List[WorkflowInstance]:
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
        self._seed_hardware_request_definition()

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

    def _seed_hardware_request_definition(self) -> None:
        """HD-026: seeds HARDWARE_REQUEST exactly per MVP Specification
        Section 4.1 — 7 states, role-gated approval chain (ManagerApproval
        -> ITApproval -> Procurement), a hard AwaitingSerialCapture gate
        (HD-033, enforced via requiredFields, not a fixed SLA), and a
        Fulfilled-entry side effect that creates the resulting Hardware CI
        (HD-034, enforced via onEnterEffects, interpreted generically by
        workflow_effects_api.py — this module has zero knowledge of what
        "createCi" actually does)."""
        states = [
            "Submitted", "ManagerApproval", "ITApproval", "Procurement",
            "AwaitingSerialCapture", "Fulfilled", "Rejected",
        ]
        transitions = [
            {
                "from": "Submitted", "to": "ManagerApproval", "action": "advance",
                "resolveApprover": "requesterManager",
            },
            {
                "from": "ManagerApproval", "to": "ITApproval", "action": "approve",
                "requiredRole": "Approver",
            },
            {
                "from": "ManagerApproval", "to": "Rejected", "action": "reject",
                "requiredRole": "Approver",
            },
            {
                "from": "ITApproval", "to": "Procurement", "action": "approve",
                "requiredRole": ["ITAgent", "ITAdmin"],
            },
            {
                "from": "ITApproval", "to": "Rejected", "action": "reject",
                "requiredRole": ["ITAgent", "ITAdmin"],
            },
            {
                "from": "Procurement", "to": "AwaitingSerialCapture", "action": "markOrdered",
                "requiredRole": "ITAdmin",
            },
            {
                "from": "AwaitingSerialCapture", "to": "Fulfilled", "action": "captureSerial",
                "requiredRole": "ITAdmin",
                "requiredFields": ["serialNumber"],
                "onEnterEffects": [
                    {
                        "type": "createCi",
                        "ciClass": "Hardware",
                        "relationshipType": "user has",
                        "nameField": "itemDescription",
                        "statusValue": "InService",
                    }
                ],
            },
        ]
        self._definitions["HARDWARE_REQUEST"] = WorkflowDefinition(
            workflow_def_id="HARDWARE_REQUEST",
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
