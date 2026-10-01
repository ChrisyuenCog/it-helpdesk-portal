"""
New offline tests for HD-069 — Strictly Confidential PIN step-up redaction
in compliance_api.py. Additive only; does not modify or replace the
existing test_compliance_api.py (which continues to pass unchanged).
"""
from cmdb_store import InMemoryCmdbStore
from compliance_store import InMemoryComplianceStore
from compliance_api import build_certificate_summary, build_policy_summary

cmdb_store = InMemoryCmdbStore()
compliance_store = InMemoryComplianceStore()

print("=== Test A: Strictly Confidential cert, no PIN session -> documentUrl redacted ===")
metadata = compliance_store.create_certificate_document(
    cmdb_store, title="Hypothetical CE+ Network Scope Doc", current_version="1.0",
    expiry_date="2027-01-01", confidentiality_level="Strictly Confidential",
    document_url="https://example.sharepoint.com/real-link",
)
ci = cmdb_store.get_ci(metadata.ci_id)
summary = build_certificate_summary(ci, metadata, pin_session_valid=False)
assert summary["documentUrl"] is None
assert summary["requiresStepUp"] is True
print(f"PASS — {summary}\n")

print("=== Test B: Strictly Confidential cert, valid PIN session -> documentUrl visible ===")
summary_unlocked = build_certificate_summary(ci, metadata, pin_session_valid=True)
assert summary_unlocked["documentUrl"] == "https://example.sharepoint.com/real-link"
assert "requiresStepUp" not in summary_unlocked
print(f"PASS — {summary_unlocked}\n")

print("=== Test C: Internal-level policy is never gated regardless of pin_session_valid ===")
policy_metadata = compliance_store.create_policy_document(
    cmdb_store, title="CLG_SEC_POL_999 Test Policy", current_version="1.0",
    approval_status="Approved", next_review_date="2027-01-01",
    document_url="https://example.sharepoint.com/policy-link",
)
policy_ci = cmdb_store.get_ci(policy_metadata.ci_id)
summary_default = build_policy_summary(policy_ci, policy_metadata)  # pin_session_valid defaults False
assert summary_default["documentUrl"] == "https://example.sharepoint.com/policy-link"
assert "requiresStepUp" not in summary_default
print(f"PASS — default confidentiality level ('Internal') never redacted — {summary_default}\n")

print("=" * 60)
print("ALL HD-069 STEP-UP TESTS PASSED")
