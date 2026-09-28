"""
Offline tests for sql_workflow_store.py's PURE logic only — row parsing,
terminal-state computation, and parameter-building. These do not require
pyodbc, azure-identity, or a live database connection, since they exercise
only the functions that don't touch the network.
Connection-dependent methods (get_definition, create_instance, get_instance,
save_instance on SqlWorkflowStore itself) are NOT covered here — they must be
validated manually against the real Azure SQL Database once provisioned, per
runbook.md Section 6.

HD-028 update: row_to_instance() now parses a 7-element row (added
requesterUpn as the 7th column — see sql_workflow_store.py's module
docstring for why it is appended rather than inserted in the middle).
Tests 3 and 4 below were updated to pass 7-element tuples accordingly, and
a new Test 3b covers the requesterUpn value round-tripping correctly.
build_insert_instance_params() now also takes a third requester_upn
argument — Test 5 updated to match; a new Test 5b covers the
requester_upn=None case (an instance started with no attributed
requester, e.g. the orchestrator's own auto-created TEST instances).
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

print("=== Test 3: row_to_instance parses a workflow_instance row correctly (HD-028: 7 columns) ===")
history = [{"from": "Start", "to": "Middle", "action": "advance", "at": "2026-09-25T15:00:00"}]
row = (
    "abc-123-guid",
    "TEST",
    "Middle",
    json.dumps(history),
    "2026-09-25 15:00:00",
    "2026-09-25 15:00:01",
    "chris.yuen@cognitionlearninggroup.com",  # HD-028: requesterUpn, 7th column
)
instance = row_to_instance(row)
assert instance.instance_id == "abc-123-guid"
assert instance.workflow_def_id == "TEST"
assert instance.current_state == "Middle"
assert instance.history == history
assert instance.requester_upn == "chris.yuen@cognitionlearninggroup.com"
print(f"PASS — instance correctly parsed, history round-trips through JSON, requesterUpn populated\n")

print("=== Test 3b: row_to_instance handles a NULL requesterUpn correctly (HD-028) ===")
row_no_requester = (
    "abc-456-guid",
    "TEST",
    "Middle",
    json.dumps(history),
    "2026-09-25 15:00:00",
    "2026-09-25 15:00:01",
    None,  # requesterUpn — e.g. an orchestrator-created instance with no attributed requester
)
instance_no_requester = row_to_instance(row_no_requester)
assert instance_no_requester.requester_upn is None
print("PASS — NULL requesterUpn correctly becomes None, not an error\n")

print("=== Test 4: row_to_instance handles NULL historyJson (new instance, no transitions yet) ===")
row = ("new-guid", "TEST", "Start", None, "2026-09-25 15:00:00", "2026-09-25 15:00:00", None)
instance = row_to_instance(row)
assert instance.history == [], f"Expected empty history for NULL historyJson, got {instance.history}"
print("PASS — NULL historyJson correctly becomes an empty list, not an error\n")

print("=== Test 5: build_insert_instance_params produces the right parameter order (HD-028: 3 params) ===")
params = build_insert_instance_params("TEST", "Start", "chris.yuen@cognitionlearninggroup.com")
assert params == ("TEST", "Start", "chris.yuen@cognitionlearninggroup.com")
print(f"PASS — insert params: {params}\n")

print("=== Test 5b: build_insert_instance_params handles requester_upn=None correctly (HD-028) ===")
params_none = build_insert_instance_params("TEST", "Start", None)
assert params_none == ("TEST", "Start", None)
print(f"PASS — insert params with no requester: {params_none}\n")

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
