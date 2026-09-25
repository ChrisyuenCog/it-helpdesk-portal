"""
IT Helpdesk Portal â€” Function App Entry Point
================================================
HD-015: Generic Durable Functions orchestrator skeleton.
HD-016: TEST workflow_definition seeded in workflow_store.py, proven here.

Design principle (per MVP Specification, Section 3.3): ONE orchestrator
drives every workflow type. This file contains zero references to
"Hardware", "Tender", or "Incident" â€” those categories are added in later
tickets purely as new rows in the workflow_store, never as new orchestrator
code. If you find yourself wanting to add an `if workflow_def_id ==
"HARDWARE_REQUEST"` branch anywhere below, that is a sign the pattern is
being violated and the fix belongs in workflow_store.py's transition data,
not here.
"""
import json
import logging
import azure.functions as func
import azure.durable_functions as df

from workflow_store import get_store, WorkflowStoreError

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


# ---------------------------------------------------------------------------
# HTTP Starter (smoke-test scope for HD-015/016 only)
# ---------------------------------------------------------------------------
# NOTE: this is a minimal starter sufficient to prove the orchestrator
# pattern for this ticket. The full-featured, role-validated
# POST /api/workflow/start (HD-017) and POST /api/workflow/action (HD-018)
# supersede this in the next tickets â€” they add caller-role validation,
# the 400-on-invalid-workflowDefId behaviour, and human-approval waiting
# via external events. This starter deliberately does none of that; it
# only proves that starting an orchestration against a workflow_def_id
# correctly walks the seeded TEST definition end to end.
@app.route(route="workflow/smoketest/start", methods=["POST"])
@app.durable_client_input(client_name="client")
async def smoketest_start(req: func.HttpRequest, client) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    workflow_def_id = body.get("workflowDefId", "TEST")

    instance_id = await client.start_new(
        "generic_workflow_orchestrator",
        client_input={"workflowDefId": workflow_def_id},
    )
    logging.info(f"Started orchestration '{instance_id}' for workflowDefId={workflow_def_id}")

    return client.create_check_status_response(req, instance_id)


# ---------------------------------------------------------------------------
# Generic Orchestrator (HD-015 â€” the actual deliverable of this ticket)
# ---------------------------------------------------------------------------
@app.orchestration_trigger(context_name="context")
def generic_workflow_orchestrator(context: df.DurableOrchestrationContext):
    """
    Reads a workflow_definition by ID and walks its states end to end.

    For HD-015/016, "walking the states" means auto-advancing through every
    transition defined for the definition (since there is no human approval
    step yet â€” that arrives with HD-018's action-waiting logic). This is
    sufficient to satisfy this ticket's acceptance criterion: "transitions
    through at least two dummy states without hardcoding any
    category-specific logic."

    Every piece of information this function needs (which states exist,
    which transitions are legal, which action to fire) comes from the
    workflow_definition read via an activity function â€” never from an
    if/elif chain keyed on workflow_def_id.
    """
    input_data = context.get_input()
    workflow_def_id = input_data["workflowDefId"]

    # Step 1: create the instance (activity function â€” deterministic replay safe)
    instance_id = yield context.call_activity("create_workflow_instance", workflow_def_id)

    transitions_taken = []

    # Step 2: repeatedly ask "what does the definition say happens next?"
    # and apply it, until the definition itself says we've reached a
    # terminal state. No workflow-specific logic appears here at all.
    while True:
        step_result = yield context.call_activity("advance_workflow_instance", instance_id)

        if step_result["error"]:
            # Defined transition ran out â€” nothing more to auto-advance.
            # (Real workflows with human approval will instead pause here
            # and await_external_event in HD-018; this ticket's TEST
            # definition has no approval steps, so this simply means done.)
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
# Activity Functions â€” the only place that touches the WorkflowStore
# ---------------------------------------------------------------------------
@app.activity_trigger(input_name="workflowDefId")
def create_workflow_instance(workflowDefId: str) -> str:
    """Creates a new workflow_instance for the given definition and
    returns its instance_id. Raises (surfacing as an orchestrator failure)
    if the workflowDefId does not exist â€” this is intentional: an
    orchestration should never silently proceed against an unknown
    definition."""
    store = get_store()
    instance = store.create_instance(workflowDefId)
    logging.info(f"Created workflow_instance {instance.instance_id} "
                 f"(def={workflowDefId}, state={instance.current_state})")
    return instance.instance_id


@app.activity_trigger(input_name="instanceId")
def advance_workflow_instance(instanceId: str) -> dict:
    """Applies the next available transition for this instance's current
    state, per its workflow_definition. Returns a small result dict rather
    than raising, so the orchestrator can decide whether to keep looping
    without treating 'no more transitions' as an error condition."""
    store = get_store()
    try:
        instance = store.get_instance(instanceId)
        definition = store.get_definition(instance.workflow_def_id)
    except WorkflowStoreError as e:
        return {"error": str(e), "transition": None, "is_terminal": True}

    if definition.is_terminal(instance.current_state):
        return {"error": None, "transition": None, "is_terminal": True}

    # For this generic skeleton, "advance" is the only action fired
    # automatically. Category-specific workflows (Hardware, Tender,
    # Incident) will instead be driven by explicit actions submitted via
    # POST /api/workflow/action (HD-018), validated against the caller's
    # role â€” that logic lives in that ticket, not here.
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
# Health check (reused pattern from the DevOps agent Function App)
# ---------------------------------------------------------------------------
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-015/HD-016"}),
        mimetype="application/json",
        status_code=200,
    )