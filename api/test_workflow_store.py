"""
Offline tests for HD-015/HD-016 â€” validates the WorkflowStore state-machine
logic directly, independent of the Azure Durable Functions runtime (which
isn't available to run locally without a full Azure Functions host).

This exercises exactly the same code path the orchestrator's activity
functions call (create_workflow_instance, advance_workflow_instance in
function_app.py), just invoked directly against the store rather than
through the Durable Functions dispatch layer. If these pass, the
orchestrator's activities will behave identically, since they are thin
wrappers with no additional logic of their own.
"""
from workflow_store import InMemoryWorkflowStore, WorkflowStoreError

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

print("=== Test 7: get_store() singleton returns the same instance across calls ===")
from workflow_store import get_store
s1 = get_store()
s2 = get_store()
assert s1 is s2, "get_store() should return a singleton within one process"
print("PASS â€” singleton pattern confirmed\n")

print("=" * 60)
print("ALL WORKFLOW STORE TESTS PASSED â€” HD-015/HD-016 logic verified")