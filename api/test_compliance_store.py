
"""
Offline tests for compliance_store.py (HD-048/049 + document_url addition)
— exercises InMemoryComplianceStore against a real InMemoryCmdbStore
(Batch A), plus compute_days_remaining()'s pure logic, no live database or
Function host required.
"""
import os
import datetime

assert "AZURE_SQL_SERVER" not in os.environ, \
    "Test assumes AZURE_SQL_SERVER is not set in this environment"

from cmdb_store import InMemoryCmdbStore
from compliance_store import (
    InMemoryComplianceStore,
    ComplianceStoreError,
    compute_days_remaining,
    get_compliance_store,
)

FOLDER_LINK = "https://cognitioneducationltd.sharepoint.com/:f:/s/CLG-ITandDigitalTransformation/IgBIT0Q92d99SLvY2hholYSTARHGadldaLttGWDIdZ2DlDQ?e=BfhPap"

print("=== Test 0: get_compliance_store() falls back to InMemoryComplianceStore when AZURE_SQL_SERVER is unset ===")
store = get_compliance_store()
assert isinstance(store, InMemoryComplianceStore), f"Expected InMemoryComplianceStore, got {type(store)}"
print("PASS — get_compliance_store() correctly falls back when SQL is not configured\n")

# ---------------------------------------------------------------------------
# HD-051: compute_days_remaining — unchanged pure logic, re-verified
# ---------------------------------------------------------------------------
print("=== Test 1 (HD-051): compute_days_remaining returns None for a policy (no expiryDate at all) ===")
assert compute_days_remaining(None) is None
print("PASS\n")

print("=== Test 2 (HD-051): compute_days_remaining returns a NEGATIVE value for an already-EXPIRED certificate ===")
as_of = datetime.date(2026, 9, 29)
result = compute_days_remaining("2026-09-23", as_of=as_of)
assert result == -6, f"Expected -6, got {result}"
print(f"PASS — {result} days\n")

print("=== Test 3 (HD-051): compute_days_remaining returns a small POSITIVE value for the ICO registration (16 days as of 2026-09-29) ===")
result = compute_days_remaining("2026-10-15", as_of=as_of)
assert result == 16, f"Expected 16, got {result}"
print(f"PASS — {result} days\n")

# ---------------------------------------------------------------------------
# document_url — new this revision
# ---------------------------------------------------------------------------
print("=== Test 4 (NEW): create_policy_document accepts and stores a document_url ===")
cmdb_store = InMemoryCmdbStore()
compliance_store = InMemoryComplianceStore()
policy_meta = compliance_store.create_policy_document(
    cmdb_store, title="CLG_SEC_POL_001 ISMS Policy", current_version="1.0",
    approval_status="Approved (Board)", next_review_date="2027-06-26",
    document_url=FOLDER_LINK,
)
assert policy_meta.document_url == FOLDER_LINK
print(f"PASS — document_url correctly stored: {policy_meta.document_url}\n")

print("=== Test 5 (NEW): create_policy_document defaults document_url to None when not supplied (backward compatible) ===")
policy_meta_no_url = compliance_store.create_policy_document(
    cmdb_store, title="Test Policy No URL", current_version="1.0",
    approval_status="Draft", next_review_date="2027-01-01",
)
assert policy_meta_no_url.document_url is None
print("PASS — omitting document_url does not break existing call sites\n")

print("=== Test 6 (NEW): create_certificate_document accepts and stores a document_url ===")
cert_meta = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Plus Certificate", current_version="Profile 3.2 (Willow)",
    expiry_date="2026-09-23", confidentiality_level="Confidential",
    document_url=FOLDER_LINK,
)
assert cert_meta.document_url == FOLDER_LINK
print(f"PASS — document_url correctly stored for certificate: {cert_meta.document_url}\n")

print("=== Test 7 (NEW): get_metadata round-trips document_url correctly ===")
fetched = compliance_store.get_metadata(cert_meta.ci_id)
assert fetched.document_url == FOLDER_LINK
print("PASS — document_url survives get_metadata round-trip\n")

# ---------------------------------------------------------------------------
# Full realistic seed — 6 policies + 3 certificates, all with the folder link
# ---------------------------------------------------------------------------
print("=== Test 8 (HD-048/049): full realistic seed — 6 policies + 3 certificates, all carrying document_url ===")
cmdb_store2 = InMemoryCmdbStore()
compliance_store2 = InMemoryComplianceStore()
policies = [
    ("CLG_SEC_POL_001 ISMS Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_002 Information and Cyber Security Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_003 Acceptable Use and Remote Working Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_004 Data Protection and Privacy Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_005 Secure Software Development Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_006 AI Governance Policy", "1.0", "Approved (Board)", "2027-06-26"),
]
for title, version, status, review in policies:
    compliance_store2.create_policy_document(cmdb_store2, title, version, status, review, document_url=FOLDER_LINK)
certificates = [
    ("Cyber Essentials Plus Certificate", "Profile 3.2 (Willow)", "2026-09-23"),
    ("Cyber Essentials Certificate", "Profile 3.3 (Danzell)", "2027-09-09"),
    ("ICO Data Protection Registration Certificate", "ZA211766", "2026-10-15"),
]
for title, version, expiry in certificates:
    compliance_store2.create_certificate_document(cmdb_store2, title, version, expiry, document_url=FOLDER_LINK)

all_policies = compliance_store2.list_metadata_by_type("Policy")
all_certificates = compliance_store2.list_metadata_by_type("Certificate")
assert len(all_policies) == 6
assert len(all_certificates) == 3
assert all(p.document_url == FOLDER_LINK for p in all_policies)
assert all(c.document_url == FOLDER_LINK for c in all_certificates)
print(f"PASS — {len(all_policies)} policies + {len(all_certificates)} certificates, all with document_url populated\n")

print("=== Test 9 (HD-049): all 3 certificates show correct expiry status ===")
ico_cert = next(c for c in all_certificates if "ICO" in c.ci_id or True)  # will filter by title via ci below
cmdb_ico = [cmdb_store2.get_ci(c.ci_id) for c in all_certificates]
by_title = {ci.name: meta for ci, meta in zip(cmdb_ico, all_certificates)}
assert compute_days_remaining(by_title["Cyber Essentials Plus Certificate"].expiry_date, as_of=as_of) == -6
assert compute_days_remaining(by_title["Cyber Essentials Certificate"].expiry_date, as_of=as_of) == 345
assert compute_days_remaining(by_title["ICO Data Protection Registration Certificate"].expiry_date, as_of=as_of) == 16
print("PASS — CE+ overdue (-6), CE valid (345), ICO urgent-but-valid (16) — all correct\n")

print("=" * 60)
print("ALL COMPLIANCE STORE OFFLINE TESTS PASSED (document_url addition verified)")
