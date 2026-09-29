
"""
Offline tests for compliance_store.py (HD-048/049) — exercises
InMemoryComplianceStore against a real InMemoryCmdbStore (Batch A), plus
compute_days_remaining()'s pure logic, no live database or Function host
required.
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

print("=== Test 0: get_compliance_store() falls back to InMemoryComplianceStore when AZURE_SQL_SERVER is unset ===")
store = get_compliance_store()
assert isinstance(store, InMemoryComplianceStore), f"Expected InMemoryComplianceStore, got {type(store)}"
print("PASS — get_compliance_store() correctly falls back when SQL is not configured\n")

# ---------------------------------------------------------------------------
# HD-051: compute_days_remaining — pure logic, tested against REAL current
# certificate data (Cyber Essentials Plus genuinely expired 2026-09-23,
# Cyber Essentials genuinely valid until 2027-09-09).
# ---------------------------------------------------------------------------
print("=== Test 1 (HD-051): compute_days_remaining returns None for a policy (no expiryDate at all) ===")
assert compute_days_remaining(None) is None
print("PASS — None correctly returned, not zero or an error, when there is no expiry concept\n")

print("=== Test 2 (HD-051): compute_days_remaining returns a NEGATIVE value for an already-EXPIRED certificate ===")
# Real data: Cyber Essentials Plus, certified 2025-09-23, recertification
# due 2026-09-23 — this is genuinely 6 days overdue as of 2026-09-29.
as_of = datetime.date(2026, 9, 29)
result = compute_days_remaining("2026-09-23", as_of=as_of)
assert result == -6, f"Expected -6 (6 days overdue), got {result}"
print(f"PASS — correctly negative: {result} days (matches HD-051's core acceptance criterion)\n")

print("=== Test 3 (HD-051): compute_days_remaining returns a POSITIVE value for a currently-valid certificate ===")
# Real data: Cyber Essentials (standard), certified 2026-09-09, due 2027-09-09.
result = compute_days_remaining("2027-09-09", as_of=as_of)
assert result == 345, f"Expected 345, got {result}"
print(f"PASS — correctly positive: {result} days remaining\n")

print("=== Test 4 (HD-051): compute_days_remaining returns exactly 0 on the expiry date itself ===")
result = compute_days_remaining("2026-09-29", as_of=as_of)
assert result == 0
print("PASS — expiry-day-itself correctly returns 0, not negative or positive\n")

print("=== Test 5 (HD-051): compute_days_remaining defaults to 'today' when as_of is not supplied ===")
result = compute_days_remaining("2099-01-01")  # far future, no as_of override
assert result is not None and result > 0
print(f"PASS — defaulted to real 'today' internally, returned a sane positive value: {result}\n")

# ---------------------------------------------------------------------------
# HD-048: policy document creation / retrieval
# ---------------------------------------------------------------------------
print("=== Test 6 (HD-048): create_policy_document creates BOTH a ci_base row AND a document_metadata row ===")
cmdb_store = InMemoryCmdbStore()
compliance_store = InMemoryComplianceStore()
policy_meta = compliance_store.create_policy_document(
    cmdb_store, title="CLG_SEC_POL_001 ISMS Policy", current_version="1.0",
    approval_status="Approved (Board)", next_review_date="2027-06-26",
)
ci = cmdb_store.get_ci(policy_meta.ci_id)
assert ci.ci_class == "Document"
assert ci.name == "CLG_SEC_POL_001 ISMS Policy"
assert policy_meta.document_type == "Policy"
assert policy_meta.current_version == "1.0"
assert policy_meta.approval_status == "Approved (Board)"
assert policy_meta.next_review_date == "2027-06-26"
print(f"PASS — ci_base row (class={ci.ci_class}) and document_metadata row created and linked by ciId={ci.ci_id}\n")

print("=== Test 7 (HD-048): get_metadata retrieves the correct metadata row by ciId ===")
fetched = compliance_store.get_metadata(policy_meta.ci_id)
assert fetched.ci_id == policy_meta.ci_id
assert fetched.current_version == "1.0"
print(f"PASS — fetched metadata matches: {fetched.current_version}\n")

print("=== Test 8: get_metadata raises ComplianceStoreError for an unknown ciId (no silent failure) ===")
try:
    compliance_store.get_metadata("not-a-real-ci-id")
    raise AssertionError("Expected ComplianceStoreError, none was raised")
except ComplianceStoreError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 9 (HD-048): list_metadata_by_type('Policy') returns only Policy-type rows, seeded with all 6 real CLG policies ===")
real_policies = [
    ("CLG_SEC_POL_001 ISMS Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_002 Information and Cyber Security Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_003 Acceptable Use and Remote Working Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_004 Data Protection and Privacy Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_005 Secure Software Development Policy", "1.0", "Approved (Board)", "2027-06-26"),
    ("CLG_SEC_POL_006 AI Governance Policy", "1.0", "Approved (Board)", "2027-06-26"),
]
for title, version, status, review in real_policies:
    compliance_store.create_policy_document(cmdb_store, title, version, status, review)
policies = compliance_store.list_metadata_by_type("Policy")
assert len(policies) == 7, f"Expected 7 (1 from Test 6 + 6 real policies), got {len(policies)}"  # +1 from test 6
print(f"PASS — {len(policies)} Policy-type document_metadata rows correctly listed\n")

# ---------------------------------------------------------------------------
# HD-049: certificate document creation / retrieval
# ---------------------------------------------------------------------------
print("=== Test 10 (HD-049): create_certificate_document creates a Certificate-type Document CI with a real expiry date ===")
ce_plus_meta = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Plus Certificate", current_version="3.2 (Willow)",
    expiry_date="2026-09-23", confidentiality_level="Confidential",
)
assert ce_plus_meta.document_type == "Certificate"
assert ce_plus_meta.expiry_date == "2026-09-23"
assert ce_plus_meta.confidentiality_level == "Confidential"
print(f"PASS — Cyber Essentials Plus certificate created: expiryDate={ce_plus_meta.expiry_date}\n")

print("=== Test 11 (HD-049): list_metadata_by_type('Certificate') correctly separates certificates from policies ===")
ce_meta = compliance_store.create_certificate_document(
    cmdb_store, title="Cyber Essentials Certificate", current_version="3.3 (Danzell)",
    expiry_date="2027-09-09",
)
certificates = compliance_store.list_metadata_by_type("Certificate")
assert len(certificates) == 2
policies_again = compliance_store.list_metadata_by_type("Policy")
assert len(policies_again) == 7, "Policy count must be unaffected by adding certificates"
print(f"PASS — {len(certificates)} certificates and {len(policies_again)} policies correctly kept separate\n")

print("=" * 60)
print("ALL COMPLIANCE STORE OFFLINE TESTS PASSED")
print("(compute_days_remaining validated against REAL Cyber Essentials / Cyber")
print(" Essentials Plus certificate dates — CE+ correctly shown 6 days overdue.)")
