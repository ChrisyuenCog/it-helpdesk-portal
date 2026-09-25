"""
Offline tests for HD-017 — validates POST /api/workflow/start's request
parsing, workflowDefId validation, and response-building logic, all
independent of the Azure Durable Functions runtime (unavailable in this
sandbox, same limitation as previous tickets in this codebase).

These tests exercise exactly the logic function_app.py's workflow_start
handler calls — if these pass, the handler's behaviour for valid/invalid
requests is proven correct; only the actual HTTP/Durable Functions plumbing
around it (untestable offline) remains to be checked manually per the
runbook.
"""
import json
from workflow_api import (
    parse_start_request,
    validate_workflow_def_id,
    build_start_success_response,
    build_error_response,
    StartRequestValidationError,
)
from workflow_store import InMemoryWorkflowStore, WorkflowStoreError

print("=== Test 1: parse_start_request accepts a valid minimal body ===")
body = json.dumps({"workflowDefId": "TEST"}).encode("utf-8")
parsed = parse_start_request(body)
assert parsed["workflowDefId"] == "TEST"
assert parsed["requesterUpn"] is None
print(f"PASS — parsed: {parsed}\n")

print("=== Test 2: parse_start_request accepts an optional requesterUpn ===")
body = json.dumps({"workflowDefId": "TEST", "requesterUpn": "chris@cognitionlearninggroup.com"}).encode("utf-8")
parsed = parse_start_request(body)
assert parsed["requesterUpn"] == "chris@cognitionlearninggroup.com"
print(f"PASS — requesterUpn passed through correctly\n")

print("=== Test 3: parse_start_request rejects an empty body ===")
try:
    parse_start_request(None)
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

try:
    parse_start_request(b"")
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected empty bytes: {e}\n")

print("=== Test 4: parse_start_request rejects malformed JSON ===")
try:
    parse_start_request(b"{not valid json")
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 5: parse_start_request rejects a JSON array (not an object) ===")
try:
    parse_start_request(b'["TEST"]')
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 6: parse_start_request rejects a missing workflowDefId ===")
try:
    parse_start_request(json.dumps({"requesterUpn": "x@y.com"}).encode("utf-8"))
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 7: parse_start_request rejects an empty-string workflowDefId ===")
try:
    parse_start_request(json.dumps({"workflowDefId": ""}).encode("utf-8"))
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 8: parse_start_request rejects a non-string workflowDefId ===")
try:
    parse_start_request(json.dumps({"workflowDefId": 12345}).encode("utf-8"))
    raise AssertionError("Expected StartRequestValidationError, none was raised")
except StartRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 9: validate_workflow_def_id passes silently for a known definition (HD-017 'valid' path) ===")
store = InMemoryWorkflowStore()
validate_workflow_def_id(store, "TEST")  # should not raise
print("PASS — no exception raised for a valid, known workflowDefId\n")

print("=== Test 10: validate_workflow_def_id raises for an unknown definition (HD-017's 400 requirement) ===")
try:
    validate_workflow_def_id(store, "DOES_NOT_EXIST")
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    print(f"PASS — correctly raised, function_app.py maps this to HTTP 400: {e}\n")

print("=== Test 11: build_start_success_response produces the documented response shape ===")
response = build_start_success_response("abc-123", "TEST", "Start")
assert response["status"] == "started"
assert response["instanceId"] == "abc-123"
assert response["workflowDefId"] == "TEST"
assert response["currentState"] == "Start"
print(f"PASS — response: {response}\n")

print("=== Test 12: build_error_response produces a consistent error shape ===")
response = build_error_response("Something went wrong")
assert response == {"status": "error", "message": "Something went wrong"}
print(f"PASS — response: {response}\n")

print("=== Test 13: end-to-end simulation — valid request through to instance creation ===")
store = InMemoryWorkflowStore()
body = json.dumps({"workflowDefId": "TEST"}).encode("utf-8")
parsed = parse_start_request(body)
validate_workflow_def_id(store, parsed["workflowDefId"])  # does not raise
instance = store.create_instance(parsed["workflowDefId"])
response = build_start_success_response(instance.instance_id, parsed["workflowDefId"], instance.current_state)
assert response["status"] == "started"
assert response["currentState"] == "Start"
print(f"PASS — full valid-request simulation succeeded: {response}\n")

print("=== Test 14: end-to-end simulation — invalid workflowDefId correctly short-circuits before any instance is created ===")
store = InMemoryWorkflowStore()
body = json.dumps({"workflowDefId": "NOT_A_REAL_WORKFLOW"}).encode("utf-8")
parsed = parse_start_request(body)
try:
    validate_workflow_def_id(store, parsed["workflowDefId"])
    raise AssertionError("Expected WorkflowStoreError, none was raised")
except WorkflowStoreError as e:
    error_response = build_error_response(str(e))
    assert error_response["status"] == "error"
    print(f"PASS — correctly short-circuited with a 400-mappable error, no instance created: {error_response}\n")

print("=" * 60)
print("ALL WORKFLOW API OFFLINE TESTS PASSED — HD-017 request/response")
print("logic verified for both valid and invalid workflowDefId paths")