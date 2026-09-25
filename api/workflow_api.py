"""
IT Helpdesk Portal — Workflow API request/response logic (HD-017)
====================================================================
[Unchanged from the merged HD-017 PR. Included in this delivery only
because workflow_action_api.py imports build_error_response from it, to
keep a single, consistent error response shape across both endpoints.]
"""
from __future__ import annotations
import json
from typing import Optional, Dict, Any, Tuple

from workflow_store import WorkflowStore, WorkflowStoreError


class StartRequestValidationError(Exception):
    pass


def parse_start_request(raw_body: Optional[bytes]) -> Dict[str, Any]:
    if not raw_body:
        raise StartRequestValidationError("Request body is required and must be JSON.")

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise StartRequestValidationError(f"Request body must be valid JSON: {e}")

    if not isinstance(body, dict):
        raise StartRequestValidationError("Request body must be a JSON object.")

    workflow_def_id = body.get("workflowDefId")
    if not workflow_def_id or not isinstance(workflow_def_id, str):
        raise StartRequestValidationError("'workflowDefId' is required and must be a non-empty string.")

    return {
        "workflowDefId": workflow_def_id,
        "requesterUpn": body.get("requesterUpn"),
    }


def validate_workflow_def_id(store: WorkflowStore, workflow_def_id: str) -> None:
    store.get_definition(workflow_def_id)  # raises WorkflowStoreError if unknown


def build_start_success_response(instance_id: str, workflow_def_id: str, initial_state: str) -> Dict[str, Any]:
    return {
        "status": "started",
        "instanceId": instance_id,
        "workflowDefId": workflow_def_id,
        "currentState": initial_state,
    }


def build_error_response(message: str) -> Dict[str, Any]:
    return {"status": "error", "message": message}