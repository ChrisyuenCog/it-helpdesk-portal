
"""
Offline tests for compliance_api.py (HD-050/051 + document_url addition)
— exercises response building against real InMemoryCmdbStore +
InMemoryComplianceStore instances, no live database or Function host
required.
"""
from cmdb_store import InMemoryCmdbStore
from compliance_store import InMemoryComplianceStore
from compliance_api import (
    build_policy_summary,
    build_policies_response,
    build_certificate_summary,
    build_certificates_response,
)

FOLDER_LINK = "https://cognitioneducationltd.sharepoint.com/:f:/s/CLG-ITandDigitalTransformation/IgBIT0Q92d99SLvY2hholYSTARHGadldaLttGWDIdZ2DlDQ?e=BfhPap"

cmdb_store = InMemoryCmdbStore()
compliance_store = InMemoryComplianceStore()

print("=== Test 1 (NEW): build_policy_summary includes documentUrl in the response ===")
metadata = compliance_store.create_policy_document(
    cmdb_store, title="CLG_SEC_POL_001 ISMS Policy", current_version="1.0",
    approval_status="Approved (Board)", next_review_date="2027-06-26",
    document_url=FOLDER_LINK,
)
ci = cmdb_store.get_ci(metadata.ci_id)
summary = build_policy_summary(ci, metadata)
assert summary["documentUrl"] == FOLDER_LINK
assert set(summary.keys()) == {"ciId", "title", "currentVersion", "approvalStatus", "nextReviewDate", "documentUrl"}
print(f"PASS — {summary}\n")

print("=== Test 2 (NEW): build_policy_summary handles a None documentUrl gracefully (no document_url ever supplied) ===")
metadata_no_url = compliance_store.create_policy_document(
    cmdb_store, title="Test Policy No URL", current_version="1.0",
    approval_status="Draft", next_review_date="2027-01-01",
)
ci_no_url = cmdb_store.get_ci(metadata_no_url.ci_id)
summary_no_url = build_policy_summary(ci_no_url, metadata_no_url)
assert summary_no_url["documentUrl"] is None
print("PASS — None correctly represented, not an error or missing key\n")

print("=== Test 3 (HD-050): build_policies_response includes documentUrl for every policy in the full 6-policy seed ===")
policies = [
    ("CLG_SEC_POL_002 Information and Cyber Security Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_003 Acceptable Use and Remote Working Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_004 Data Protection and Privacy Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_005 Secure Software Development Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_006 AI Governance Policy", "1.0", "Approved (Board)", "2027-06-26"),
]
for title, version, status, review in policies:
    compliance_store.create_policy_document(cmdb_store, title, version, status, review, document_url=FOLDER_LINK)
response = build_policies_response(cmdb_store, compliance_store)
real_policies = [p for p in response["policies"] if p["title"] != "Test Policy No URL"]
assert len(real_policies) == 6
assert all(p["documentUrl"] == FOLDER_LINK for p in real_policies)
print(f"PASS — all 6 real policies include the correct documentUrl\n")

print("=== Test 4 (HD-051): build_certificate_summary includes documentUrl alongside the existing daysRemaining/isExpired fields ===")
ce_plus_metadata = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Plus Certificate", current_version="Profile 3.2 (Willow)",
    expiry_date="2026-09-23", confidentiality_level="Confidential", document_url=FOLDER_LINK,
)
ce_plus_ci = cmdb_store.get_ci(ce_plus_metadata.ci_id)
summary = build_certificate_summary(ce_plus_ci, ce_plus_metadata)
assert summary["documentUrl"] == FOLDER_LINK
assert summary["isExpired"] is True
assert summary["daysRemaining"] < 0
print(f"PASS — {summary}\n")

print("=== Test 5 (HD-049/051): build_certificates_response includes the ICO certificate with correct urgency ===")
ico_metadata = compliance_store.create_certificate_document(
    cmdb_store, title="ICO Data Protection Registration Certificate", current_version="ZA211766",
    expiry_date="2026-10-15", confidentiality_level="Confidential", document_url=FOLDER_LINK,
)
ce_metadata = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Certificate", current_version="Profile 3.3 (Danzell)",
    expiry_date="2027-09-09", confidentiality_level="Confidential", document_url=FOLDER_LINK,
)
response = build_certificates_response(cmdb_store, compliance_store)
assert response["count"] == 3
ico_in_response = next(c for c in response["certificates"] if "ICO" in c["title"])
assert ico_in_response["documentUrl"] == FOLDER_LINK
assert ico_in_response["isExpired"] is False
assert 0 < ico_in_response["daysRemaining"] < 30, "ICO cert should be urgent (< 30 days) but not yet expired"
print(f"PASS — 3 certificates returned, ICO correctly flagged as urgent-but-valid: daysRemaining={ico_in_response['daysRemaining']}\n")

print("=" * 60)
print("ALL COMPLIANCE API OFFLINE TESTS PASSED (document_url addition verified)")
