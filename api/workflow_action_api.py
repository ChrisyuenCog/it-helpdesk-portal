
"""
IT Helpdesk Portal — Workflow Action API request/response logic (HD-018)
===========================================================================
Pure request-validation, transition-resolution, and role-checking logic
for POST /api/workflow/action, separated from the actual Azure Functions
HTTP trigger in function_app.py, same pattern as workflow_api.py for
HD-017, so it can be offline-tested without a live Durable Functions host.
*** IMPORTANT SECURITY SCOPE NOTE — READ BEFORE RELYING ON THIS CODE ***
This ticket accepts the caller's role as an explicit 'callerRole' field in
the REQUEST BODY, not from a validated Microsoft Entra ID token claim. This
is a deliberate, temporary MVP simplification — see HD-066, Security
Hardening. Until that lands, 'callerRole' is NOT a real access-control
boundary.
HD-026/030/033/034 (this revision) — Hardware Request backend:
  - parse_action_request() gains an optional 'fields' key in the request
    body (e.g. {"serialNumber": "SN123"}), returned in the parsed dict as
    parsed["fields"] (defaults to {} if absent — never None, so callers
    never need a None-check before passing it to instance.record_transition
    or check_required_fields).
  - check_role_permission() now accepts a transition whose 'requiredRole'
    is EITHER a single string (unchanged) OR a list of acceptable roles
    (new, e.g. HARDWARE_REQUEST's ITApproval transitions, actionable by
    EITHER 'ITAgent' OR 'ITAdmin'). Delegates to
    workflow_store.normalize_required_roles() so this function and
    WorkflowDefinition.roles_pending_from() can never disagree on what a
    transition's requiredRole actually means.
  - check_required_fields() / MissingRequiredFieldError — HD-033's hard
    gate, implemented GENERICALLY: a transition may declare
    'requiredFields': ["serialNumber"], and this function raises if any
    named field is missing or blank in the caller-supplied 'fields' dict.
    Nothing here says "Hardware" or "serialNumber" specifically — those are
    DATA on the HARDWARE_REQUEST workflow_definition (see
    workflow_store.py's _seed_hardware_request_definition), not code here.
  - resolve_expected_approver() — HD-030's dynamic-approver resolution. A
    transition may declare 'resolveApprover': "requesterManager", meaning
    "when this transition is taken, look up the requester's manager via
    Graph and record it as the expected approver for the state being
    entered." The actual Graph call is injected as `resolve_manager_upn_fn`
    (defaults to graph_api.resolve_manager_upn) so this function is fully
    offline-testable with a fake resolver — this function contains no
    Graph-specific code itself, only the generic "if this transition asks
    for approver resolution, call the injected resolver and return its
    result (or None on any failure)" logic.
"""
from __future__ import annotations
import json
from typing import Optional, Dict, Any, List, Callable
from workflow_store import WorkflowDefinition, WorkflowInstance, WorkflowStoreError, normalize_required_roles
from workflow_api import build_error_response  # reused for a single, consistent error shape


class ActionRequestValidationError(Exception):
    """Raised for any problem with the incoming request body itself
    (missing/malformed fields) — maps to HTTP 400 in function_app.py."""
    pass


class ActionNotAllowedError(Exception):
    """Raised when the requested action is not a valid transition from the
    instance's CURRENT state (including when the instance is already in a
    terminal state) — maps to HTTP 400."""
    pass


class RoleNotPermittedError(Exception):
    """Raised when a transition exists but requires a role the caller did
    not supply (or supplied a non-matching one) — maps to HTTP 403."""
    pass


class MissingRequiredFieldError(Exception):
    """HD-033: raised when a transition declares 'requiredFields' and one
    or more of those fields is missing or blank in the caller-supplied
    'fields' dict — maps to HTTP 400 in function_app.py. Kept as its own
    exception (distinct from ActionRequestValidationError, which is about
    the request body's own SHAPE, and ActionNotAllowedError, which is about
    the transition not existing) so each distinct failure reason maps to
    its own, distinguishable error, matching this module's established
    precedent."""
    pass


def parse_action_request(raw_body: Optional[bytes]) -> Dict[str, Any]:
    """Validates the request body shape. Does not check whether instanceId
    refers to a real instance, or whether the action is valid for that
    instance's state — those are separate, subsequent steps."""
    if not raw_body:
        raise ActionRequestValidationError("Request body is required and must be JSON.")
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ActionRequestValidationError(f"Request body must be valid JSON: {e}")
    if not isinstance(body, dict):
        raise ActionRequestValidationError("Request body must be a JSON object.")
    instance_id = body.get("instanceId")
    if not instance_id or not isinstance(instance_id, str):
        raise ActionRequestValidationError("'instanceId' is required and must be a non-empty string.")
    action = body.get("action")
    if not action or not isinstance(action, str):
        raise ActionRequestValidationError("'action' is required and must be a non-empty string.")
    caller_role = body.get("callerRole")
    if caller_role is not None and not isinstance(caller_role, str):
        raise ActionRequestValidationError("'callerRole', if provided, must be a string.")
    caller_upn = body.get("callerUpn")
    if caller_upn is not None and not isinstance(caller_upn, str):
        raise ActionRequestValidationError("'callerUpn', if provided, must be a string.")
    fields = body.get("fields")
    if fields is not None and not isinstance(fields, dict):
        raise ActionRequestValidationError("'fields', if provided, must be a JSON object.")
    return {
        "instanceId": instance_id,
        "action": action,
        "callerRole": caller_role,
        "callerUpn": caller_upn,
        "fields": fields or {},
    }


def resolve_transition(definition: WorkflowDefinition, instance: WorkflowInstance, action: str) -> Dict[str, Any]:
    """Returns the full transition dict for the instance's current state +
    the requested action. Raises ActionNotAllowedError if the instance is
    already terminal, or if no such transition is defined from its current
    state."""
    if definition.is_terminal(instance.current_state):
        raise ActionNotAllowedError(
            f"Instance {instance.instance_id} is already in terminal state "
            f"'{instance.current_state}'; no further actions are possible."
        )
    transition = definition.get_transition(instance.current_state, action)
    if transition is None:
        raise ActionNotAllowedError(
            f"Action '{action}' is not valid from state '{instance.current_state}' "
            f"for workflow '{definition.workflow_def_id}'."
        )
    return transition


def check_role_permission(transition: Dict[str, Any], caller_role: Optional[str]) -> None:
    """Raises RoleNotPermittedError if the transition requires a role and
    the caller did not supply a matching one. HD-026/031: 'requiredRole'
    may be a single string (unchanged) or a list of acceptable roles (new)
    — normalize_required_roles() flattens either shape, so a caller
    matching ANY one of the acceptable roles is permitted. A transition
    with no requiredRole is permitted for any caller, preserving TEST's
    original role-free behaviour exactly."""
    acceptable_roles = normalize_required_roles(transition.get("requiredRole"))
    if not acceptable_roles:
        return  # no role required — anyone may perform this transition
    if caller_role not in acceptable_roles:
        required_desc = acceptable_roles[0] if len(acceptable_roles) == 1 else " or ".join(acceptable_roles)
        raise RoleNotPermittedError(
            f"This action requires role '{required_desc}'; caller supplied '{caller_role}'."
        )


def check_required_fields(transition: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """HD-033: raises MissingRequiredFieldError if any field named in the
    transition's 'requiredFields' list is missing, None, or blank
    (whitespace-only) in the caller-supplied 'fields' dict. A transition
    with no 'requiredFields' key imposes no constraint — this preserves
    every existing transition's behaviour (TEST, TEST_APPROVAL, and every
    other HARDWARE_REQUEST transition except AwaitingSerialCapture->
    Fulfilled) exactly."""
    required = transition.get("requiredFields", [])
    missing = []
    for field_name in required:
        value = fields.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field_name)
    if missing:
        raise MissingRequiredFieldError(
            f"The following required field(s) are missing or blank: {', '.join(missing)}."
        )


def resolve_expected_approver(
    transition: Dict[str, Any],
    instance: WorkflowInstance,
    resolve_manager_upn_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[str]:
    """HD-030: if this transition declares 'resolveApprover': "requesterManager",
    calls the injected resolver (defaults to graph_api.resolve_manager_upn)
    with instance.requester_upn and returns its result. Returns None
    (never raises) if 'resolveApprover' isn't set on this transition, if
    the instance has no requester_upn, or if the resolver itself returns
    None (e.g. Graph permissions not yet provisioned — see graph_api.py's
    module docstring for the HD-012 dependency note). This function is
    deliberately tolerant: a failed/unavailable approver resolution must
    never block the underlying state transition itself."""
    if transition.get("resolveApprover") != "requesterManager":
        return None
    if not instance.requester_upn:
        return None
    if resolve_manager_upn_fn is None:
        from graph_api import resolve_manager_upn as resolve_manager_upn_fn
    try:
        return resolve_manager_upn_fn(instance.requester_upn)
    except Exception:
        return None


def determine_approval_status(action: str) -> str:
    """Maps an action name to the status recorded in the approval_chain
    entry. 'approve' -> 'Approved', 'reject' -> 'Rejected'; any other
    role-gated action name is recorded verbatim (capitalised)."""
    mapping = {"approve": "Approved", "reject": "Rejected"}
    return mapping.get(action, action.capitalize())


def build_action_success_response(
    instance: WorkflowInstance,
    transition: Dict[str, Any],
    approval_entry: Optional[Any] = None,
    effects: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    response = {
        "status": "actioned",
        "instanceId": instance.instance_id,
        "workflowDefId": instance.workflow_def_id,
        "previousState": transition["from"],
        "currentState": instance.current_state,
        "action": transition["action"],
    }
    if approval_entry is not None:
        response["approvalChainEntry"] = {
            "stepOrder": approval_entry.step_order,
            "approverUpn": approval_entry.approver_upn,
            "status": approval_entry.status,
            "actionedAt": approval_entry.actioned_at,
        }
    if effects:
        response["effects"] = effects
    return response
