
"""
Offline tests for graph_api.py (HD-030) — exercises ONLY the pure,
connection-independent response parser. resolve_manager_upn() itself is
connection-dependent (live Microsoft Graph call via Managed Identity) and
is explicitly NOT covered here — see graph_api.py's module docstring for
why this cannot be validated end-to-end until HD-012's Entra App
Registration and Graph permissions are provisioned (Batch B, Not Started
as of this revision). This mirrors test_sql_workflow_store.py's precedent
of testing only the pure row/response-parsing logic offline, leaving the
actual connection-dependent call to be validated manually per runbook.md
Section 6 once its real dependency (HD-012) ships.
"""
from graph_api import _manager_upn_from_graph_response, resolve_manager_upn

print("=== Test 1 (HD-030): _manager_upn_from_graph_response parses a well-formed Graph response ===")
response = {"userPrincipalName": "manager@cognitionlearninggroup.com", "id": "abc-123"}
assert _manager_upn_from_graph_response(response) == "manager@cognitionlearninggroup.com"
print("PASS — userPrincipalName correctly extracted\n")

print("=== Test 2 (HD-030): _manager_upn_from_graph_response returns None when userPrincipalName is absent ===")
assert _manager_upn_from_graph_response({"id": "abc-123"}) is None
print("PASS — missing field correctly treated as 'no manager', not an error\n")

print("=== Test 3 (HD-030): _manager_upn_from_graph_response returns None for a non-dict input ===")
assert _manager_upn_from_graph_response(None) is None
assert _manager_upn_from_graph_response("not a dict") is None
assert _manager_upn_from_graph_response([]) is None
print("PASS — any non-conforming shape correctly returns None rather than raising\n")

print("=== Test 4 (HD-030): _manager_upn_from_graph_response treats a blank userPrincipalName as no manager ===")
assert _manager_upn_from_graph_response({"userPrincipalName": ""}) is None
assert _manager_upn_from_graph_response({"userPrincipalName": "   "}) is None
print("PASS — blank/whitespace-only value correctly treated as absent\n")

print("=== Test 5 (HD-030): resolve_manager_upn NEVER raises, even with no live Graph/Managed Identity available ===")
# This sandbox has no live Azure credentials or network access to Graph —
# resolve_manager_upn must gracefully return None rather than raising,
# exactly as it would in production before HD-012 ships.
result = resolve_manager_upn("someone@cognitionlearninggroup.com")
assert result is None, f"Expected None (no live Graph access in this environment), got {result!r}"
print("PASS — resolve_manager_upn is fail-soft: gracefully returns None with no live Graph "
      "access, exactly matching the expected pre-HD-012 production behaviour\n")

print("=" * 60)
print("ALL GRAPH API OFFLINE TESTS PASSED (pure response-parsing logic).")
print("resolve_manager_upn's LIVE Graph call still requires manual validation")
print("against a real tenant once HD-012's Entra App Registration ships.")
