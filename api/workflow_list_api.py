"""
IT Helpdesk Portal — Workflow List API request/response logic (HD-028/029)
=============================================================================
Pure request-parsing and response-building logic for:
  GET /api/workflow/myRequests    (HD-028)
  GET /api/workflow/myApprovals   (HD-029)
Separated from the Azure Functions HTTP triggers in function_app.py, same
pattern as workflow_api.py / workflow_action_api.py / workflow_instance_api.py,
so this can be offline-tested without a live Durable Functions host.

*** SCOPE NOTE — read alongside workflow_action_api.py's existing one ***
Both endpoints identify "the caller" via a query string parameter
(?requesterUpn=... / ?role=...) rather than a validated Entra ID token
claim, for the exact same MVP-stage reason already documented in
workflow_action_api.py: real identity/token validation is Sprint 4's
Security Hardening epic (HD-066), not yet built. Until then, anyone can
view any requester's requests or any role's approvals simply by supplying
that value — this endpoint proves the LIST-FILTERING LOGIC is correct, it
does not yet prove only the genuine requester/approver can see their own
list. Do not treat as production-secure until wired to real identity.

Design note on "roles_pending_from" — see workflow_store.py's module
docstring for the full rationale on why HD-029 is implemented as a DERIVED
query (is this instance non-terminal, and does its current state have an
outgoing transition requiring this role) rather than reading stored
approval_chain rows with a status of 'Pending' — this MVP's approval_chain
rows are only ever written after a decision is actioned, never before.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from workflow_store import WorkflowInstance


class MyRequestsValidationError(Exception):
    """Raised when ?requesterUpn= is missing from the query string —
    maps to HTTP 400 in function_app.py."""
    pass


class MyApprovalsValidationError(Exception):
    """Raised when ?role= is missing from the query string — maps to
    HTTP 400 in function_app.py."""
    pass


def parse_my_requests_query(query_params: Dict[str, str]) -> str:
    """Returns the validated requesterUpn string, or raises
    MyRequestsValidationError. Kept as its own function (rather than
    inlined in the HTTP trigger) so the exact validation rule is
    independently offline-testable, matching this module's siblings."""
    requester_upn = query_params.get("requesterUpn")
    if not requester_upn or not requester_upn.strip():
        raise MyRequestsValidationError(
            "'requesterUpn' query parameter is required, e.g. "
            "?requesterUpn=chris.yuen@cognitionlearninggroup.com"
        )
    return requester_upn.strip()


def parse_my_approvals_query(query_params: Dict[str, str]) -> str:
    """Returns the validated role string, or raises
    MyApprovalsValidationError."""
    role = query_params.get("role")
    if not role or not role.strip():
        raise MyApprovalsValidationError(
            "'role' query parameter is required, e.g. ?role=Approver"
        )
    return role.strip()


def build_instance_summary(instance: WorkflowInstance) -> Dict[str, Any]:
    """A deliberately LIGHTER-weight view than HD-027's full
    load_instance_view() (which also fetches approval_chain + sla_clock
    with extra store round-trips per instance). List endpoints return one
    row per matching instance, so keeping this to fields already present
    on the WorkflowInstance object itself (zero extra store calls per row)
    keeps GET /myRequests and /myApprovals cheap even as the number of
    matching instances grows. A caller wanting full detail on any one
    instance calls GET /api/workflow/instance/{instanceId} (HD-027) next,
    exactly as a real UI's list-then-drill-down pattern would."""
    return {
        "instanceId": instance.instance_id,
        "workflowDefId": instance.workflow_def_id,
        "currentState": instance.current_state,
        "requesterUpn": instance.requester_upn,
        "createdAt": instance.created_at,
        "updatedAt": instance.updated_at,
    }


def build_my_requests_response(instances: List[WorkflowInstance], requester_upn: str) -> Dict[str, Any]:
    return {
        "requesterUpn": requester_upn,
        "count": len(instances),
        "instances": [build_instance_summary(i) for i in instances],
    }


def build_my_approvals_response(instances: List[WorkflowInstance], role: str) -> Dict[str, Any]:
    return {
        "role": role,
        "count": len(instances),
        "instances": [build_instance_summary(i) for i in instances],
    }
