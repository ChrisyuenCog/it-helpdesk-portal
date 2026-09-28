"""
IT Helpdesk Portal — Workflow Instance View API request/response logic (HD-027)
=================================================================================
Pure response-building logic for GET /api/workflow/instance/{instanceId},
separated from the Azure Functions HTTP trigger in function_app.py, following
the exact same pattern as workflow_api.py (HD-017) and workflow_action_api.py
(HD-018) so this ticket can also be offline-tested without a live Durable
Functions host.

Scope note: the MVP Build Backlog's acceptance criterion for HD-027 asks for
"currentState, sla_clock fields, and the full approval_chain array". As of
this revision, HD-007 has added WorkflowStore.get_sla_clock() to the store
interface (both InMemoryWorkflowStore and SqlWorkflowStore implement it),
so this module now calls it directly. The accessor is still probed via
getattr rather than a hard type-checked call, purely so this module keeps
degrading gracefully if ever pointed at some future third store
implementation that hasn't added sla_clock support yet — not because the
two current stores are missing it.
"""
from __future__ import annotations

import json
from typing import Optional, Dict, Any, List

from workflow_store import WorkflowStore, WorkflowInstance, WorkflowStoreError
from workflow_api import build_error_response  # reused for a single, consistent error shape


class InstanceNotFoundError(Exception):
    """Raised when instanceId does not refer to a known workflow_instance —
    maps to HTTP 404 in function_app.py. Kept as its own exception (rather
    than reusing WorkflowStoreError directly) so the HTTP trigger's except
    clause reads the same way as the other two endpoints' 404/400 mapping,
    without needing to inspect the WorkflowStoreError message string."""
    pass


def parse_instance_id(route_param: Optional[str]) -> str:
    """Validates the {instanceId} route parameter itself is present. Does
    not check whether it refers to a real instance — that is a separate,
    subsequent step (see load_instance_view below), matching the same
    'each distinct failure reason maps to its own error' principle used in
    workflow_action_api.py."""
    if not route_param or not isinstance(route_param, str):
        raise InstanceNotFoundError("instanceId path parameter is required.")
    return route_param


def _get_sla_view(store: WorkflowStore, instance_id: str) -> Dict[str, Any]:
    """Returns the sla_clock view for an instance. HD-007 added
    get_sla_clock() to both current store implementations; the getattr
    probe here is defensive graceful-degradation for any future third
    store, not a workaround for a known gap (see module docstring)."""
    accessor = getattr(store, "get_sla_clock", None)
    if accessor is None:
        return {"available": False, "reason": "sla_clock accessor not implemented on this WorkflowStore."}
    try:
        sla = accessor(instance_id)
    except Exception:
        return {"available": False, "reason": "sla_clock lookup failed."}
    if sla is None:
        return {"available": False, "reason": "No sla_clock row exists for this instance."}
    return {
        "available": True,
        "targetResponseAt": sla.target_response_at,
        "targetResolutionAt": sla.target_resolution_at,
        "breached": sla.breached_flag,
    }


def load_instance_view(store: WorkflowStore, instance_id: str) -> Dict[str, Any]:
    """The single entry point this ticket's HTTP trigger calls. Loads the
    instance, its approval_chain, and (if available) its sla_clock view,
    and assembles them into the HD-027 response shape. Raises
    InstanceNotFoundError (-> 404) if instanceId is unknown; any other
    WorkflowStoreError is left to propagate as-is, matching HD-018's
    precedent of surfacing unexpected store errors rather than masking
    them behind a misleading 404."""
    try:
        instance: WorkflowInstance = store.get_instance(instance_id)
    except WorkflowStoreError as e:
        raise InstanceNotFoundError(str(e))

    approval_chain: List[Any] = store.get_approval_chain(instance_id)

    return {
        "instanceId": instance.instance_id,
        "workflowDefId": instance.workflow_def_id,
        "currentState": instance.current_state,
        "createdAt": instance.created_at,
        "updatedAt": instance.updated_at,
        "history": instance.history,
        "approvalChain": [
            {
                "stepOrder": entry.step_order,
                "approverUpn": entry.approver_upn,
                "status": entry.status,
                "actionedAt": entry.actioned_at,
            }
            for entry in approval_chain
        ],
        "sla": _get_sla_view(store, instance_id),
    }
