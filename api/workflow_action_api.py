"""
IT Helpdesk Portal — Workflow Action API request/response logic (HD-018)
===========================================================================
Pure request-validation, transition-resolution, and role-checking logic
for POST /api/workflow/action, separated from the actual Azure Functions
HTTP trigger in function_app.py (same pattern as workflow_api.py for
HD-017), so it can be offline-tested without a live Durable Functions host.

*** IMPORTANT SECURITY SCOPE NOTE — READ BEFORE RELYING ON THIS CODE ***
This ticket accepts the caller's role as an explicit 'callerRole' field in
the REQUEST BODY, not from a validated Microsoft Entra ID token claim. This
is a deliberate, temporary MVP simplification: the IT Helpdesk Portal's own
Entra App Roles / token validation (distinct from the CLG DevOps Agent's
already-built roles) has not been implemented yet — that work belongs to
the "Security Hardening" epic (HD-066 and related, MVP Specification
Sprint 4). Until that lands, 'callerRole' is NOT a real access-control
boundary: any caller can currently claim to be an "Approver" simply by
setting that field. This ticket exists to prove the ROLE-CHECKING LOGIC
itself is correct (i.e. that a mismatched role is correctly rejected, and
a matching role is correctly permitted) — it does NOT yet prove that only
genuine Approvers can supply that role. Do not treat this endpoint as
production-secure until it is wired to real, server-validated identity.
"""
from __future__ import annotations
import json
from typing import Optional, Dict, Any

from workflow_store import WorkflowDefinition, WorkflowInstance, WorkflowStoreError
from workflow_api import build_error_response  # reused for a single, consistent error shape


class ActionRequestValidationError(Exception):
    """Raised for any problem with the incoming request body itself
    (missing/malformed fields) — maps to HTTP 400 in function_app.py."""
    pass


class ActionNotAllowedError(Exception):
    """Raised when the requested action is not a valid transition from the
    instance's CURRENT state (including when the instance is already in a
    terminal state) — maps to HTTP 400. Distinct from RoleNotPermittedError
    below so the two different failure reasons are never conflated: 'this
    action doesn't exist from here' vs 'you're not allowed to do this
    action'."""
    pass


class RoleNotPermittedError(Exception):
    """Raised when a transition exists but requires a role the caller did
    not supply (or supplied a non-matching one) — maps to HTTP 403, per
    HD-018's acceptance criterion."""
    pass


def parse_action_request(raw_body: Optional[bytes]) -> Dict[str, Any]:
    """Validates the request body shape. Does not check whether instanceId
    refers to a real instance, or whether the action is valid for that
    instance's state — those are separate, subsequent steps (see
    resolve_transition below) so each distinct failure reason maps to its
    own, distinguishable error."""
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

    return {
        "instanceId": instance_id,
        "action": action,
        "callerRole": caller_role,
        "callerUpn": caller_upn,
    }


def resolve_transition(definition: WorkflowDefinition, instance: WorkflowInstance, action: str) -> Dict[str, str]:
    """Returns the full transition dict for the instance's current state +
    the requested action. Raises ActionNotAllowedError if the instance is
    already terminal, or if no such transition is defined from its current
    state — both are '400 bad request for this instance's state', distinct
    from a role-permission failure."""
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


def check_role_permission(transition: Dict[str, str], caller_role: Optional[str]) -> None:
    """Raises RoleNotPermittedError if the transition requires a specific
    role and the caller did not supply a matching one. A transition with
    no 'requiredRole' key is permitted for any caller, including one who
    supplied no role at all — this preserves TEST's original role-free
    behaviour exactly."""
    required_role = transition.get("requiredRole")
    if required_role is None:
        return  # no role required — anyone may perform this transition
    if caller_role != required_role:
        raise RoleNotPermittedError(
            f"This action requires role '{required_role}'; caller supplied "
            f"'{caller_role}'."
        )


def determine_approval_status(action: str) -> str:
    """Maps an action name to the status recorded in the approval_chain
    entry. 'approve' -> 'Approved', 'reject' -> 'Rejected'; any other
    role-gated action name is recorded verbatim (capitalised), so future
    workflow definitions can introduce new role-gated action names (e.g.
    'escalate') without requiring a code change here."""
    mapping = {"approve": "Approved", "reject": "Rejected"}
    return mapping.get(action, action.capitalize())


def build_action_success_response(
    instance: WorkflowInstance,
    transition: Dict[str, str],
    approval_entry: Optional[Any] = None,
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
    return response