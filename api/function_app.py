
"""
IT Helpdesk Portal — Function App Entry Point
================================================
HD-015: Generic Durable Functions orchestrator skeleton.
HD-016: TEST workflow_definition seeded.
HD-017: POST /api/workflow/start.
HD-018: POST /api/workflow/action.
HD-027: GET /api/workflow/instance/{instanceId}.
HD-028/029: GET /api/workflow/myRequests, GET /api/workflow/myApprovals.
HD-019/020/021: GET /api/cmdb/ci/{ciId}, GET /api/cmdb/ci?class=&owner=,
  GET /api/cmdb/relationships?ciId=.
HD-026/030/033/034: HARDWARE_REQUEST backend — requiredFields hard gate,
  dynamic approver resolution, generic onEnterEffects (createCi).
HD-040 (this revision) — GET /api/identity/authMethods?upn=:
  Thin HTTP trigger delegating to identity_api.py (request parsing/response
  shaping) and graph_api.py (the actual Graph call, HD-030's sibling
  function). Same "logic lives in its own module, HTTP trigger is just
  plumbing" pattern as every route above. HD-039 (SSPR tile) and HD-041
  (wizard UI) are frontend-only tickets built on top of this endpoint — see
  web/index.html — and require no further backend changes.
HD-045/046 (this revision) — Knowledge Base:
  - GET /api/kb/search?query= — simple case-insensitive keyword match
    against article title/body, delegating to kb_api.py + kb_store.py.
    An unmatched query is a valid 200 with an empty results list, not an
    error (HD-045's core acceptance criterion).
  - POST /api/kb/feedback — records a Yes/No "was this helpful" response
    against an article. Always inserts a NEW row, even for a repeated
    submission from the same session — see kb_store.py's module docstring
    for why this is deliberately append-only, not an upsert. HD-047's
    search + feedback UI is frontend-only, built on top of these two
    endpoints — see web/index.html.
*** Scope note carried from every prior module's docstring — repeated here
because it matters at the point where routes are wired up: 'callerRole'
(HD-018), 'requesterUpn'/'role' (HD-028/029), CMDB reads (HD-019/020/021),
and now 'upn' (HD-040) are all unauthenticated/caller-supplied for MVP
demonstration purposes; Graph-based manager resolution (HD-030) and
Graph-based auth-methods lookup (HD-040) are similarly best-effort until
HD-012's Entra App Registration ships. None of this is yet a real
access-control or identity boundary — that is Sprint 4's Security
Hardening epic (HD-066). ***
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
    check_required_fields,
    resolve_expected_approver,
    determine_approval_status,
    build_action_success_response,
    ActionRequestValidationError,
    ActionNotAllowedError,
    RoleNotPermittedError,
    MissingRequiredFieldError,
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
from workflow_effects_api import apply_enter_effects
from identity_api import (
    parse_auth_methods_query,
    build_auth_methods_response,
    AuthMethodsValidationError,
)
from graph_api import get_auth_methods
from kb_store import get_kb_store
from kb_api import (
    parse_search_query,
    build_search_response,
    parse_feedback_request,
    submit_feedback,
    build_feedback_response,
    SearchValidationError,
    FeedbackRequestValidationError,
    ArticleNotFoundError,
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
    requester_upn = parsed.get("requesterUpn")
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
    try:
        check_required_fields(transition, parsed["fields"])
    except MissingRequiredFieldError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    from_state = instance.current_state
    to_state = transition["to"]
    expected_approver = resolve_expected_approver(transition, instance)
    instance.record_transition(
        from_state, to_state, parsed["action"],
        fields=parsed["fields"], expected_approver_upn=expected_approver,
    )
    store.save_instance(instance)
    approval_entry = None
    if transition.get("requiredRole"):
        status = determine_approval_status(parsed["action"])
        approval_entry = store.append_approval_entry(
            instance.instance_id, parsed["callerUpn"], status
        )
    cmdb_store = get_cmdb_store()
    effects = apply_enter_effects(cmdb_store, instance, transition)
    logging.info(
        f"HD-018: instance {instance.instance_id} action='{parsed['action']}' "
        f"{from_state} -> {to_state}"
        + (f", approval_chain entry recorded (status={approval_entry.status})" if approval_entry else "")
        + (f", expectedApprover={expected_approver}" if expected_approver else "")
        + (f", effects={effects}" if effects else "")
    )
    response_body = build_action_success_response(instance, transition, approval_entry, effects)
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
# HD-040: GET /api/identity/authMethods?upn=
# ---------------------------------------------------------------------------
@app.route(route="identity/authMethods", methods=["GET"])
def identity_get_auth_methods(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?upn=chris.yuen@cognitionlearninggroup.com
    HTTP status mapping:
    - 400: 'upn' query parameter missing or empty
    - 200: ALWAYS returned for a syntactically valid request — even when
      the underlying Graph call fails or HD-012 isn't provisioned yet, in
      which case the response body's 'available' key is False with a
      human-readable 'reason' (see identity_api.py's
      build_auth_methods_response docstring for why this is a 200, not a
      5xx: Graph unavailability is a normal, expected MVP-stage condition,
      not a caller error).
    """
    try:
        upn = parse_auth_methods_query(dict(req.params))
    except AuthMethodsValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    methods = get_auth_methods(upn)
    response_body = build_auth_methods_response(upn, methods)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-045: GET /api/kb/search?query=
# ---------------------------------------------------------------------------
@app.route(route="kb/search", methods=["GET"])
def kb_search(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query string: ?query=password
    HTTP status mapping:
    - 400: 'query' query parameter missing or empty
    - 200: returns { query, count, results: [...] }, possibly an empty
      results list if no article matches — per HD-045's core acceptance
      criterion, an unmatched query is a valid 200 response, not an error.
    """
    try:
        query = parse_search_query(dict(req.params))
    except SearchValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    store = get_kb_store()
    articles = store.search_articles(query)
    response_body = build_search_response(articles, query)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-046: POST /api/kb/feedback
# ---------------------------------------------------------------------------
@app.route(route="kb/feedback", methods=["POST"])
def kb_feedback(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body: { "articleId": "...", "helpful": true, "sessionId": "..." (optional) }
    HTTP status mapping:
    - 400: request body missing/malformed, or 'articleId'/'helpful' invalid
    - 404: articleId does not refer to a known article
    - 200: feedback recorded — always as a NEW row, even for a repeated
      submission from the same session (see kb_store.py's module docstring
      for why this is deliberately append-only, not an upsert).
    """
    try:
        parsed = parse_feedback_request(req.get_body())
    except FeedbackRequestValidationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=400,
        )
    store = get_kb_store()
    try:
        entry = submit_feedback(store, parsed["articleId"], parsed["sessionId"], parsed["helpful"])
    except ArticleNotFoundError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=404,
        )
    response_body = build_feedback_response(entry)
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
    transition = definition.get_transition(instance.current_state, "advance")
    if transition is None:
        return {"error": "No transition defined", "transition": None, "is_terminal": True}
    from_state = instance.current_state
    next_state = transition["to"]
    expected_approver = resolve_expected_approver(transition, instance)
    instance.record_transition(from_state, next_state, action="advance", expected_approver_upn=expected_approver)
    store.save_instance(instance)
    cmdb_store = get_cmdb_store()
    effects = apply_enter_effects(cmdb_store, instance, transition)
    logging.info(
        f"Instance {instanceId}: {from_state} -> {next_state}"
        + (f", expectedApprover={expected_approver}" if expected_approver else "")
        + (f", effects={effects}" if effects else "")
    )
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
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-044-045-046"}),
        mimetype="application/json",
        status_code=200,
    )
