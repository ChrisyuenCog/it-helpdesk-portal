"""
IT Helpdesk Portal — Function App Entry Point
================================================
HD-015: Generic Durable Functions orchestrator skeleton.
HD-016: TEST workflow_definition seeded (see workflow_store.py / sql/schema.sql).
HD-002/003/005/006: durable Azure SQL-backed storage, with safe in-memory fallback.
HD-017: POST /api/workflow/start — the first real, externally-callable API
         endpoint. Supersedes the HD-015 smoke-test starter
         (workflow/smoketest/start), which is now removed.

Design principle (per MVP Specification, Section 3.3): ONE orchestrator
drives every workflow type. This file contains zero references to
"Hardware", "Tender", or "Incident" — those categories are added in later
tickets purely as new rows in the workflow_store, never as new orchestrator
code.
"""
import json
import logging
import azure.functions as func
import azure.durable_functions as df

from workflow_store import get_store, WorkflowStoreError
from workflow_api import (
    parse_start_request,
    validate_workflow_def_id,
    build_start_success_response,
    build_error_response,
    StartRequestValidationError,
)

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


# ---------------------------------------------------------------------------
# HD-017: POST /api/workflow/start (generic, any workflowDefId)
# ---------------------------------------------------------------------------
@app.route(route="workflow/start", methods=["POST"])
@app.durable_client_input(client_name="client")
async def workflow_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    Request body: { "workflowDefId": "TEST", "requesterUpn": "user@... " (optional) }

    Acceptance criteria (HD-017):
    - Calling with a valid workflowDefId creates a workflow_instance in the
      correct starting state.
    - An invalid workflowDefId returns 400.

    Design note: workflowDefId is validated SYNCHRONOUSLY against the store
    before any Durable Functions orchestration starts (see workflow_api.py's
    module docstring for why). This means a 400 response never involves an
    orchestration at all — nothing is left half-started on bad input.
    """
    try:
        parsed = parse_start_request(req.get_body())
    except StartRequestValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )

    workflow_def_id = parsed["workflowDefId"]
    store = get_store()

    try:
        validate_workflow_def_id(store, workflow_def_id)
    except WorkflowStoreError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )

    # Validation passed — now, and only now, create the instance and start
    # the orchestration. create_instance() itself also re-validates against
    # the store (see workflow_store.py), which is intentionally redundant
    # with the check above: defence in depth against a definition being
    # deleted in the split second between the two calls, however unlikely.
    try:
        instance = store.create_instance(workflow_def_id)
    except WorkflowStoreError as e:
        # Extremely unlikely given the check above, but never silently
        # swallow a store error — surface it as a 400 for consistency.
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )

    orchestration_instance_id = await client.start_new(
        "generic_workflow_orchestrator",
        instance_id=instance.instance_id,
        client_input={"workflowDefId": workflow_def_id, "existingInstanceId": instance.instance_id},
    )
    logging.info(
        f"HD-017: started orchestration '{orchestration_instance_id}' for "
        f"workflowDefId={workflow_def_id}, workflow_instance={instance.instance_id}"
    )

    response_body = build_start_success_response(
        instance_id=instance.instance_id,
        workflow_def_id=workflow_def_id,
        initial_state=instance.current_state,
    )
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=201,
    )


# ---------------------------------------------------------------------------
# Generic Orchestrator (HD-015)
# ---------------------------------------------------------------------------
@app.orchestration_trigger(context_name="context")
def generic_workflow_orchestrator(context: df.DurableOrchestrationContext):
    """
    Walks a workflow_definition's states end to end, using only data read
    via activity functions — never category-specific logic.

    HD-017 update: the orchestrator now accepts an OPTIONAL
    'existingInstanceId' in its input. When present (as HD-017's
    workflow_start endpoint always supplies), the orchestrator operates on
    the workflow_instance already created by the HTTP trigger, rather than
    creating a second, duplicate one itself. This avoids the HD-015-era
    behaviour of the orchestrator creating its own instance internally,
    which would have produced two competing workflow_instance rows for a
    single logical request once a real HTTP caller was involved.
    """
    input_data = context.get_input()
    workflow_def_id = input_data["workflowDefId"]
    existing_instance_id = input_data.get("existingInstanceId")

    if existing_instance_id:
        instance_id = existing_instance_id
    else:
        # Preserved for backward compatibility with any direct internal
        # callers that don't pre-create an instance (none remain in this
        # codebase after HD-017, but this keeps the orchestrator
        # independently usable/testable without the HTTP layer).
        instance_id = yield context.call_activity("create_workflow_instance", workflow_def_id)

    transitions_taken = []

    while True:
        step_result = yield context.call_activity("advance_workflow_instance", instance_id)

        if step_result["error"]:
            break

        transitions_taken.append(step_result["transition"])

        if step_result["is_terminal"]:
            break

    return {
        "instanceId": instance_id,
        "workflowDefId": workflow_def_id,
        "transitionsTaken": transitions_taken,
        "finalState": transitions_taken[-1]["to"] if transitions_taken else None,
    }


# ---------------------------------------------------------------------------
# Activity Functions — the only place that touches the WorkflowStore
# ---------------------------------------------------------------------------
@app.activity_trigger(input_name="workflowDefId")
def create_workflow_instance(workflowDefId: str) -> str:
    """Creates a new workflow_instance for the given definition and
    returns its instance_id. Retained for orchestrations that don't
    pre-create an instance via the HTTP layer (see docstring above)."""
    store = get_store()
    instance = store.create_instance(workflowDefId)
    logging.info(f"Created workflow_instance {instance.instance_id} "
                 f"(def={workflowDefId}, state={instance.current_state})")
    return instance.instance_id


@app.activity_trigger(input_name="instanceId")
def advance_workflow_instance(instanceId: str) -> dict:
    """Applies the next available transition for this instance's current
    state, per its workflow_definition."""
    store = get_store()
    try:
        instance = store.get_instance(instanceId)
        definition = store.get_definition(instance.workflow_def_id)
    except WorkflowStoreError as e:
        return {"error": str(e), "transition": None, "is_terminal": True}

    if definition.is_terminal(instance.current_state):
        return {"error": None, "transition": None, "is_terminal": True}

    next_state = definition.next_state(instance.current_state, action="advance")

    if next_state is None:
        return {"error": "No transition defined", "transition": None, "is_terminal": True}

    from_state = instance.current_state
    instance.record_transition(from_state, next_state, action="advance")
    store.save_instance(instance)

    logging.info(f"Instance {instanceId}: {from_state} -> {next_state}")

    return {
        "error": None,
        "transition": {"from": from_state, "to": next_state, "action": "advance"},
        "is_terminal": definition.is_terminal(next_state),
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-017"}),
        mimetype="application/json",
        status_code=200,
    )