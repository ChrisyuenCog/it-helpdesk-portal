"""
Offline tests for the workflow store — HD-015/HD-016 original tests
(unchanged, regression) plus HD-018 additions (get_transition, terminal
state computation reuse, TEST_APPROVAL seed, approval_chain round-trip).
"""
import os
from workflow_store import (
    InMemoryWorkflowStore,
    WorkflowStoreError,
    get_store,
    compute_terminal_states,
)

# ---------------------------------------------------------------------------
# Original HD-015/016 regression tests — UNCHANGED. Must still pass exactly
# as before, proving HD-018's changes did not alter TEST's behaviour.
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
t = approval_def.get_transition("Start", "approve")  # 'approve' isn't valid from 'Start'
assert t is None
print("PASS — correctly returns None rather than raising, for use in resolve_transition's own error handling\n")

print("=== Test 10 (HD-018): next_state still works correctly on top of the get_transition refactor (no regression) ===")
assert approval_def.next_state("Start", "submit") == "PendingApproval"
assert approval_def.next_state("PendingApproval", "approve") == "Approved"
assert approval_def.next_state("PendingApproval", "reject") == "Rejected"
assert approval_def.next_state("Start", "approve") is None  # not valid from Start
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

print("=" * 60)
print("ALL WORKFLOW STORE TESTS PASSED (7 original regression + 8 new HD-018)")
print("HD-015/HD-016 behaviour fully preserved; HD-018 additions verified.")