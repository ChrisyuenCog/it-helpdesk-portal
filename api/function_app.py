
"""
IT Helpdesk Portal — Function App Entry Point
================================================
HD-015: Generic Durable Functions orchestrator skeleton.
HD-016: TEST workflow_definition seeded.
HD-017: POST /api/workflow/start.
HD-018: POST /api/workflow/action.
HD-027: GET /api/workflow/instance/{instanceId}.
HD-028/029:
  - workflow_start now captures the caller-supplied 'requesterUpn' from
    the request body (already parsed by workflow_api.parse_start_request,
    but previously discarded — never passed to store.create_instance())
    and threads it through so instances are attributable to a requester.
  - GET /api/workflow/myRequests — a Requester's own submitted requests
    across every category, via ?requesterUpn=.
  - GET /api/workflow/myApprovals — every instance currently awaiting a
    given role's decision, across every category, via ?role=.
  Both new routes are thin HTTP triggers delegating to workflow_list_api.py,
  the same "logic lives in its own module" pattern as every prior ticket.
HD-019/020/021 (this revision) — CMDB read endpoints, Batch A:
  - GET /api/cmdb/ci/{ciId} — fetch any CI by ID, regardless of class.
  - GET /api/cmdb/ci?class=&owner= — powers My Devices; owner filtering is
    resolved via ci_relationship 'user has' edges, not a plain ci_base.owner
    match (see cmdb_store.py's module docstring for the full rationale).
  - GET /api/cmdb/relationships?ciId= — traverse relationships for a CI in
    either direction (fromCiId or toCiId).
  All three are thin HTTP triggers delegating to cmdb_api.py, the same
  "logic lives in its own module, HTTP trigger is just plumbing" pattern
  used by every workflow endpoint above. This file still contains zero
  references to "Hardware", "Tender", or "Incident" — CMDB reads are
  generic across every CI class, exactly like the workflow orchestrator is
  generic across every workflow category.
*** Scope note carried from workflow_action_api.py / workflow_list_api.py —
repeated here because it matters at the point where routes are wired up:
'callerRole' (HD-018) and 'requesterUpn'/'role' (HD-028/029) are all
accepted directly from the caller (request body or query string) for MVP
demonstration purposes. None are yet backed by validated Entra ID token
claims. The same applies to HD-019/020/021's CMDB reads — there is no
Row-Level Security yet (that is HD-066, Sprint 4). Treat these endpoints as
functionally correct but NOT YET a real access-control boundary until
Sprint 4's Security Hardening work wires them to genuine identity. ***
Design principle (per MVP Specification, Section 3.3): ONE orchestrator
drives every workflow type. This file contains zero references to
"Hardware", "Tender", or "Incident" — those categories are added purely as
new rows in the workflow_store, never as new orchestrator code.
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
from workflow_instance_api import (
    parse_instance_id,
    load_instance_view,
    InstanceNotFoundError,
)
from workflow_list_api import (
    parse_my_requests_query,
    parse_my_approvals_query,
    build_my_requests_response,
    build_my_approvals_response,
    MyRequestsValidationError,
    MyApprovalsValidationError,
)
from cmdb_store import get_cmdb_store
from cmdb_api import (
    parse_ci_id,
    load_ci_view,
    parse_list_ci_query,
    build_ci_list_response,
    parse_relationships_query,
    build_relationships_response,
    CiNotFoundError,
    RelationshipsValidationError,
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
    requester_upn = parsed.get("requesterUpn")  # HD-028: now actually used, not discarded
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
        instance = store.create_instance(workflow_def_id, requester_upn=requester_upn)
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
        f"workflowDefId={workflow_def_id}, workflow_instance={instance.instance_id}, "
        f"requesterUpn={requester_upn}"
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
# HD-027: GET /api/workflow/instance/{instanceId}
# ---------------------------------------------------------------------------
@app.route(route="workflow/instance/{instanceId}", methods=["GET"])
def workflow_get_instance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        instance_id = parse_instance_id(req.route_params.get("instanceId"))
    except InstanceNotFoundError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=404,
        )
    store = get_store()
    try:
        view = load_instance_view(store, instance_id)
    except InstanceNotFoundError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=404,
        )
    return func.HttpResponse(
        json.dumps(view),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-028: GET /api/workflow/myRequests?requesterUpn=
# ---------------------------------------------------------------------------
@app.route(route="workflow/myRequests", methods=["GET"])
def workflow_my_requests(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?requesterUpn=chris.yuen@cognitionlearninggroup.com
    HTTP status mapping:
    - 400: 'requesterUpn' query parameter missing or empty
    - 200: returns { requesterUpn, count, instances: [...] }, possibly
      an empty instances list if this requester has never started one
    See this file's module docstring and workflow_list_api.py's for the
    MVP identity scope note — requesterUpn is caller-supplied, not yet
    validated against a real signed-in identity.
    """
    try:
        requester_upn = parse_my_requests_query(dict(req.params))
    except MyRequestsValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    store = get_store()
    instances = store.get_instances_by_requester(requester_upn)
    response_body = build_my_requests_response(instances, requester_upn)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-029: GET /api/workflow/myApprovals?role=
# ---------------------------------------------------------------------------
@app.route(route="workflow/myApprovals", methods=["GET"])
def workflow_my_approvals(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?role=Approver (or ITAgent, ITAdmin, etc. — any value
    that appears as a 'requiredRole' on some workflow_definition's
    transitions)
    HTTP status mapping:
    - 400: 'role' query parameter missing or empty
    - 200: returns { role, count, instances: [...] } — every non-terminal
      instance whose current state has an outgoing transition requiring
      this role, across every workflow category
    See workflow_store.py's module docstring for why this is implemented
    as a derived query rather than reading stored 'Pending' approval_chain
    rows (this MVP's approval_chain rows are only ever written after a
    decision is actioned, never before).
    """
    try:
        role = parse_my_approvals_query(dict(req.params))
    except MyApprovalsValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    store = get_store()
    instances = store.get_instances_pending_role(role)
    response_body = build_my_approvals_response(instances, role)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-019: GET /api/cmdb/ci/{ciId}
# ---------------------------------------------------------------------------
@app.route(route="cmdb/ci/{ciId}", methods=["GET"])
def cmdb_get_ci(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP status mapping:
    - 404: ciId path parameter missing, or does not refer to a known CI
    - 200: returns the CI's current fields (ciId, ciClass, name, status,
      owner, entity, createdAt)
    See cmdb_store.py's module docstring for the MVP scope note on why
    ValidFrom/ValidTo system-time columns are not part of this response.
    """
    store = get_cmdb_store()
    try:
        ci_id = parse_ci_id(req.route_params.get("ciId"))
        view = load_ci_view(store, ci_id)
    except CiNotFoundError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=404,
        )
    return func.HttpResponse(
        json.dumps(view),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-020: GET /api/cmdb/ci?class=&owner=
# ---------------------------------------------------------------------------
@app.route(route="cmdb/ci", methods=["GET"])
def cmdb_list_ci(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?class=Hardware&owner=chris.yuen@cognitionlearninggroup.com
    Both filters are optional; omitting both returns every CI. When 'owner'
    is supplied, results are restricted to CIs reachable via a 'user has'
    ci_relationship from that owner's UPN — see cmdb_store.py's module
    docstring for the full rationale (this is what powers My Devices).
    HTTP status mapping:
    - 200: returns { class, owner, count, items: [...] }, possibly an
      empty items list if no CI matches the supplied filters
    """
    store = get_cmdb_store()
    filters = parse_list_ci_query(dict(req.params))
    cis = store.list_ci(ci_class=filters["ci_class"], owner=filters["owner"])
    response_body = build_ci_list_response(cis, filters["ci_class"], filters["owner"])
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-021: GET /api/cmdb/relationships?ciId=
# ---------------------------------------------------------------------------
@app.route(route="cmdb/relationships", methods=["GET"])
def cmdb_get_relationships(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?ciId=<a known ciId>
    Direction-agnostic: returns every relationship where the supplied ciId
    appears as EITHER fromCiId OR toCiId, so querying either a User CI or
    a Hardware CI returns the same 'user has' row.
    HTTP status mapping:
    - 400: 'ciId' query parameter missing or empty
    - 200: returns { ciId, count, relationships: [...] }, possibly an
      empty relationships list if this CI has none
    """
    try:
        ci_id = parse_relationships_query(dict(req.params))
    except RelationshipsValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    store = get_cmdb_store()
    relationships = store.get_relationships_for_ci(ci_id)
    response_body = build_relationships_response(relationships, ci_id)
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
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-019-020-021"}),
        mimetype="application/json",
        status_code=200,
    )
