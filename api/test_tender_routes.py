"""
End-to-end tests for the /api/tender/* routes in function_app.py: real
handlers, real auth check, in-memory stores. Skips cleanly (exit 0) where
the azure-functions packages are not installed, like the other suites'
offline fallbacks. Run: python test_tender_routes.py
"""
import base64
import datetime
import json
import os
import sys

try:
    import azure.functions as func
    import azure.durable_functions  # noqa: F401
except ImportError:
    print("SKIP: azure-functions not installed; route tests need it (deploy.yml installs requirements first).")
    sys.exit(0)

GROUP = "49cab434-8d81-44fd-b871-ecead72becdc"
os.environ["IT_HELPDESK_ACCESS_GROUP_ID"] = GROUP
os.environ.pop("AZURE_SQL_SERVER", None)

import function_app as fa  # noqa: E402
from cmdb_store import get_cmdb_store  # noqa: E402
from compliance_store import get_compliance_store  # noqa: E402

TODAY = datetime.datetime.utcnow().date()


def principal(user, groups):
    claims = [{"typ": "preferred_username", "val": user}] + [{"typ": "groups", "val": g} for g in groups]
    return base64.b64encode(json.dumps({"userId": user, "claims": claims}).encode()).decode()


def call(fn, method="GET", body=None, route_params=None, user="cyuen@cognitionlearninggroup.com", groups=(GROUP,), url="/api/x"):
    req = func.HttpRequest(
        method=method, url=url, headers={"X-MS-CLIENT-PRINCIPAL": principal(user, list(groups))},
        params={}, route_params=route_params or {}, body=json.dumps(body).encode() if body is not None else b"",
    )
    resp = fn(req)
    return resp.status_code, json.loads(resp.get_body() or b"{}")


def seed_compliance():
    cs, cm = get_compliance_store(), get_cmdb_store()
    d = lambda days: (TODAY + datetime.timedelta(days=days)).isoformat()
    cs.create_certificate_document(cm, "Cyber Essentials Plus", "CE+ cert", d(-9), "Internal", "https://x/ceplus")
    cs.create_certificate_document(cm, "Cyber Essentials", "CE cert", d(345), "Internal", "https://x/ce")
    cs.create_certificate_document(cm, "ICO Data Protection Registration", "ZA211766", d(13), "Internal", "https://x/ico")
    cs.create_policy_document(cm, "CLG_SEC_POL_001 ISMS Policy", "V1.0", "Board approved", d(180), "https://x/pol1")


def test_non_member_is_refused():
    status, body = call(fa.tender_library_list, groups=("some-other-group",))
    assert status == 403 and "restricted" in body["message"], (status, body)
    print("PASS: non-members get 403 on tender routes")


def test_library_and_evidence():
    status, body = call(fa.tender_library_list)
    from tender_seed import SEED_ANSWERS
    assert status == 200 and body["count"] == len(SEED_ANSWERS), body.get("count")
    status, body = call(fa.tender_evidence_list)
    assert status == 200 and {e["title"] for e in body["evidence"]} >= {"Cyber Essentials", "CLG_SEC_POL_001 ISMS Policy"}
    print(f"PASS: library ({len(SEED_ANSWERS)} answers) and evidence list load")


def test_full_flow_approve_match_issue_and_fetch():
    status, body = call(fa.tender_library_approve, "POST", route_params={"answerId": "cert-cyber-essentials"})
    assert status == 200 and body["answer"]["status"] == "Approved"
    assert body["answer"]["approvedBy"] == "cyuen@cognitionlearninggroup.com"
    deadline = (TODAY + datetime.timedelta(days=8)).isoformat()
    status, m = call(fa.tender_match, "POST", {"deadline": deadline, "questions": "1. Do you hold Cyber Essentials?\n2. Do you hold Cyber Essentials Plus?"})
    assert status == 200 and [i["status"] for i in m["items"]] == ["ready", "blocked"], m
    items = [{"question": i["question"], "answerId": i["answer"]["answerId"], "answerText": i["answerText"],
              "include": i["status"] != "blocked"} for i in m["items"]]
    status, p = call(fa.tender_pack_create, "POST", {"clientName": "Example Council", "bidReference": "EC-14",
                                                      "deadline": deadline, "items": items, "preparedBy": "forged@x"})
    assert status == 201, p
    snap = p["pack"]["snapshot"]
    assert snap["preparedBy"] == "cyuen@cognitionlearninggroup.com" and len(snap["items"]) == 1
    status, listing = call(fa.tender_pack_list)
    assert status == 200 and listing["packs"][0]["packRef"] == p["pack"]["packRef"]
    status, got = call(fa.tender_pack_get, route_params={"packId": p["pack"]["packId"]})
    assert status == 200 and got["pack"]["snapshot"]["items"][0]["answerId"] == "cert-cyber-essentials"
    print("PASS: approve, match, issue and re-open a pack end to end; preparer comes from the token")


def test_errors_map_to_400_and_404():
    status, body = call(fa.tender_match, "POST", {"deadline": "2000-01-01", "questions": "Do you hold CE?"})
    assert status == 400 and "past" in body["message"]
    status, body = call(fa.tender_pack_get, route_params={"packId": "nope"})
    assert status == 404
    status, body = call(fa.tender_library_approve, "POST", route_params={"answerId": "cert-iso-27001"})
    assert status == 400 and "[confirm" in body["message"]
    req = func.HttpRequest(method="POST", url="/api/x", headers={"X-MS-CLIENT-PRINCIPAL": principal("a@x", [GROUP])},
                           params={}, route_params={}, body=b"{not json")
    assert fa.tender_match(req).status_code == 400
    print("PASS: bad input is 400, unknown pack is 404, placeholder approval is refused")


def test_library_save_records_editor():
    status, body = call(fa.tender_library_save, "POST", {"category": "Certifications", "question": "Do you hold PCI DSS?",
                                                          "answerText": "No. CLG does not process card payments directly.",
                                                          "keywords": "pci, card payments", "evidence": []}, user="it.admin@x")
    assert status == 200 and body["answer"]["updatedBy"] == "it.admin@x" and body["answer"]["status"] == "Draft"
    assert body["answer"]["keywords"] == ["pci", "card payments"]
    print("PASS: saving a library answer records the editor from the token and starts as Draft")


if __name__ == "__main__":
    seed_compliance()
    test_non_member_is_refused()
    test_library_and_evidence()
    test_full_flow_approve_match_issue_and_fetch()
    test_errors_map_to_400_and_404()
    test_library_save_records_editor()
    print("\nALL TENDER ROUTE TESTS PASSED")
