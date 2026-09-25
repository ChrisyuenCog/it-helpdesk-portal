"""
Offline tests for HD-015/HD-016 â€” validates the WorkflowStore state-machine
logic directly, independent of the Azure Durable Functions runtime (which
isn't available to run locally without a full Azure Functions host).

Regression note: these tests must still pass unchanged after HD-002/003/005/006
graduated get_store() to prefer SqlWorkflowStore when AZURE_SQL_SERVER is set.
Since that env var is NOT set in this test run, get_store() must fall back to
InMemoryWorkflowStore exactly as before â€” this file is the proof that the
fallback path preserves 100% of the original HD-015/016 behaviour.
"""
import os
from workflow_store import InMemoryWorkflowStore, WorkflowStoreError, get_store

print("=== Test 0: get_store() falls back to InMemoryWorkflowStore when AZURE_SQL_SERVER is unset ===")
assert "AZURE_SQL_SERVER" not in os.environ, "Test assumes AZURE_SQL_SERVER is not set in this environment"
store = get_store()
assert isinstance(store, InMemoryWorkflowStore), f"Expected InMemoryWorkflowStore, got {type(store)}"
print("PASS â€” get_store() correctly falls back when SQL is not configured\n")

print("=== Test 1: TEST definition seeded correctly (HD-016) ===")
store = InMemoryWorkflowStore()
definition = store.get_definition("TEST")
assert definition.states == ["Start", "Middle", "End"], f"Unexpected states: {definition.states}"
assert definition.terminal_states == ["End"]
assert len(definition.transitions) == 2
print(f"PASS â€” states: {definition.states}, terminal: {definition.terminal_states}\n")

print("=== Test 2: unknown workflowDefId raises (no silent failure) ===")
try:
    store.get_definition("DOES_NOT_EXIST")
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    print(f"PASS â€” correctly raised: {e}\n")

print("=== Test 3: create_instance starts at the definition's initial state ===")
instance = store.create_instance("TEST")
assert instance.current_state == "Start", f"Expected 'Start', got '{instance.current_state}'"
assert instance.workflow_def_id == "TEST"
print(f"PASS â€” instance {instance.instance_id} starts at '{instance.current_state}'\n")

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
print(f"PASS â€” transitions taken: {transitions_taken}")
print(f"PASS â€” final state: {instance.current_state}")
print(f"PASS â€” history recorded {len(instance.history)} entries\n")

print("=== Test 5: no transition defined from a terminal state (loop termination) ===")
next_state = definition.next_state("End", action="advance")
assert next_state is None, "Terminal state should have no further transition"
print("PASS â€” terminal state correctly has no outgoing transition\n")

print("=== Test 6: unknown instance_id raises (no silent failure) ===")
try:
    store.get_instance("not-a-real-id")
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    print(f"PASS â€” correctly raised: {e}\n")

print("=" * 60)
print("ALL WORKFLOW STORE REGRESSION TESTS PASSED â€” HD-015/HD-016 behaviour")
print("preserved unchanged after HD-002/003/005/006 storage graduation")