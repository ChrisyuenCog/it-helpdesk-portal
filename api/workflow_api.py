"""
IT Helpdesk Portal — Workflow API request/response logic (HD-017)
====================================================================
Pure request-validation and response-building logic for
POST /api/workflow/start, deliberately separated from the actual Azure
Functions HTTP trigger in function_app.py so it can be offline-tested
without needing a live Durable Functions host (same pattern already used
for workflow_store.py and sql_workflow_store.py in this codebase).

Design decision: workflowDefId validity is checked SYNCHRONOUSLY, against
the WorkflowStore, BEFORE any Durable Functions orchestration is started.
This is what makes the 400-on-invalid-workflowDefId acceptance criterion
clean — an orchestration that failed asynchronously would otherwise leave
the HTTP caller with a 202 Accepted and no easy way to learn it failed.
Failing fast, synchronously, for bad input avoids that entirely.
"""
from __future__ import annotations
import json
from typing import Optional, Dict, Any, Tuple

from workflow_store import WorkflowStore, WorkflowStoreError


class StartRequestValidationError(Exception):
    """Raised for any problem with the incoming request body itself
    (missing/malformed fields), as distinct from an unknown workflowDefId
    (which is a business-logic 400, handled separately so the two failure
    modes can return distinguishable error messages)."""
    pass


def parse_start_request(raw_body: Optional[bytes]) -> Dict[str, Any]:
    """Parses and minimally validates the JSON body shape. Raises
    StartRequestValidationError with a caller-facing message on any
    problem. Does NOT check whether workflowDefId actually exists —
    that is a separate, subsequent step (see validate_workflow_def_id)
    so the two distinct failure reasons ('bad request shape' vs 'unknown
    workflow type') are never conflated into one generic error."""
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
        # requesterUpn is optional at this ticket's scope — HD-018 and the
        # role-validation work will make fuller use of caller identity.
        # Accepted here, passed through, but not yet required or validated.
        "requesterUpn": body.get("requesterUpn"),
    }


def validate_workflow_def_id(store: WorkflowStore, workflow_def_id: str) -> None:
    """Raises WorkflowStoreError (already defined in workflow_store.py) if
    workflow_def_id does not exist. Re-raising the store's own exception
    type (rather than wrapping it) keeps this a single, consistent error
    type for 'unknown workflow definition' across the whole codebase."""
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