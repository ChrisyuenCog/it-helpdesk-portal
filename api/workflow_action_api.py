
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
HD-026/030/033/034:
  - parse_action_request() gains an optional 'fields' key in the request
    body (e.g. {"serialNumber": "SN123"}), returned in the parsed dict as
    parsed["fields"] (defaults to {} if absent).
  - check_role_permission() accepts a transition whose 'requiredRole' is
    EITHER a single string (unchanged) OR a list of acceptable roles (new,
    e.g. HARDWARE_REQUEST's ITApproval transitions, actionable by EITHER
    'ITAgent' OR 'ITAdmin'). Delegates to
    workflow_store.normalize_required_roles().
  - check_required_fields() / MissingRequiredFieldError — HD-033's hard
    gate, implemented generically via a transition's 'requiredFields' list.
  - resolve_expected_approver() — HD-030's dynamic-approver resolution.
HD-026/030 PRODUCTION FIX (this revision):
  A live-deployment bug was found and fixed here: the deferred
  `from graph_api import resolve_manager_upn` import was previously OUTSIDE
  the try/except block, so any import-time failure of graph_api.py inside
  the live Azure Functions worker (module path/packaging issue, or any
  other cause) raised an UNHANDLED exception straight up through
  advance_workflow_instance's Durable Functions activity call — causing
  the entire activity invocation to fail silently from the caller's
  perspective (the workflow_instance was created but its history stayed
  permanently empty, stuck at its initial state, with no error surfaced to
  GET /api/workflow/instance/{instanceId}). This was not caught by
  test_workflow_action_api.py's offline tests because every test there
  supplies resolve_manager_upn_fn explicitly, so the deferred import path
  itself was never actually exercised. Fix: both the import AND the call
  are now inside the SAME try/except — resolve_expected_approver() is
  fully fail-soft end-to-end, exactly as its docstring already claimed,
  with no exception able to escape regardless of WHERE it originates
  (import time or call time).
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
    'fields' dict — maps to HTTP 400 in function_app.py."""
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
    the caller did not supply a matching one. 'requiredRole' may be a
    single string or a list of acceptable roles — a caller matching ANY
    one of the acceptable roles is permitted."""
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
    (whitespace-only) in the caller-supplied 'fields' dict."""
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
    (never raises — see this module's docstring for the production fix
    that closed a real gap here) if 'resolveApprover' isn't set, if the
    instance has no requester_upn, or if resolution fails for ANY reason,
    including a failure to import graph_api itself. A failed/unavailable
    approver resolution must never block the underlying state transition."""
    if transition.get("resolveApprover") != "requesterManager":
        return None
    if not instance.requester_upn:
        return None
    try:
        if resolve_manager_upn_fn is None:
            from graph_api import resolve_manager_upn as resolve_manager_upn_fn
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
