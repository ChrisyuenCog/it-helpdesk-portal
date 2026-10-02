
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
HD-040: GET /api/identity/authMethods?upn= — HD-039/041 (SSPR tile +
  wizard) are frontend-only, built on top of this endpoint.
HD-045/046: GET /api/kb/search?query=, POST /api/kb/feedback.
HD-050/051 (this revision) — Policy & Compliance Hub:
  - GET /api/compliance/policies — every Policy-type Document CI
    (CLG_SEC_POL_001-006), joined with its version/approval/review-date
    metadata via compliance_api.py + compliance_store.py.
  - GET /api/compliance/certificates — every Certificate-type Document CI
    (Cyber Essentials, Cyber Essentials Plus), with a LIVE-computed
    days-remaining countdown (never stored — same design precedent as
    HD-007's SlaClock.breached_flag). HD-052 (Policy Library viewer) and
    HD-053 (certificate expiry cards) are frontend-only, built on top of
    these two endpoints — see web/index.html.
  Neither endpoint takes query parameters or requires request validation
  — they simply list every Document CI of the relevant type — so, unlike
  most routes in this file, there is no 400 error path for either.
HD-066/067/068/069 (Batch K, brought forward) — Security Hardening:
*** SUPERSEDES the scope note previously here. *** Every route below (one
exception: GET /api/health) now calls auth_api.require_access_group() as
its first action, restricting the ENTIRE portal to members of the CLG -
IT and Digital Transformation Entra ID security group (Object ID
49cab434-8d81-44fd-b871-ecead72becdc) — not the wider 5-role model the
original MVP Specification described (see auth_api.py's module docstring
for the full rationale). A new POST /api/compliance/verifyPin endpoint
(HD-067) issues a short-lived signed session token for stepping up to
view Strictly Confidential documents (HD-069) in the Policy & Compliance
Hub; GET /api/compliance/policies and GET /api/compliance/certificates
now also read an optional X-Pin-Session-Token request header and pass its
validity through to compliance_api.py so Strictly Confidential rows are
redacted unless that step-up has been completed. GET /api/health remains
on func.AuthLevel.ANONYMOUS and deliberately skips the group check — it
is a liveness probe with no CLG data in its response body, and gating it
would break existing uptime/monitoring checks that call it
unauthenticated.
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
from compliance_store import get_compliance_store
from compliance_api import build_policies_response, build_certificates_response
import datetime
from tender_store import get_tender_store, TenderStoreError
from knowledge_store import get_knowledge_store, KnowledgeStoreError
import knowledge_api as kapi
from tender_api import (
    TenderRequestError,
    build_evidence_index,
    build_match_response,
    evaluate_answer_choice,
    build_pack,
    apply_answer_edit,
    approve_answer,
    parse_deadline,
)
from auth_api import (
    require_access_group,
    build_access_denied_response,
    AccessDeniedError,
    verify_pin,
    PinVerificationError,
    validate_pin_session_token,
    get_pin_session_token_from_request,
    build_access_check_body,
)

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


# ---------------------------------------------------------------------------
# HD-017: POST /api/workflow/start (generic, any workflowDefId)
# ---------------------------------------------------------------------------
@app.route(route="workflow/start", methods=["POST"])
@app.durable_client_input(client_name="client")
async def workflow_start(req: func.HttpRequest, client) -> func.HttpResponse:
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
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
# HD-050: GET /api/compliance/policies
# ---------------------------------------------------------------------------
@app.route(route="compliance/policies", methods=["GET"])
def compliance_get_policies(req: func.HttpRequest) -> func.HttpResponse:
    """
    No query parameters. Returns every Policy-type Document CI
    (CLG_SEC_POL_001-006) with its version, approval status, and next
    review date. Always 200 — an empty policies list (before seeding) is
    a valid, non-error response.
    HD-069: an optional X-Pin-Session-Token request header, if present and
    valid, unlocks documentUrl for any Strictly Confidential row (none of
    today's 6 seeded policies are Strictly Confidential, so this has no
    visible effect on current production data).
    """
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
    pin_session_valid = validate_pin_session_token(get_pin_session_token_from_request(req))
    cmdb_store = get_cmdb_store()
    compliance_store = get_compliance_store()
    response_body = build_policies_response(cmdb_store, compliance_store, pin_session_valid=pin_session_valid)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-051: GET /api/compliance/certificates
# ---------------------------------------------------------------------------
@app.route(route="compliance/certificates", methods=["GET"])
def compliance_get_certificates(req: func.HttpRequest) -> func.HttpResponse:
    """
    No query parameters. Returns every Certificate-type Document CI
    (Cyber Essentials, Cyber Essentials Plus) with a LIVE-computed
    daysRemaining (negative if already expired — see compliance_store.py's
    compute_days_remaining docstring) and isExpired flag. Always 200.
    HD-069: an optional X-Pin-Session-Token request header, if present and
    valid, unlocks documentUrl for any Strictly Confidential row (none of
    today's 3 seeded certificates are Strictly Confidential, so this has
    no visible effect on current production data).
    """
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
    pin_session_valid = validate_pin_session_token(get_pin_session_token_from_request(req))
    cmdb_store = get_cmdb_store()
    compliance_store = get_compliance_store()
    response_body = build_certificates_response(cmdb_store, compliance_store, pin_session_valid=pin_session_valid)
    return func.HttpResponse(
        json.dumps(response_body),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# HD-067: POST /api/compliance/verifyPin — Strictly Confidential step-up
# ---------------------------------------------------------------------------
@app.route(route="compliance/verifyPin", methods=["POST"])
def compliance_verify_pin(req: func.HttpRequest) -> func.HttpResponse:
    """
    HD-067: verifies a submitted PIN (body: {"pin": "..."}) against the
    IT_HELPDESK_ADMIN_PIN app setting. On success, returns a signed,
    stateless session token (8-hour TTL) the frontend should echo back on
    subsequent GET /api/compliance/policies|certificates calls via the
    X-Pin-Session-Token header to unlock any Strictly Confidential rows.
    Still requires group membership first — PIN step-up is an ADDITIONAL
    layer on top of the group gate, not a substitute for it.
    """
    try:
        require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
    try:
        body = json.loads(req.get_body() or b"{}")
    except (json.JSONDecodeError, ValueError):
        return func.HttpResponse(
            json.dumps(build_error_response("Request body must be valid JSON.")),
            mimetype="application/json",
            status_code=400,
        )
    try:
        token = verify_pin(body.get("pin", ""))
    except PinVerificationError as e:
        return func.HttpResponse(
            json.dumps(build_error_response(str(e))),
            mimetype="application/json",
            status_code=401,
        )
    return func.HttpResponse(
        json.dumps({"token": token}),
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
# Tender Pack (Batch I, HD-054–058 widened) — /api/tender/*
# ---------------------------------------------------------------------------
# Every route: group check first; the caller's identity for audit fields
# (preparedBy, updatedBy, approvedBy) comes from the sign-in token via
# require_access_group(), never from the request body. Evidence is always
# read live from Policy & Compliance (Strictly Confidential URLs redacted).
def _json_response(body, status_code=200):
    return func.HttpResponse(json.dumps(body), mimetype="application/json", status_code=status_code)


def _caller_name(identity) -> str:
    return identity.user_name or identity.user_id or "unknown"


def _read_json(req):
    try:
        body = json.loads(req.get_body() or b"{}")
    except (json.JSONDecodeError, ValueError):
        raise TenderRequestError("Request body must be valid JSON.")
    if not isinstance(body, dict):
        raise TenderRequestError("Request body must be a JSON object.")
    return body


def _tender_evidence():
    cmdb_store, compliance_store = get_cmdb_store(), get_compliance_store()
    certs = build_certificates_response(cmdb_store, compliance_store)["certificates"]
    policies = build_policies_response(cmdb_store, compliance_store)["policies"]
    return build_evidence_index(certs, policies)


def _tender_guard(handler):
    """Shared auth + error mapping so each route stays a few lines."""
    def wrapped(req: func.HttpRequest) -> func.HttpResponse:
        try:
            identity = require_access_group(req)
        except AccessDeniedError as e:
            return build_access_denied_response(str(e))
        try:
            return handler(req, identity)
        except TenderRequestError as e:
            return _json_response(build_error_response(str(e)), 400)
        except TenderStoreError as e:
            return _json_response(build_error_response(str(e)), 404)
        except Exception:
            logging.exception("tender route failed")
            return _json_response(build_error_response("The tender service hit an unexpected error. Try again."), 500)
    wrapped.__name__ = handler.__name__
    return wrapped


@app.route(route="tender/library", methods=["GET"])
def tender_library_list(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        include_retired = (req.params.get("includeRetired") or "").lower() == "true"
        answers = get_tender_store().list_answers(include_retired=include_retired)
        return _json_response({"count": len(answers), "answers": [a.to_api() for a in answers]})
    return _tender_guard(handler)(req)


@app.route(route="tender/library", methods=["POST"])
def tender_library_save(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        body = _read_json(req)
        store = get_tender_store()
        existing = store.get_answer(body["answerId"]) if body.get("answerId") else None
        ids = [a.answer_id for a in store.list_answers(include_retired=True)]
        saved = store.upsert_answer(apply_answer_edit(body, existing, _caller_name(identity), ids))
        return _json_response({"answer": saved.to_api()})
    return _tender_guard(handler)(req)


@app.route(route="tender/library/{answerId}/approve", methods=["POST"])
def tender_library_approve(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_tender_store()
        answer = store.get_answer(req.route_params.get("answerId"))
        saved = store.upsert_answer(approve_answer(answer, _caller_name(identity), datetime.datetime.utcnow()))
        return _json_response({"answer": saved.to_api()})
    return _tender_guard(handler)(req)


@app.route(route="tender/evidence", methods=["GET"])
def tender_evidence_list(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        docs = _tender_evidence()
        return _json_response({"count": len(docs), "evidence": docs})
    return _tender_guard(handler)(req)


@app.route(route="tender/match", methods=["POST"])
def tender_match(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        body = _read_json(req)
        result = build_match_response(body, get_tender_store().list_answers(), _tender_evidence(),
                                      datetime.datetime.utcnow().date())
        return _json_response(result)
    return _tender_guard(handler)(req)


@app.route(route="tender/evaluate", methods=["POST"])
def tender_evaluate(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        body = _read_json(req)
        today = datetime.datetime.utcnow().date()
        deadline = parse_deadline(body.get("deadline"), today)
        answer = get_tender_store().get_answer(str(body.get("answerId") or ""))
        return _json_response(evaluate_answer_choice(str(body.get("question") or ""), answer, _tender_evidence(), deadline, today))
    return _tender_guard(handler)(req)


@app.route(route="tender/packs", methods=["POST"])
def tender_pack_create(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        body = _read_json(req)
        store = get_tender_store()
        answers = {a.answer_id: a for a in store.list_answers(include_retired=True)}
        pack = build_pack(body, answers, _tender_evidence(), _caller_name(identity), datetime.datetime.utcnow())
        saved = store.create_pack(pack)
        logging.info(f"tender pack {saved.pack_ref} issued by {saved.prepared_by} for {saved.client_name}")
        return _json_response({"pack": {**saved.to_list_item(), "snapshot": saved.snapshot}}, 201)
    return _tender_guard(handler)(req)


@app.route(route="tender/packs", methods=["GET"])
def tender_pack_list(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        packs = get_tender_store().list_packs()
        return _json_response({"count": len(packs), "packs": [p.to_list_item() for p in packs]})
    return _tender_guard(handler)(req)


@app.route(route="tender/packs/{packId}", methods=["GET"])
def tender_pack_get(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        pack = get_tender_store().get_pack(req.route_params.get("packId"))
        return _json_response({"pack": {**pack.to_list_item(), "snapshot": pack.snapshot}})
    return _tender_guard(handler)(req)


# ---------------------------------------------------------------------------
# Knowledge Base v2 — /api/knowledge/*  (the HD-045/046 /api/kb/* routes stay as they are)
# ---------------------------------------------------------------------------
# Readers see Approved articles; "drafts=true" shows drafts too, for the Manage
# view. The portal is currently limited to the IT group, so every caller is an
# editor; when Entra app roles land (roadmap Phase 1), restrict drafts=true and
# the write routes to an editor role here.
def _knowledge_guard(handler):
    def wrapped(req: func.HttpRequest) -> func.HttpResponse:
        try:
            identity = require_access_group(req)
        except AccessDeniedError as e:
            return build_access_denied_response(str(e))
        try:
            return handler(req, identity)
        except (kapi.KnowledgeRequestError, TenderRequestError) as e:
            return _json_response(build_error_response(str(e)), 400)
        except KnowledgeStoreError as e:
            return _json_response(build_error_response(str(e)), 404)
        except Exception:
            logging.exception("knowledge route failed")
            return _json_response(build_error_response("The knowledge base hit an unexpected error. Try again."), 500)
    wrapped.__name__ = handler.__name__
    return wrapped


def _drafts(req) -> bool:
    return (req.params.get("drafts") or "").lower() == "true"


@app.route(route="knowledge/home", methods=["GET"])
def knowledge_home(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        return _json_response(kapi.build_home_response(get_knowledge_store().list_articles(), _drafts(req)))
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/search", methods=["GET"])
def knowledge_search(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        body, entry = kapi.build_search_response(req.params.get("q"), store.list_articles(), _drafts(req))
        if not _drafts(req) and req.params.get("log") != "false":
            store.log_search(entry)  # reader searches only; suggest-as-you-type passes log=false
        return _json_response(body)
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/category", methods=["GET"])
def knowledge_category(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        return _json_response(kapi.build_category_response(str(req.params.get("name") or ""),
                                                          get_knowledge_store().list_articles(), _drafts(req)))
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/articles", methods=["GET"])
def knowledge_list(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        arts = store.list_articles(include_retired=(req.params.get("includeRetired") or "").lower() == "true")
        fb = store.list_feedback()
        return _json_response({"count": len(arts), "articles": [
            {**a.to_api(include_body=False), **kapi.rating_summary(a.article_id, fb)} for a in arts]})
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/articles/{articleId}", methods=["GET"])
def knowledge_get(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        a = store.get_article(req.route_params.get("articleId"))
        body = kapi.build_article_response(a, store.list_articles(), store.list_feedback(), _drafts(req),
                                           datetime.datetime.utcnow().date())
        if a.status == "Approved" and not _drafts(req):
            store.increment_views(a.article_id)
        return _json_response(body)
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/articles", methods=["POST"])
def knowledge_save(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        body = _read_json(req)
        store = get_knowledge_store()
        existing = store.get_article(body["articleId"]) if body.get("articleId") else None
        ids = [a.article_id for a in store.list_articles(include_retired=True)]
        saved = store.upsert_article(kapi.apply_edit(body, existing, _caller_name(identity), ids))
        return _json_response({"article": saved.to_api()})
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/articles/{articleId}/approve", methods=["POST"])
def knowledge_approve(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        a = store.get_article(req.route_params.get("articleId"))
        saved = store.upsert_article(kapi.approve(a, _caller_name(identity), datetime.datetime.utcnow()))
        return _json_response({"article": saved.to_api()})
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/feedback", methods=["POST"])
def knowledge_feedback(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        fb = kapi.parse_feedback(_read_json(req), {a.article_id: a for a in store.list_articles()}, _caller_name(identity))
        store.add_feedback(fb)
        return _json_response({"status": "ok"}, 201)
    return _knowledge_guard(handler)(req)


@app.route(route="knowledge/insights", methods=["GET"])
def knowledge_insights(req: func.HttpRequest) -> func.HttpResponse:
    def handler(req, identity):
        store = get_knowledge_store()
        return _json_response(kapi.build_insights(store.list_articles(include_retired=True), store.list_feedback(),
                                                  store.list_search_log(), datetime.datetime.utcnow().date()))
    return _knowledge_guard(handler)(req)


# ---------------------------------------------------------------------------
# GET /api/auth/check — "is this caller allowed?" probe
# ---------------------------------------------------------------------------
@app.route(route="auth/check", methods=["GET"])
def auth_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns 200 for members of the access group and the usual 403 JSON
    denial for everyone else. Used by the IT Asset Register tab so the
    launch link is only shown to signed-in, authorised staff. Reads no
    data from SQL, so it is cheap to call on every tab click.
    """
    try:
        identity = require_access_group(req)
    except AccessDeniedError as e:
        return build_access_denied_response(str(e))
    return func.HttpResponse(
        json.dumps(build_access_check_body(identity)),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "ok", "service": "it-helpdesk-api", "ticket": "HD-048-049-050-051"}),
        mimetype="application/json",
        status_code=200,
    )
