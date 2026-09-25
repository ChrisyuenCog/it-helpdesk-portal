"""
Offline tests for sql_workflow_store.py's PURE logic only — row parsing,
terminal-state computation, and parameter-building. These do not require
pyodbc, azure-identity, or a live database connection, since they exercise
only the functions that don't touch the network.
Connection-dependent methods (get_definition, create_instance, get_instance,
save_instance on SqlWorkflowStore itself) are NOT covered here — they must be
validated manually against the real Azure SQL Database once provisioned, per
runbook.md Section 6.
"""
import json
from sql_workflow_store import (
    row_to_definition,
    row_to_instance,
    compute_terminal_states,
    build_insert_instance_params,
    build_update_instance_params,
)
from workflow_store import WorkflowInstance

print("=== Test 1: row_to_definition parses the TEST definition row correctly ===")
row = (
    "TEST",
    json.dumps(["Start", "Middle", "End"]),
    json.dumps([
        {"from": "Start", "to": "Middle", "action": "advance"},
        {"from": "Middle", "to": "End", "action": "advance"},
    ]),
    None,
    None,
)
definition = row_to_definition(row)
assert definition.workflow_def_id == "TEST"
assert definition.states == ["Start", "Middle", "End"]
assert definition.terminal_states == ["End"], f"Expected ['End'], got {definition.terminal_states}"
assert definition.next_state("Start", "advance") == "Middle"
assert definition.next_state("Middle", "advance") == "End"
assert definition.is_terminal("End") is True
assert definition.is_terminal("Start") is False
print(f"PASS — parsed definition matches HD-016's original in-memory seed exactly\n")

print("=== Test 2: compute_terminal_states handles a branching definition correctly ===")
states = ["A", "B", "C", "D"]
transitions = [
    {"from": "A", "to": "B", "action": "approve"},
    {"from": "A", "to": "D", "action": "reject"},
    {"from": "B", "to": "C", "action": "advance"},
]
terminal = compute_terminal_states(states, transitions)
assert set(terminal) == {"C", "D"}, f"Expected C and D terminal, got {terminal}"
print(f"PASS — correctly identifies multiple terminal states: {sorted(terminal)}\n")

print("=== Test 3: row_to_instance parses a workflow_instance row correctly ===")
history = [{"from": "Start", "to": "Middle", "action": "advance", "at": "2026-09-25T15:00:00"}]
row = (
    "abc-123-guid",
    "TEST",
    "Middle",
    json.dumps(history),
    "2026-09-25 15:00:00",
    "2026-09-25 15:00:01",
)
instance = row_to_instance(row)
assert instance.instance_id == "abc-123-guid"
assert instance.workflow_def_id == "TEST"
assert instance.current_state == "Middle"
assert instance.history == history
print(f"PASS — instance correctly parsed, history round-trips through JSON\n")

print("=== Test 4: row_to_instance handles NULL historyJson (new instance, no transitions yet) ===")
row = ("new-guid", "TEST", "Start", None, "2026-09-25 15:00:00", "2026-09-25 15:00:00")
instance = row_to_instance(row)
assert instance.history == [], f"Expected empty history for NULL historyJson, got {instance.history}"
print("PASS — NULL historyJson correctly becomes an empty list, not an error\n")

print("=== Test 5: build_insert_instance_params produces the right parameter order ===")
params = build_insert_instance_params("TEST", "Start")
assert params == ("TEST", "Start")
print(f"PASS — insert params: {params}\n")

print("=== Test 6: build_update_instance_params serializes history correctly ===")
inst = WorkflowInstance(instance_id="xyz", workflow_def_id="TEST", current_state="Start")
inst.record_transition("Start", "Middle", "advance")
params = build_update_instance_params(inst)
current_state, history_json, instance_id = params
assert current_state == "Middle"
assert instance_id == "xyz"
parsed_history = json.loads(history_json)
assert len(parsed_history) == 1
assert parsed_history[0]["from"] == "Start"
assert parsed_history[0]["to"] == "Middle"
print(f"PASS — update params correctly built: state={current_state}, 1 history entry\n")

print("=" * 60)
print("ALL SQL WORKFLOW STORE OFFLINE TESTS PASSED")
print("(Connection-dependent methods still require manual validation against")
print(" the live Azure SQL Database — see runbook.md Section 6.)")
