"""
Offline tests for auth_api.py — HD-066/067/068/069.
"""
import base64
import json
import os
import time

import auth_api

REAL_GROUP_ID = "49cab434-8d81-44fd-b871-ecead72becdc"  # CLG - IT and Digital Transformation


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def _encode_principal(user_name, group_ids):
    claims = [{"typ": "preferred_username", "val": user_name}]
    for gid in group_ids:
        claims.append({"typ": "groups", "val": gid})
    payload = {"userId": user_name, "claims": claims}
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def test_require_access_group_allows_member():
    os.environ["IT_HELPDESK_ACCESS_GROUP_ID"] = REAL_GROUP_ID
    req = FakeRequest({"X-MS-CLIENT-PRINCIPAL": _encode_principal("chris@cognitioneducation.com", [REAL_GROUP_ID])})
    identity = auth_api.require_access_group(req)
    assert identity.user_name == "chris@cognitioneducation.com"
    print("PASS: member of CLG - IT and Digital Transformation is allowed")


def test_require_access_group_denies_non_member():
    os.environ["IT_HELPDESK_ACCESS_GROUP_ID"] = REAL_GROUP_ID
    req = FakeRequest({"X-MS-CLIENT-PRINCIPAL": _encode_principal("someone@cognitioneducation.com", ["grp-999-unrelated"])})
    try:
        auth_api.require_access_group(req)
        assert False, "expected AccessDeniedError"
    except auth_api.AccessDeniedError:
        print("PASS: non-member is denied")


def test_require_access_group_fails_closed_when_unconfigured():
    os.environ.pop("IT_HELPDESK_ACCESS_GROUP_ID", None)
    req = FakeRequest({"X-MS-CLIENT-PRINCIPAL": _encode_principal("chris@cognitioneducation.com", [REAL_GROUP_ID])})
    try:
        auth_api.require_access_group(req)
        assert False, "expected AccessDeniedError (fail closed)"
    except auth_api.AccessDeniedError:
        print("PASS: missing config fails closed (denies, does not open)")


def test_require_access_group_denies_no_principal_header():
    os.environ["IT_HELPDESK_ACCESS_GROUP_ID"] = REAL_GROUP_ID
    req = FakeRequest({})
    try:
        auth_api.require_access_group(req)
        assert False, "expected AccessDeniedError"
    except auth_api.AccessDeniedError:
        print("PASS: missing principal header is denied")


def test_pin_matches_strips_whitespace_both_sides():
    os.environ["IT_HELPDESK_ADMIN_PIN"] = " 4321 "
    os.environ["IT_HELPDESK_PIN_TOKEN_SECRET"] = "s3cr3t"
    token = auth_api.verify_pin("4321")
    assert auth_api.validate_pin_session_token(token) is True
    print("PASS: PIN whitespace-stripping fix applied on both sides")


def test_pin_wrong_raises():
    os.environ["IT_HELPDESK_ADMIN_PIN"] = "4321"
    os.environ["IT_HELPDESK_PIN_TOKEN_SECRET"] = "s3cr3t"
    try:
        auth_api.verify_pin("0000")
        assert False, "expected PinVerificationError"
    except auth_api.PinVerificationError:
        print("PASS: wrong PIN rejected")


def test_pin_token_expires():
    os.environ["IT_HELPDESK_ADMIN_PIN"] = "4321"
    os.environ["IT_HELPDESK_PIN_TOKEN_SECRET"] = "s3cr3t"
    expired_payload = f"strictly-confidential-access|{int(time.time()) - 10}"
    expired_token = auth_api._sign_token(expired_payload, "s3cr3t")
    assert auth_api.validate_pin_session_token(expired_token) is False
    print("PASS: expired token is rejected")


def test_pin_token_bad_signature_rejected():
    os.environ["IT_HELPDESK_PIN_TOKEN_SECRET"] = "s3cr3t"
    assert auth_api.validate_pin_session_token("garbage.notasignature") is False
    print("PASS: tampered/garbage token rejected")


def test_get_pin_session_token_from_request_reads_header():
    req = FakeRequest({"X-Pin-Session-Token": "abc.def"})
    assert auth_api.get_pin_session_token_from_request(req) == "abc.def"
    print("PASS: PIN session token header reader works")


if __name__ == "__main__":
    test_require_access_group_allows_member()
    test_require_access_group_denies_non_member()
    test_require_access_group_fails_closed_when_unconfigured()
    test_require_access_group_denies_no_principal_header()
    test_pin_matches_strips_whitespace_both_sides()
    test_pin_wrong_raises()
    test_pin_token_expires()
    test_pin_token_bad_signature_rejected()
    test_get_pin_session_token_from_request_reads_header()
    print("\nAll auth_api tests passed.")
