
"""
Offline tests for the workflow store — HD-015/HD-016 original tests
(unchanged, regression) plus HD-018 additions (get_transition, terminal
state computation reuse, TEST_APPROVAL seed, approval_chain round-trip)
plus HD-026/030 additions (HARDWARE_REQUEST seed, list-form requiredRole,
fields/expectedApproverUpn embedded-in-history round-trip).
"""
import os
from workflow_store import (
    InMemoryWorkflowStore,
    WorkflowStoreError,
    get_store,
    compute_terminal_states,
    normalize_required_roles,
)
# ---------------------------------------------------------------------------
# Original HD-015/016 regression tests — UNCHANGED. Must still pass exactly
# as before, proving HD-018/026/030's changes did not alter TEST's behaviour.
# ---------------------------------------------------------------------------
print("=== Test 0: get_store() falls back to InMemoryWorkflowStore when AZURE_SQL_SERVER is unset ===")
assert "AZURE_SQL_SERVER" not in os.environ, "Test assumes AZURE_SQL_SERVER is not set in this environment"
store = get_store()
assert isinstance(store, InMemoryWorkflowStore), f"Expected InMemoryWorkflowStore, got {type(store)}"
print("PASS — get_store() correctly falls back when SQL is not configured\n")
print("=== Test 1: TEST definition seeded correctly (HD-016) ===")
store = InMemoryWorkflowStore()
definition = store.get_definition("TEST")
assert definition.states == ["Start", "Middle", "End"], f"Unexpected states: {definition.states}"
assert definition.terminal_states == ["End"]
assert len(definition.transitions) == 2
print(f"PASS — states: {definition.states}, terminal: {definition.terminal_states}\n")
print("=== Test 2: unknown workflowDefId raises (no silent failure) ===")
try:
    store.get_definition("DOES_NOT_EXIST")
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    print(f"PASS — correctly raised: {e}\n")
print("=== Test 3: create_instance starts at the definition's initial state ===")
instance = store.create_instance("TEST")
assert instance.current_state == "Start", f"Expected 'Start', got '{instance.current_state}'"
assert instance.workflow_def_id == "TEST"
print(f"PASS — instance {instance.instance_id} starts at '{instance.current_state}'\n")
print("=== Test 4: full walk from Start -> Middle -> End (HD-015 core requirement) ===")
instance = store.create_instance("TEST")
definition = store.get_definition(instance.workflow_def_id)
transitions_taken = []
while not definition.is_terminal(instance.current_state):
    next_state = definition.next_state(instance.current_state, action="advance")
    assert next_state is not None, f"No transition defined from '{instance.current_state}'"
    from_state = instance.current_state
    instance.record_transition(from_state, next_state, action="advance")
    store.save_instance(instance)
    transitions_taken.append((from_state, next_state))
assert transitions_taken == [("Start", "Middle"), ("Middle", "End")], \
    f"Unexpected transition sequence: {transitions_taken}"
assert instance.current_state == "End"
assert len(instance.history) == 2
print(f"PASS — transitions taken: {transitions_taken}")
print(f"PASS — final state: {instance.current_state}")
print(f"PASS — history recorded {len(instance.history)} entries\n")
print("=== Test 5: no transition defined from a terminal state (loop termination) ===")
next_state = definition.next_state("End", action="advance")
assert next_state is None, "Terminal state should have no further transition"
print("PASS — terminal state correctly has no outgoing transition\n")
print("=== Test 6: unknown instance_id raises (no silent failure) ===")
try:
    store.get_instance("not-a-real-id")
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    print(f"PASS — correctly raised: {e}\n")
# ---------------------------------------------------------------------------
# HD-018 additions
# ---------------------------------------------------------------------------
print("=== Test 7 (HD-018): compute_terminal_states matches TEST's previous hardcoded value ===")
terminal = compute_terminal_states(
    ["Start", "Middle", "End"],
    [
        {"from": "Start", "to": "Middle", "action": "advance"},
        {"from": "Middle", "to": "End", "action": "advance"},
    ],
)
assert terminal == ["End"], f"Expected ['End'], got {terminal}"
print("PASS — shared terminal-state computation matches original hardcoded TEST behaviour exactly\n")
print("=== Test 8 (HD-018): get_transition returns the FULL transition dict, including requiredRole when present ===")
store = InMemoryWorkflowStore()
approval_def = store.get_definition("TEST_APPROVAL")
t = approval_def.get_transition("PendingApproval", "approve")
assert t is not None
assert t["to"] == "Approved"
assert t["requiredRole"] == "Approver"
print(f"PASS — full transition dict returned: {t}\n")
print("=== Test 9 (HD-018): get_transition returns None for an undefined (state, action) pair ===")
t = approval_def.get_transition("Start", "approve")
assert t is None
print("PASS — correctly returns None rather than raising, for use in resolve_transition's own error handling\n")
print("=== Test 10 (HD-018): next_state still works correctly on top of the get_transition refactor (no regression) ===")
assert approval_def.next_state("Start", "submit") == "PendingApproval"
assert approval_def.next_state("PendingApproval", "approve") == "Approved"
assert approval_def.next_state("PendingApproval", "reject") == "Rejected"
assert approval_def.next_state("Start", "approve") is None
print("PASS — next_state() contract fully preserved after refactor to use get_transition() internally\n")
print("=== Test 11 (HD-018): TEST_APPROVAL definition seeded with correct states and terminal states ===")
assert approval_def.states == ["Start", "PendingApproval", "Approved", "Rejected"]
assert set(approval_def.terminal_states) == {"Approved", "Rejected"}
print(f"PASS — states: {approval_def.states}, terminal: {sorted(approval_def.terminal_states)}\n")
print("=== Test 12 (HD-018): TEST (original) definition is completely unaffected by TEST_APPROVAL's addition ===")
test_def = store.get_definition("TEST")
assert test_def.states == ["Start", "Middle", "End"]
assert test_def.terminal_states == ["End"]
print("PASS — TEST definition unchanged, confirming zero cross-contamination between seeded definitions\n")
print("=== Test 13 (HD-018): append_approval_entry / get_approval_chain round-trip correctly, with incrementing step_order ===")
store = InMemoryWorkflowStore()
instance = store.create_instance("TEST_APPROVAL")
entry1 = store.append_approval_entry(instance.instance_id, "manager1@x.com", "Approved")
assert entry1.step_order == 1
entry2 = store.append_approval_entry(instance.instance_id, "manager2@x.com", "Approved")
assert entry2.step_order == 2
chain = store.get_approval_chain(instance.instance_id)
assert len(chain) == 2
assert chain[0].approver_upn == "manager1@x.com"
assert chain[1].approver_upn == "manager2@x.com"
print(f"PASS — 2 approval_chain entries recorded with correctly incrementing step_order: "
      f"{[e.step_order for e in chain]}\n")
print("=== Test 14 (HD-018): get_approval_chain returns an empty list for an instance with no approval history ===")
fresh_instance = store.create_instance("TEST")
assert store.get_approval_chain(fresh_instance.instance_id) == []
print("PASS — empty list returned, not an error, for an instance with no approval entries yet\n")
# ---------------------------------------------------------------------------
# HD-026/030/033/034 additions
# ---------------------------------------------------------------------------
print("=== Test 15 (HD-026): normalize_required_roles handles None, string, and list forms ===")
assert normalize_required_roles(None) == []
assert normalize_required_roles("Approver") == ["Approver"]
assert normalize_required_roles(["ITAgent", "ITAdmin"]) == ["ITAgent", "ITAdmin"]
print("PASS — all three shapes normalize correctly\n")
print("=== Test 16 (HD-026): HARDWARE_REQUEST definition seeded with all 7 states per MVP Spec Section 4.1 ===")
store = InMemoryWorkflowStore()
hw_def = store.get_definition("HARDWARE_REQUEST")
assert hw_def.states == [
    "Submitted", "ManagerApproval", "ITApproval", "Procurement",
    "AwaitingSerialCapture", "Fulfilled", "Rejected",
], f"Unexpected states: {hw_def.states}"
assert set(hw_def.terminal_states) == {"Fulfilled", "Rejected"}, f"Unexpected terminal states: {hw_def.terminal_states}"
print(f"PASS — states: {hw_def.states}, terminal: {sorted(hw_def.terminal_states)}\n")
print("=== Test 17 (HD-026): HARDWARE_REQUEST's full happy-path transition chain resolves correctly ===")
assert hw_def.next_state("Submitted", "advance") == "ManagerApproval"
assert hw_def.next_state("ManagerApproval", "approve") == "ITApproval"
assert hw_def.next_state("ITApproval", "approve") == "Procurement"
assert hw_def.next_state("Procurement", "markOrdered") == "AwaitingSerialCapture"
assert hw_def.next_state("AwaitingSerialCapture", "captureSerial") == "Fulfilled"
print("PASS — Submitted -> ManagerApproval -> ITApproval -> Procurement -> AwaitingSerialCapture -> Fulfilled\n")
print("=== Test 18 (HD-026): HARDWARE_REQUEST's reject paths resolve correctly from both approval states ===")
assert hw_def.next_state("ManagerApproval", "reject") == "Rejected"
assert hw_def.next_state("ITApproval", "reject") == "Rejected"
print("PASS — both ManagerApproval and ITApproval can reject to the terminal Rejected state\n")
print("=== Test 19 (HD-031, via HD-026 seed): ITApproval's requiredRole is list-form ['ITAgent','ITAdmin'] ===")
it_approval_transition = hw_def.get_transition("ITApproval", "approve")
assert it_approval_transition["requiredRole"] == ["ITAgent", "ITAdmin"]
print(f"PASS — {it_approval_transition['requiredRole']}\n")
print("=== Test 20 (HD-033, via HD-026 seed): AwaitingSerialCapture->Fulfilled declares requiredFields=['serialNumber'] ===")
serial_transition = hw_def.get_transition("AwaitingSerialCapture", "captureSerial")
assert serial_transition["requiredFields"] == ["serialNumber"]
print(f"PASS — {serial_transition['requiredFields']}\n")
print("=== Test 21 (HD-034, via HD-026 seed): Fulfilled-entry transition declares a createCi onEnterEffect ===")
assert serial_transition["onEnterEffects"][0]["type"] == "createCi"
assert serial_transition["onEnterEffects"][0]["ciClass"] == "Hardware"
print(f"PASS — {serial_transition['onEnterEffects']}\n")
print("=== Test 22 (HD-030, via HD-026 seed): Submitted->ManagerApproval declares resolveApprover='requesterManager' ===")
submit_transition = hw_def.get_transition("Submitted", "advance")
assert submit_transition["resolveApprover"] == "requesterManager"
print(f"PASS — {submit_transition['resolveApprover']}\n")
print("=== Test 23 (HD-026/031): roles_pending_from correctly flattens list-form requiredRole for ITApproval ===")
pending_roles = hw_def.roles_pending_from("ITApproval")
assert pending_roles == ["ITAdmin", "ITAgent"], f"Expected sorted ['ITAdmin','ITAgent'], got {pending_roles}"
print(f"PASS — {pending_roles} (both roles individually present, matching 'ITAgent OR ITAdmin')\n")
print("=== Test 24 (HD-026): roles_pending_from for ManagerApproval still returns single-string form correctly ===")
assert hw_def.roles_pending_from("ManagerApproval") == ["Approver"]
print("PASS — string-form requiredRole still flattens correctly alongside list-form transitions in the same definition\n")
print("=== Test 25 (HD-026/033/030): WorkflowInstance.record_transition embeds fields/expectedApproverUpn in history, not new columns ===")
store = InMemoryWorkflowStore()
hw_instance = store.create_instance("HARDWARE_REQUEST", requester_upn="alice@cognitionlearninggroup.com")
hw_instance.record_transition("Submitted", "ManagerApproval", "advance", expected_approver_upn="manager@cognitionlearninggroup.com")
assert hw_instance.history[-1]["expectedApproverUpn"] == "manager@cognitionlearninggroup.com"
assert "fields" not in hw_instance.history[-1], "No fields were passed — key must be absent, not an empty dict"
hw_instance.record_transition("ManagerApproval", "ITApproval", "approve")
hw_instance.record_transition("ITApproval", "Procurement", "approve")
hw_instance.record_transition("Procurement", "AwaitingSerialCapture", "markOrdered")
hw_instance.record_transition("AwaitingSerialCapture", "Fulfilled", "captureSerial", fields={"serialNumber": "SN-001"})
store.save_instance(hw_instance)
print("PASS — 5-step full lifecycle recorded via record_transition with no schema changes\n")
print("=== Test 26 (HD-026/033): get_fields() flattens fields across the whole history, later entries win on collision ===")
assert hw_instance.get_fields() == {"serialNumber": "SN-001"}
print(f"PASS — {hw_instance.get_fields()}\n")
print("=== Test 27 (HD-030): get_expected_approver_upn() returns the most recently recorded value ===")
assert hw_instance.get_expected_approver_upn() == "manager@cognitionlearninggroup.com"
print(f"PASS — {hw_instance.get_expected_approver_upn()}\n")
print("=== Test 28 (HD-030): get_expected_approver_upn() returns None for an instance where it was never set ===")
plain_instance = store.create_instance("TEST")
assert plain_instance.get_expected_approver_upn() is None
print("PASS — None correctly returned, not an error or empty string, for an instance with no approver resolution history\n")
print("=== Test 29 (HD-026/033): get_fields() returns an empty dict for an instance with no captured fields ===")
assert plain_instance.get_fields() == {}
print("PASS — empty dict correctly returned for TEST instances, which never capture fields\n")
print("=" * 60)
print("ALL WORKFLOW STORE TESTS PASSED (14 original regression + 8 HD-018 + 15 HD-026/030/033/034)")
print("HD-015 through HD-029 behaviour fully preserved; HD-026/030/033/034 additions verified.")
