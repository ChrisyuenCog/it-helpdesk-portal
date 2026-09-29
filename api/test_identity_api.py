
"""
Offline tests for identity_api.py (HD-040/041) — exercises request parsing
and response building with no live Graph/Function host required.
"""
from identity_api import (
    parse_auth_methods_query,
    build_auth_methods_response,
    AuthMethodsValidationError,
)

print("=== Test 1 (HD-040): parse_auth_methods_query returns the validated upn ===")
assert parse_auth_methods_query({"upn": " chris.yuen@cognitionlearninggroup.com "}) == "chris.yuen@cognitionlearninggroup.com"
print("PASS — upn parsed and whitespace-stripped\n")

print("=== Test 2 (HD-040): parse_auth_methods_query raises when upn is missing ===")
try:
    parse_auth_methods_query({})
    raise AssertionError("Expected AuthMethodsValidationError")
except AuthMethodsValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 3 (HD-040): parse_auth_methods_query raises for an empty/whitespace upn ===")
try:
    parse_auth_methods_query({"upn": "   "})
    raise AssertionError("Expected AuthMethodsValidationError")
except AuthMethodsValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 4 (HD-040/041): build_auth_methods_response with methods=None (Graph unavailable) ===")
response = build_auth_methods_response("chris.yuen@cognitionlearninggroup.com", None)
assert response["available"] is False
assert response["hasAnyMethod"] is False
assert response["methodCount"] == 0
assert response["methods"] == []
assert "reason" in response
print(f"PASS — graceful unavailable state: {response}\n")

print("=== Test 5 (HD-041): build_auth_methods_response correctly flags ZERO registered methods ===")
# Only Password is registered — this must NOT count as "has a method",
# per HD-041's core acceptance criterion (flags users with zero registered
# methods and links to the registration flow).
methods_password_only = [{"type": "Password", "id": "m1"}]
response = build_auth_methods_response("bob@cognitionlearninggroup.com", methods_password_only)
assert response["available"] is True
assert response["hasAnyMethod"] is False, "Password alone must not count as a registered MFA/SSPR method"
assert response["methodCount"] == 0
print(f"PASS — Password-only correctly flagged as zero real methods: {response}\n")

print("=== Test 6 (HD-041): build_auth_methods_response correctly shows a CONFIRMATION state when a real method exists ===")
methods_with_mfa = [
    {"type": "Password", "id": "m1"},
    {"type": "Microsoft Authenticator", "id": "m2"},
]
response = build_auth_methods_response("alice@cognitionlearninggroup.com", methods_with_mfa)
assert response["available"] is True
assert response["hasAnyMethod"] is True
assert response["methodCount"] == 1
assert len(response["methods"]) == 2, "Full raw list (including Password) is still returned for display purposes"
print(f"PASS — real method correctly detected, confirmation state warranted: {response}\n")

print("=== Test 7 (HD-041): build_auth_methods_response with MULTIPLE real methods counts all of them ===")
methods_multi = [
    {"type": "Password", "id": "m1"},
    {"type": "Microsoft Authenticator", "id": "m2"},
    {"type": "Phone", "id": "m3"},
]
response = build_auth_methods_response("carol@cognitionlearninggroup.com", methods_multi)
assert response["methodCount"] == 2
print(f"PASS — methodCount correctly excludes Password: {response['methodCount']}\n")

print("=== Test 8 (HD-040/041): build_auth_methods_response with an EMPTY methods list (no methods at all, not even Password) ===")
response = build_auth_methods_response("dave@cognitionlearninggroup.com", [])
assert response["available"] is True
assert response["hasAnyMethod"] is False
assert response["methodCount"] == 0
print(f"PASS — empty list correctly flagged as zero methods, not an error: {response}\n")

print("=" * 60)
print("ALL IDENTITY API OFFLINE TESTS PASSED")
