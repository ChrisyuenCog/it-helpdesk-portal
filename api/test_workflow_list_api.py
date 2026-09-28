"""
Offline smoke test for HD-028/029 — exercises workflow_list_api.py against
an InMemoryWorkflowStore, no Azure/Durable Functions host required.
Run with: python3 test_workflow_list_api.py
"""
from workflow_store import InMemoryWorkflowStore
from workflow_list_api import (
    parse_my_requests_query,
    parse_my_approvals_query,
    build_my_requests_response,
    build_my_approvals_response,
    build_instance_summary,
    MyRequestsValidationError,
    MyApprovalsValidationError,
)

print("=== Test 1: parse_my_requests_query rejects missing/empty requesterUpn ===")
for bad_params in ({}, {"requesterUpn": ""}, {"requesterUpn": "   "}):
    try:
        parse_my_requests_query(bad_params)
        raise AssertionError(f"Expected MyRequestsValidationError for {bad_params!r}")
    except MyRequestsValidationError:
        pass
print("PASS — missing/empty requesterUpn correctly rejected\n")

print("=== Test 2: parse_my_requests_query accepts and trims a valid value ===")
result = parse_my_requests_query({"requesterUpn": "  chris.yuen@cognitionlearninggroup.com  "})
assert result == "chris.yuen@cognitionlearninggroup.com"
print(f"PASS — trimmed correctly: '{result}'\n")

print("=== Test 3: parse_my_approvals_query rejects missing/empty role ===")
for bad_params in ({}, {"role": ""}, {"role": "  "}):
    try:
        parse_my_approvals_query(bad_params)
        raise AssertionError(f"Expected MyApprovalsValidationError for {bad_params!r}")
    except MyApprovalsValidationError:
        pass
print("PASS — missing/empty role correctly rejected\n")

print("=== Test 4: HD-028 — myRequests returns only this requester's instances ===")
store = InMemoryWorkflowStore()
inst_a1 = store.create_instance("TEST", requester_upn="alice@cognitionlearninggroup.com")
inst_a2 = store.create_instance("TEST_APPROVAL", requester_upn="alice@cognitionlearninggroup.com")
inst_b1 = store.create_instance("TEST", requester_upn="bob@cognitionlearninggroup.com")
inst_c1 = store.create_instance("TEST")  # no requester — should never appear in anyone's myRequests

alice_instances = store.get_instances_by_requester("alice@cognitionlearninggroup.com")
assert len(alice_instances) == 2
assert {i.instance_id for i in alice_instances} == {inst_a1.instance_id, inst_a2.instance_id}

bob_instances = store.get_instances_by_requester("bob@cognitionlearninggroup.com")
assert len(bob_instances) == 1
assert bob_instances[0].instance_id == inst_b1.instance_id

nobody_instances = store.get_instances_by_requester("nobody@cognitionlearninggroup.com")
assert nobody_instances == []
print(f"PASS — alice sees {len(alice_instances)}, bob sees {len(bob_instances)}, "
      f"unrelated requester sees {len(nobody_instances)}\n")

print("=== Test 5: HD-028 — build_my_requests_response shape is correct ===")
response = build_my_requests_response(alice_instances, "alice@cognitionlearninggroup.com")
assert response["requesterUpn"] == "alice@cognitionlearninggroup.com"
assert response["count"] == 2
assert all(item["requesterUpn"] == "alice@cognitionlearninggroup.com" for item in response["instances"])
print(f"PASS — response shape correct: {response}\n")

print("=== Test 6: HD-029 — myApprovals returns instances awaiting a given role ===")
# inst_x is a TEST_APPROVAL instance sitting in PendingApproval, which HAS
# outgoing transitions requiring 'Approver' — should appear in Approver's list.
inst_x = store.create_instance("TEST_APPROVAL", requester_upn="carol@cognitionlearninggroup.com")
inst_x.record_transition("Start", "PendingApproval", "submit")
store.save_instance(inst_x)

approver_pending = store.get_instances_pending_role("Approver")
assert inst_x.instance_id in {i.instance_id for i in approver_pending}
# inst_a2 is still sitting in Start (never submitted) — Start's only
# outgoing transition is 'submit' with NO requiredRole, so it must NOT
# appear in Approver's pending list.
assert inst_a2.instance_id not in {i.instance_id for i in approver_pending}
print(f"PASS — {len(approver_pending)} instance(s) correctly pending for role 'Approver', "
      f"includes inst_x, excludes not-yet-submitted inst_a2\n")

print("=== Test 7: HD-029 — a role with no matching pending instances returns empty ===")
itadmin_pending = store.get_instances_pending_role("ITAdmin")
assert itadmin_pending == []
print("PASS — unrelated role correctly returns an empty list\n")

print("=== Test 8: HD-029 — once actioned, instance drops out of the pending list ===")
inst_x.record_transition("PendingApproval", "Approved", "approve")
store.save_instance(inst_x)
approver_pending_after = store.get_instances_pending_role("Approver")
assert inst_x.instance_id not in {i.instance_id for i in approver_pending_after}
print("PASS — approved instance correctly no longer appears in Approver's pending list "
      "(now terminal — Approved has no outgoing transitions)\n")

print("=== Test 9: build_my_approvals_response shape is correct ===")
response2 = build_my_approvals_response(approver_pending, "Approver")
assert response2["role"] == "Approver"
assert response2["count"] == len(approver_pending)
print(f"PASS — response shape correct: {response2}\n")

print("=== Test 10: build_instance_summary includes all expected fields, no extra store calls ===")
summary = build_instance_summary(inst_a1)
assert set(summary.keys()) == {"instanceId", "workflowDefId", "currentState", "requesterUpn", "createdAt", "updatedAt"}
print(f"PASS — summary shape correct: {summary}\n")

print("=" * 50)
print("ALL HD-028/029 OFFLINE TESTS PASSED")
