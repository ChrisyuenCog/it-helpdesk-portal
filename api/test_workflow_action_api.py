
"""
Offline tests for HD-018 — validates POST /api/workflow/action's request
parsing, transition resolution, and role-checking logic, independent of the
Azure Durable Functions runtime (unavailable in this sandbox).
Plus HD-026/030/033/034 additions: list-form requiredRole, requiredFields
hard-gate, and injectable-resolver approver resolution.
"""
import json
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
from workflow_store import InMemoryWorkflowStore, WorkflowStoreError
print("=== Test 1: parse_action_request accepts a valid minimal body ===")
body = json.dumps({"instanceId": "abc-123", "action": "approve"}).encode("utf-8")
parsed = parse_action_request(body)
assert parsed["instanceId"] == "abc-123"
assert parsed["action"] == "approve"
assert parsed["callerRole"] is None
assert parsed["callerUpn"] is None
print(f"PASS — parsed: {parsed}\n")
print("=== Test 2: parse_action_request accepts optional callerRole/callerUpn ===")
body = json.dumps({
    "instanceId": "abc-123", "action": "approve",
    "callerRole": "Approver", "callerUpn": "manager@cognitionlearninggroup.com",
}).encode("utf-8")
parsed = parse_action_request(body)
assert parsed["callerRole"] == "Approver"
assert parsed["callerUpn"] == "manager@cognitionlearninggroup.com"
print(f"PASS — optional fields passed through correctly\n")
print("=== Test 3: parse_action_request rejects missing instanceId ===")
try:
    parse_action_request(json.dumps({"action": "approve"}).encode("utf-8"))
    raise AssertionError("Expected ActionRequestValidationError")
except ActionRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")
print("=== Test 4: parse_action_request rejects missing action ===")
try:
    parse_action_request(json.dumps({"instanceId": "abc-123"}).encode("utf-8"))
    raise AssertionError("Expected ActionRequestValidationError")
except ActionRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")
print("=== Test 5: parse_action_request rejects a non-string callerRole ===")
try:
    parse_action_request(json.dumps({"instanceId": "abc-123", "action": "approve", "callerRole": 123}).encode("utf-8"))
    raise AssertionError("Expected ActionRequestValidationError")
except ActionRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")
print("=== Test 6: resolve_transition finds a valid role-free transition (submit) ===")
store = InMemoryWorkflowStore()
instance = store.create_instance("TEST_APPROVAL")
definition = store.get_definition("TEST_APPROVAL")
transition = resolve_transition(definition, instance, "submit")
assert transition["from"] == "Start"
assert transition["to"] == "PendingApproval"
assert "requiredRole" not in transition
print(f"PASS — resolved: {transition}\n")
print("=== Test 7: resolve_transition raises for an action not valid from the current state ===")
try:
    resolve_transition(definition, instance, "approve")
    raise AssertionError("Expected ActionNotAllowedError")
except ActionNotAllowedError as e:
    print(f"PASS — correctly rejected: {e}\n")
print("=== Test 8: resolve_transition raises for an already-terminal instance ===")
terminal_instance = store.create_instance("TEST")
terminal_instance.record_transition("Start", "Middle", "advance")
terminal_instance.record_transition("Middle", "End", "advance")
store.save_instance(terminal_instance)
test_definition = store.get_definition("TEST")
try:
    resolve_transition(test_definition, terminal_instance, "advance")
    raise AssertionError("Expected ActionNotAllowedError")
except ActionNotAllowedError as e:
    print(f"PASS — correctly rejected terminal-state action: {e}\n")
print("=== Test 9: check_role_permission passes when no role is required ===")
transition_no_role = {"from": "Start", "to": "Middle", "action": "advance"}
check_role_permission(transition_no_role, None)
check_role_permission(transition_no_role, "AnyRoleAtAll")
print("PASS — role-free transitions permit any caller, including no role at all\n")
print("=== Test 10: check_role_permission passes when caller role matches (HD-018 'valid' path) ===")
transition_gated = {"from": "PendingApproval", "to": "Approved", "action": "approve", "requiredRole": "Approver"}
check_role_permission(transition_gated, "Approver")
print("PASS — matching role correctly permitted\n")
print("=== Test 11: check_role_permission raises 403-mappable error on role mismatch (HD-018's core acceptance criterion) ===")
try:
    check_role_permission(transition_gated, "Requester")
    raise AssertionError("Expected RoleNotPermittedError")
except RoleNotPermittedError as e:
    print(f"PASS — correctly raised, function_app.py maps this to HTTP 403: {e}\n")
print("=== Test 12: check_role_permission raises when no role at all is supplied for a gated transition ===")
try:
    check_role_permission(transition_gated, None)
    raise AssertionError("Expected RoleNotPermittedError")
except RoleNotPermittedError as e:
    print(f"PASS — correctly raised: {e}\n")
print("=== Test 13: determine_approval_status maps known actions correctly ===")
assert determine_approval_status("approve") == "Approved"
assert determine_approval_status("reject") == "Rejected"
assert determine_approval_status("escalate") == "Escalate"
print("PASS — approve->Approved, reject->Rejected, unknown actions capitalised\n")
print("=== Test 14: build_action_success_response includes approval_chain data when present ===")
from workflow_store import ApprovalChainEntry
entry = ApprovalChainEntry(instance_id="abc-123", step_order=1, approver_upn="manager@x.com", status="Approved")
response = build_action_success_response(instance, transition_gated, entry)
assert response["status"] == "actioned"
assert response["approvalChainEntry"]["status"] == "Approved"
assert response["approvalChainEntry"]["stepOrder"] == 1
print(f"PASS — response includes approvalChainEntry: {response['approvalChainEntry']}\n")
print("=== Test 15: build_action_success_response omits approval_chain data when None (role-free transitions) ===")
response = build_action_success_response(instance, transition_no_role, None)
assert "approvalChainEntry" not in response
print("PASS — no approvalChainEntry key present for role-free transitions\n")
print("=== Test 16: FULL END-TO-END — submit then approve, with correct role, appends to approval_chain ===")
store = InMemoryWorkflowStore()
instance = store.create_instance("TEST_APPROVAL")
definition = store.get_definition("TEST_APPROVAL")
transition = resolve_transition(definition, instance, "submit")
check_role_permission(transition, None)
instance.record_transition(transition["from"], transition["to"], "submit")
store.save_instance(instance)
assert instance.current_state == "PendingApproval"
transition = resolve_transition(definition, instance, "approve")
check_role_permission(transition, "Approver")
instance.record_transition(transition["from"], transition["to"], "approve")
store.save_instance(instance)
entry = store.append_approval_entry(instance.instance_id, "manager@cognitionlearninggroup.com", "Approved")
assert instance.current_state == "Approved"
assert definition.is_terminal(instance.current_state)
chain = store.get_approval_chain(instance.instance_id)
assert len(chain) == 1
assert chain[0].status == "Approved"
assert chain[0].approver_upn == "manager@cognitionlearninggroup.com"
print(f"PASS — full submit->approve flow: final state={instance.current_state}, "
      f"approval_chain has {len(chain)} entry\n")
print("=== Test 17: FULL END-TO-END — attempting to approve with the WRONG role is correctly rejected, no state change ===")
store2 = InMemoryWorkflowStore()
instance2 = store2.create_instance("TEST_APPROVAL")
definition2 = store2.get_definition("TEST_APPROVAL")
transition = resolve_transition(definition2, instance2, "submit")
check_role_permission(transition, None)
instance2.record_transition(transition["from"], transition["to"], "submit")
store2.save_instance(instance2)
transition = resolve_transition(definition2, instance2, "approve")
try:
    check_role_permission(transition, "Requester")
    raise AssertionError("Expected RoleNotPermittedError")
except RoleNotPermittedError:
    pass
reloaded = store2.get_instance(instance2.instance_id)
assert reloaded.current_state == "PendingApproval", (
    f"Instance must remain in PendingApproval after a rejected role check, "
    f"got '{reloaded.current_state}'"
)
assert store2.get_approval_chain(instance2.instance_id) == []
print("PASS — wrong-role attempt correctly left the instance untouched, "
      "no approval_chain entry created\n")
# ---------------------------------------------------------------------------
# HD-026/030/033/034 additions
# ---------------------------------------------------------------------------
print("=== Test 18 (HD-026/031): check_role_permission accepts list-form requiredRole, either matching role permitted ===")
transition_multi_role = {"from": "ITApproval", "to": "Procurement", "action": "approve", "requiredRole": ["ITAgent", "ITAdmin"]}
check_role_permission(transition_multi_role, "ITAgent")
check_role_permission(transition_multi_role, "ITAdmin")
print("PASS — both 'ITAgent' and 'ITAdmin' independently permitted for the same list-gated transition\n")
print("=== Test 19 (HD-026/031): check_role_permission rejects a role NOT in the list ===")
try:
    check_role_permission(transition_multi_role, "Requester")
    raise AssertionError("Expected RoleNotPermittedError")
except RoleNotPermittedError as e:
    print(f"PASS — correctly rejected: {e}\n")
print("=== Test 20 (HD-033): check_required_fields passes when no requiredFields declared (every pre-HD-033 transition) ===")
check_required_fields(transition_no_role, {})
check_required_fields(transition_gated, {"anything": "irrelevant"})
print("PASS — transitions with no requiredFields impose no constraint at all\n")
print("=== Test 21 (HD-033): check_required_fields passes when the required field is present and non-blank ===")
serial_transition = {"from": "AwaitingSerialCapture", "to": "Fulfilled", "action": "captureSerial", "requiredFields": ["serialNumber"]}
check_required_fields(serial_transition, {"serialNumber": "SN-001"})
print("PASS — present, non-blank field correctly permitted\n")
print("=== Test 22 (HD-033): check_required_fields raises when the required field is missing entirely ===")
try:
    check_required_fields(serial_transition, {})
    raise AssertionError("Expected MissingRequiredFieldError")
except MissingRequiredFieldError as e:
    print(f"PASS — correctly raised (HD-033's core acceptance criterion — empty serial number field is rejected): {e}\n")
print("=== Test 23 (HD-033): check_required_fields raises when the required field is present but blank/whitespace ===")
try:
    check_required_fields(serial_transition, {"serialNumber": "   "})
    raise AssertionError("Expected MissingRequiredFieldError")
except MissingRequiredFieldError as e:
    print(f"PASS — correctly raised for whitespace-only value: {e}\n")
print("=== Test 24 (HD-033): check_required_fields reports ALL missing fields, not just the first ===")
multi_field_transition = {"from": "A", "to": "B", "action": "x", "requiredFields": ["fieldOne", "fieldTwo"]}
try:
    check_required_fields(multi_field_transition, {"fieldOne": "present"})
    raise AssertionError("Expected MissingRequiredFieldError")
except MissingRequiredFieldError as e:
    assert "fieldTwo" in str(e)
    assert "fieldOne" not in str(e)
    print(f"PASS — only the genuinely missing field is reported: {e}\n")
print("=== Test 25 (HD-030): resolve_expected_approver returns None when transition has no resolveApprover ===")
store3 = InMemoryWorkflowStore()
plain_instance = store3.create_instance("TEST", requester_upn="alice@cognitionlearninggroup.com")
assert resolve_expected_approver(transition_no_role, plain_instance) is None
print("PASS — a transition with no 'resolveApprover' key never attempts resolution\n")
print("=== Test 26 (HD-030): resolve_expected_approver calls the injected resolver and returns its result ===")
manager_transition = {"from": "Submitted", "to": "ManagerApproval", "action": "advance", "resolveApprover": "requesterManager"}
def fake_resolver_success(upn):
    assert upn == "alice@cognitionlearninggroup.com"
    return "bob.manager@cognitionlearninggroup.com"
result = resolve_expected_approver(manager_transition, plain_instance, resolve_manager_upn_fn=fake_resolver_success)
assert result == "bob.manager@cognitionlearninggroup.com"
print(f"PASS — injected resolver's result correctly returned: {result}\n")
print("=== Test 27 (HD-030): resolve_expected_approver gracefully returns None if the resolver itself raises ===")
def fake_resolver_failure(upn):
    raise RuntimeError("Graph permissions not yet provisioned (HD-012 pending)")
result = resolve_expected_approver(manager_transition, plain_instance, resolve_manager_upn_fn=fake_resolver_failure)
assert result is None
print("PASS — resolver failure is swallowed, returns None rather than propagating — never blocks the transition\n")
print("=== Test 28 (HD-030): resolve_expected_approver returns None when the instance has no requester_upn ===")
no_requester_instance = store3.create_instance("TEST")
result = resolve_expected_approver(manager_transition, no_requester_instance, resolve_manager_upn_fn=fake_resolver_success)
assert result is None
print("PASS — no requester_upn to resolve against — correctly short-circuits without calling the resolver\n")
print("=== Test 29 (HD-034): build_action_success_response includes 'effects' only when non-empty ===")
response_with_effects = build_action_success_response(instance, transition_gated, None, effects=[{"effectType": "createCi", "ciId": "abc"}])
assert response_with_effects["effects"] == [{"effectType": "createCi", "ciId": "abc"}]
response_without_effects = build_action_success_response(instance, transition_gated, None, effects=[])
assert "effects" not in response_without_effects
response_default = build_action_success_response(instance, transition_gated, None)
assert "effects" not in response_default
print("PASS — 'effects' key present only when non-empty, absent for every pre-HD-034 call site\n")
print("=== Test 30 (HD-026/033): FULL END-TO-END — HARDWARE_REQUEST captureSerial rejected with blank serial, then succeeds ===")
store4 = InMemoryWorkflowStore()
hw_instance = store4.create_instance("HARDWARE_REQUEST", requester_upn="carol@cognitionlearninggroup.com")
hw_def = store4.get_definition("HARDWARE_REQUEST")
for from_s, to_s, action, role in [
    ("Submitted", "ManagerApproval", "advance", None),
    ("ManagerApproval", "ITApproval", "approve", "Approver"),
    ("ITApproval", "Procurement", "approve", "ITAgent"),
    ("Procurement", "AwaitingSerialCapture", "markOrdered", "ITAdmin"),
]:
    t = resolve_transition(hw_def, hw_instance, action)
    check_role_permission(t, role)
    hw_instance.record_transition(from_s, to_s, action)
    store4.save_instance(hw_instance)
assert hw_instance.current_state == "AwaitingSerialCapture"
final_transition = resolve_transition(hw_def, hw_instance, "captureSerial")
check_role_permission(final_transition, "ITAdmin")
try:
    check_required_fields(final_transition, {})
    raise AssertionError("Expected MissingRequiredFieldError for blank serial number")
except MissingRequiredFieldError:
    pass
reloaded_hw = store4.get_instance(hw_instance.instance_id)
assert reloaded_hw.current_state == "AwaitingSerialCapture", "Instance must NOT advance past the hard gate without a serial number"
check_required_fields(final_transition, {"serialNumber": "SN-999"})
hw_instance.record_transition("AwaitingSerialCapture", "Fulfilled", "captureSerial", fields={"serialNumber": "SN-999"})
store4.save_instance(hw_instance)
assert hw_instance.current_state == "Fulfilled"
assert hw_def.is_terminal(hw_instance.current_state)
assert hw_instance.get_fields()["serialNumber"] == "SN-999"
print("PASS — full ManagerApproval->ITApproval->Procurement->AwaitingSerialCapture path completed; "
      "blank serial correctly blocked the final transition; valid serial correctly completed it "
      "to the terminal Fulfilled state, with the serial number retrievable via get_fields()\n")
print("=" * 60)
print("ALL WORKFLOW ACTION API OFFLINE TESTS PASSED — HD-018's original 17 plus")
print("HD-026/030/033/034's 13 new tests, covering list-form roles, the requiredFields")
print("hard gate, injectable approver resolution, and a full HARDWARE_REQUEST lifecycle.")
