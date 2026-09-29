
"""
Offline tests for compliance_api.py (HD-050/051) — exercises response
building against real InMemoryCmdbStore + InMemoryComplianceStore
instances, no live database or Function host required.
"""
import datetime
from cmdb_store import InMemoryCmdbStore
from compliance_store import InMemoryComplianceStore
from compliance_api import (
    build_policy_summary,
    build_policies_response,
    build_certificate_summary,
    build_certificates_response,
)

cmdb_store = InMemoryCmdbStore()
compliance_store = InMemoryComplianceStore()

print("=== Test 1 (HD-050): build_policy_summary joins ci_base and document_metadata into one flat shape ===")
metadata = compliance_store.create_policy_document(
    cmdb_store, title="CLG_SEC_POL_001 ISMS Policy", current_version="1.0",
    approval_status="Approved (Board)", next_review_date="2027-06-26",
)
ci = cmdb_store.get_ci(metadata.ci_id)
summary = build_policy_summary(ci, metadata)
assert summary == {
    "ciId": metadata.ci_id, "title": "CLG_SEC_POL_001 ISMS Policy",
    "currentVersion": "1.0", "approvalStatus": "Approved (Board)", "nextReviewDate": "2027-06-26",
}
print(f"PASS — {summary}\n")

print("=== Test 2 (HD-050): build_policies_response returns ALL 6 real seeded policies, matching HD-048's acceptance criterion ===")
real_policies = [
    ("CLG_SEC_POL_002 Information and Cyber Security Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_003 Acceptable Use and Remote Working Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_004 Data Protection and Privacy Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_005 Secure Software Development Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_006 AI Governance Policy", "1.0", "Approved (Board)", "2027-06-26"),
]
for title, version, status, review in real_policies:
    compliance_store.create_policy_document(cmdb_store, title, version, status, review)
response = build_policies_response(cmdb_store, compliance_store)
assert response["count"] == 6, f"Expected 6 policies (HD-044's own acceptance criterion), got {response['count']}"
titles = {p["title"] for p in response["policies"]}
assert "CLG_SEC_POL_001 ISMS Policy" in titles
assert "CLG_SEC_POL_006 AI Governance Policy" in titles
print(f"PASS — all 6 real policies present: {sorted(titles)}\n")

print("=== Test 3 (HD-050): every policy in the response has all 3 required fields populated (currentVersion/approvalStatus/nextReviewDate) ===")
for policy in response["policies"]:
    assert policy["currentVersion"] is not None
    assert policy["approvalStatus"] is not None
    assert policy["nextReviewDate"] is not None
print("PASS — HD-048's core acceptance criterion satisfied: zero fields unaccounted for\n")

print("=== Test 4: build_policies_response returns an empty list (not an error) when no policies exist yet ===")
empty_cmdb = InMemoryCmdbStore()
empty_compliance = InMemoryComplianceStore()
empty_response = build_policies_response(empty_cmdb, empty_compliance)
assert empty_response == {"count": 0, "policies": []}
print("PASS — empty state correctly represented, not an error\n")

# ---------------------------------------------------------------------------
# HD-051: certificates + live days-remaining countdown
# ---------------------------------------------------------------------------
print("=== Test 5 (HD-051): build_certificate_summary includes a computed daysRemaining and isExpired flag ===")
ce_plus_metadata = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Plus Certificate", current_version="3.2 (Willow)",
    expiry_date="2026-09-23", confidentiality_level="Confidential",
)
ce_plus_ci = cmdb_store.get_ci(ce_plus_metadata.ci_id)
# Monkeypatch-free: call compute_days_remaining indirectly via a fixed as_of
# by directly testing build_certificate_summary's use of "today" — since
# this session's real "today" (2026-09-29) IS the actual test environment
# date, this exercises the real, non-mocked default path.
summary = build_certificate_summary(ce_plus_ci, ce_plus_metadata)
assert summary["expiryDate"] == "2026-09-23"
assert summary["daysRemaining"] < 0, f"Expected negative (overdue) days, got {summary['daysRemaining']}"
assert summary["isExpired"] is True
print(f"PASS — CE+ correctly shown as EXPIRED: daysRemaining={summary['daysRemaining']}, isExpired={summary['isExpired']}\n")

print("=== Test 6 (HD-051): build_certificate_summary shows isExpired=False and positive daysRemaining for a valid certificate ===")
ce_metadata = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Certificate", current_version="3.3 (Danzell)",
    expiry_date="2027-09-09",
)
ce_ci = cmdb_store.get_ci(ce_metadata.ci_id)
summary = build_certificate_summary(ce_ci, ce_metadata)
assert summary["isExpired"] is False
assert summary["daysRemaining"] > 0
print(f"PASS — CE correctly shown as valid: daysRemaining={summary['daysRemaining']}, isExpired={summary['isExpired']}\n")

print("=== Test 7 (HD-051): build_certificates_response returns BOTH real certificates, each with correct confidentialityLevel ===")
response = build_certificates_response(cmdb_store, compliance_store)
assert response["count"] == 2
ce_plus_in_response = next(c for c in response["certificates"] if "Plus" in c["title"])
assert ce_plus_in_response["confidentialityLevel"] == "Confidential"
assert ce_plus_in_response["isExpired"] is True
ce_in_response = next(c for c in response["certificates"] if c["title"] == "Cyber Essentials Certificate")
assert ce_in_response["confidentialityLevel"] == "Confidential"  # default when not explicitly overridden
assert ce_in_response["isExpired"] is False
print(f"PASS — {response['count']} certificates correctly returned with expiry status and confidentiality level\n")

print("=== Test 8: build_certificates_response returns an empty list (not an error) when no certificates exist yet ===")
empty_response = build_certificates_response(InMemoryCmdbStore(), InMemoryComplianceStore())
assert empty_response == {"count": 0, "certificates": []}
print("PASS — empty state correctly represented, not an error\n")

print("=" * 60)
print("ALL COMPLIANCE API OFFLINE TESTS PASSED")
print("HD-050's 6-policy response and HD-051's real, live-computed expiry")
print("countdowns (including CE+'s genuine current overdue status) both verified.")
