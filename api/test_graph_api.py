
"""
Offline tests for graph_api.py (HD-030, HD-040) — exercises ONLY the pure,
connection-independent response parsers. resolve_manager_upn() and
get_auth_methods() are both connection-dependent (live Microsoft Graph call
via Managed Identity) and are covered only for their fail-soft behaviour —
see each function's docstring for why full live validation cannot happen
until HD-012's Entra App Registration ships.
"""
from graph_api import (
    _manager_upn_from_graph_response,
    resolve_manager_upn,
    _method_type_label,
    parse_auth_methods_response,
    get_auth_methods,
    NON_MFA_METHOD_TYPES,
)

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

print("=== Test 4 (HD-030): resolve_manager_upn NEVER raises, even with no live Graph/Managed Identity available ===")
result = resolve_manager_upn("someone@cognitionlearninggroup.com")
assert result is None, f"Expected None (no live Graph access in this environment), got {result!r}"
print("PASS — resolve_manager_upn is fail-soft\n")

print("=== Test 5 (HD-040): NON_MFA_METHOD_TYPES contains Password ===")
assert "Password" in NON_MFA_METHOD_TYPES
print("PASS — Password correctly excluded from real-MFA-method accounting\n")

print("=== Test 6 (HD-040): _method_type_label maps known odata types to friendly labels ===")
assert _method_type_label({"@odata.type": "#microsoft.graph.passwordAuthenticationMethod"}) == "Password"
assert _method_type_label({"@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod"}) == "Microsoft Authenticator"
assert _method_type_label({"@odata.type": "#microsoft.graph.phoneAuthenticationMethod"}) == "Phone"
assert _method_type_label({"@odata.type": "#microsoft.graph.fido2AuthenticationMethod"}) == "Security Key (FIDO2)"
print("PASS — all known method types map to friendly labels\n")

print("=== Test 7 (HD-040): _method_type_label gracefully derives a label for an UNKNOWN odata type ===")
label = _method_type_label({"@odata.type": "#microsoft.graph.someFutureAuthenticationMethod"})
assert label == "someFuture", f"Expected derived label 'someFuture', got '{label}'"
print(f"PASS — unknown type gracefully derived rather than raising: '{label}'\n")

print("=== Test 8 (HD-040): _method_type_label handles a missing/blank odata type ===")
assert _method_type_label({}) == "Unknown method"
print("PASS — missing @odata.type correctly falls back to 'Unknown method'\n")

print("=== Test 9 (HD-040): parse_auth_methods_response parses a well-formed Graph collection response ===")
graph_response = {
    "value": [
        {"@odata.type": "#microsoft.graph.passwordAuthenticationMethod", "id": "m1"},
        {"@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod", "id": "m2"},
    ]
}
parsed = parse_auth_methods_response(graph_response)
assert parsed == [
    {"type": "Password", "id": "m1"},
    {"type": "Microsoft Authenticator", "id": "m2"},
]
print(f"PASS — parsed correctly: {parsed}\n")

print("=== Test 10 (HD-040): parse_auth_methods_response returns an empty list for a user with zero methods ===")
assert parse_auth_methods_response({"value": []}) == []
print("PASS — empty 'value' array correctly returns an empty list, not None or an error\n")

print("=== Test 11 (HD-040): parse_auth_methods_response returns None for a malformed response (missing 'value') ===")
assert parse_auth_methods_response({"unexpected": "shape"}) is None
assert parse_auth_methods_response(None) is None
assert parse_auth_methods_response("not a dict") is None
print("PASS — malformed responses correctly return None, distinguishing 'call failed' from 'zero methods'\n")

print("=== Test 12 (HD-040): parse_auth_methods_response skips non-dict entries in 'value' gracefully ===")
parsed = parse_auth_methods_response({"value": [{"@odata.type": "#microsoft.graph.phoneAuthenticationMethod", "id": "m1"}, "garbage", None]})
assert parsed == [{"type": "Phone", "id": "m1"}]
print(f"PASS — garbage entries skipped, valid entry still parsed: {parsed}\n")

print("=== Test 13 (HD-040): get_auth_methods NEVER raises, even with no live Graph/Managed Identity available ===")
result = get_auth_methods("someone@cognitionlearninggroup.com")
assert result is None, f"Expected None (no live Graph access in this environment), got {result!r}"
print("PASS — get_auth_methods is fail-soft, matching resolve_manager_upn's established precedent\n")

print("=" * 60)
print("ALL GRAPH API OFFLINE TESTS PASSED (13 total — HD-030's original 5 plus HD-040's 8 new).")
print("Both resolve_manager_upn and get_auth_methods' LIVE Graph calls still require")
print("manual validation against a real tenant once HD-012's Entra App Registration ships.")
