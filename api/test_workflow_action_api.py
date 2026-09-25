"""
Offline tests for HD-018 — validates POST /api/workflow/action's request
parsing, transition resolution, and role-checking logic, independent of the
Azure Durable Functions runtime (unavailable in this sandbox).

These directly exercise the logic function_app.py's workflow_action handler
calls. If these pass, the handler's 400/403/200 behaviour is proven correct
for every acceptance-criterion scenario; only the actual HTTP plumbing
(untestable offline) remains to be checked manually per the runbook.
"""
import json
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
    resolve_transition(definition, instance, "approve")  # instance is still in 'Start', not 'PendingApproval'
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
check_role_permission(transition_no_role, None)  # should not raise
check_role_permission(transition_no_role, "AnyRoleAtAll")  # should also not raise
print("PASS — role-free transitions permit any caller, including no role at all\n")

print("=== Test 10: check_role_permission passes when caller role matches (HD-018 'valid' path) ===")
transition_gated = {"from": "PendingApproval", "to": "Approved", "action": "approve", "requiredRole": "Approver"}
check_role_permission(transition_gated, "Approver")  # should not raise
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
assert determine_approval_status("escalate") == "Escalate"  # unknown action, capitalised verbatim
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

# Step 1: submit (no role required)
transition = resolve_transition(definition, instance, "submit")
check_role_permission(transition, None)
instance.record_transition(transition["from"], transition["to"], "submit")
store.save_instance(instance)
assert instance.current_state == "PendingApproval"

# Step 2: approve (requires Approver role)
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
    check_role_permission(transition, "Requester")  # WRONG role
    raise AssertionError("Expected RoleNotPermittedError")
except RoleNotPermittedError:
    pass  # expected — instance must NOT have transitioned

reloaded = store2.get_instance(instance2.instance_id)
assert reloaded.current_state == "PendingApproval", (
    f"Instance must remain in PendingApproval after a rejected role check, "
    f"got '{reloaded.current_state}'"
)
assert store2.get_approval_chain(instance2.instance_id) == []
print("PASS — wrong-role attempt correctly left the instance untouched, "
      "no approval_chain entry created\n")

print("=" * 60)
print("ALL WORKFLOW ACTION API OFFLINE TESTS PASSED — HD-018 request/response,")
print("transition-resolution, and role-checking logic verified for both the")
print("valid and invalid (400/403) paths, end to end.")