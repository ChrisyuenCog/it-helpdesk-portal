"""
IT Helpdesk Portal — Function App Entry Point
================================================
HD-015: Generic Durable Functions orchestrator skeleton.
HD-016: TEST workflow_definition seeded.
HD-002/003/005/006/008: durable Azure SQL-backed storage (ci_base,
    workflow_definition, workflow_instance, approval_chain), with safe
    in-memory fallback.
HD-017: POST /api/workflow/start.
HD-018 (this revision): POST /api/workflow/action — the endpoint that
    lets a human decision (approve/reject/etc.) progress a workflow
    instance, with role-gated 400/403 handling and approval_chain logging.

*** Scope note carried from workflow_action_api.py — repeated here because
it matters at the point where the route is wired up, not just buried in a
helper module: 'callerRole' is accepted directly in the request body for
MVP demonstration purposes. It is NOT yet backed by validated Entra ID
token claims. Treat POST /api/workflow/action as functionally correct but
NOT YET a real access-control boundary until Sprint 4's Security Hardening
work (HD-066 and related) wires this to genuine identity. ***

Design principle (per MVP Specification, Section 3.3): ONE orchestrator
drives every workflow type. This file contains zero references to
"Hardware", "Tender", or "Incident" — those categories are added in later
tickets purely as new rows in the workflow_store, never as new orchestrator
code.

HD-018 architectural note on why /api/workflow/action does NOT touch
Durable Functions at all: the generic orchestrator's auto-advance loop only
ever attempts action='advance' transitions (see
generic_workflow_orchestrator below) — it has no concept of waiting for a
human decision. For TEST_APPROVAL (this ticket's new role-gated seed
definition), the orchestration therefore completes immediately after
instance creation, having taken zero transitions, once it finds no
'advance' action available from the initial state. The workflow_instance
row in the store remains the single source of truth for state from that
point forward, and POST /api/workflow/action operates directly against the
store — independent of the (already-completed) orchestration's lifecycle.
Building true event-driven waiting (Durable Functions'
wait_for_external_event, the "Human Interaction" pattern referenced in the
original architecture rethink) is deferred to a later maturity ticket; it
is not required to satisfy HD-018's stated acceptance criteria, and adding
it now would be scope creep against an MVP ticket.
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
from workflow_action_api import (
    parse_action_request,
    resolve_transition,
    check_role_permission,
    determine_approval_status,
    build_action_success_response,
    ActionRequestValidationError,
    ActionNotAllowedError,
    RoleNotPermittedError,
)

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


# ---------------------------------------------------------------------------
# HD-017: POST /api/workflow/start (generic, any workflowDefId)
# ---------------------------------------------------------------------------
@app.route(route="workflow/start", methods=["POST"])
@app.durable_client_input(client_name="client")
async def workflow_start(req: func.HttpRequest, client) -> func.HttpResponse:
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

    try:
        instance = store.create_instance(workflow_def_id)
    except WorkflowStoreError as e:
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
# HD-018: POST /api/workflow/action
# ---------------------------------------------------------------------------
@app.route(route="workflow/action", methods=["POST"])
def workflow_action(req: func.HttpRequest) -> func.HttpResponse:
    """
    Request body: {
        "instanceId": "...",
        "action": "approve" | "reject" | "submit" | ...,
        "callerRole": "Approver" (optional — see MVP scope note at top of file),
        "callerUpn": "manager@..." (optional, recorded on the approval_chain entry)
    }

    HTTP status mapping:
    - 400: malformed request body, OR the action is not valid from the
      instance's current state (including an already-terminal instance)
    - 403: the transition requires a role the caller did not supply /
      match (HD-018's core acceptance criterion)
    - 404: instanceId does not refer to a known workflow_instance
    - 200: transition applied successfully

    Note this is a plain HTTP-triggered function, NOT wired to the Durable
    Functions client — see this file's module docstring for why this
    ticket's design does not require touching orchestration state at all.
    """
    try:
        parsed = parse_action_request(req.get_body())
    except ActionRequestValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )

    store = get_store()

    try:
        instance = store.get_instance(parsed["instanceId"])
    except WorkflowStoreError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=404,
        )

    try:
        definition = store.get_definition(instance.workflow_def_id)
    except WorkflowStoreError as e:
        # An instance referencing a now-missing definition is a data
        # integrity problem, not a caller error — surface as 500 and log
        # loudly rather than silently mapping it to a 4xx.
        logging.error(
            f"HD-018: instance {instance.instance_id} references unknown "
            f"workflowDefId '{instance.workflow_def_id}': {e}"
        )
        return func.HttpResponse(
            json.dumps(build_error_response("Internal data integrity error.")),
            mimetype="application/json",
            status_code=500,
        )

    try:
        transition = resolve_transition(definition, instance, parsed["action"])
    except ActionNotAllowedError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )

    try:
        check_role_permission(transition, parsed["callerRole"])
    except RoleNotPermittedError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=403,
        )

    from_state = instance.current_state
    to_state = transition["to"]
    instance.record_transition(from_state, to_state, parsed["action"])
    store.save_instance(instance)

    approval_entry = None
    if transition.get("requiredRole"):
        status = determine_approval_status(parsed["action"])
        approval_entry = store.append_approval_entry(
            instance.instance_id, parsed["callerUpn"], status
        )

    logging.info(
        f"HD-018: instance {instance.instance_id} action='{parsed['action']}' "
        f"{from_state} -> {to_state}"
        + (f", approval_chain entry recorded (status={approval_entry.status})" if approval_entry else "")
    )

    response_body = build_action_success_response(instance, transition, approval_entry)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Generic Orchestrator (HD-015, updated HD-017)
# ---------------------------------------------------------------------------
@app.orchestration_trigger(context_name="context")
def generic_workflow_orchestrator(context: df.DurableOrchestrationContext):
    """
    Walks a workflow_definition's states end to end using only data read
    via activity functions — never category-specific logic. Only ever
    auto-advances 'advance'-action transitions; role-gated transitions
    (like TEST_APPROVAL's approve/reject) are left for POST
    /api/workflow/action to apply directly against the store (see this
    file's module docstring for the full explanation).
    """
    input_data = context.get_input()
    workflow_def_id = input_data["workflowDefId"]
    existing_instance_id = input_data.get("existingInstanceId")

    if existing_instance_id:
        instance_id = existing_instance_id
    else:
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
    store = get_store()
    instance = store.create_instance(workflowDefId)
    logging.info(f"Created workflow_instance {instance.instance_id} "
                 f"(def={workflowDefId}, state={instance.current_state})")
    return instance.instance_id


@app.activity_trigger(input_name="instanceId")
def advance_workflow_instance(instanceId: str) -> dict:
    """Applies the next available 'advance'-action transition for this
    instance's current state, if one exists. Role-gated actions (approve/
    reject/etc.) are never attempted here — only POST /api/workflow/action
    applies those, by design (see module docstring)."""
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
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-018"}),
        mimetype="application/json",
        status_code=200,
    )