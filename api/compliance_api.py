
"""
IT Helpdesk Portal — Policy & Compliance API request/response logic
(HD-050/051)
========================================================================
Pure response-building logic for:
  GET /api/compliance/policies       (HD-050)
  GET /api/compliance/certificates   (HD-051)
Separated from the Azure Functions HTTP triggers in function_app.py.

THIS REVISION: both build_policy_summary() and build_certificate_summary()
now include a 'documentUrl' field in their response, sourced from
DocumentMetadata.document_url, so the frontend can render a "View
Document" link. See compliance_store.py's module docstring for the
important limitation that this currently points at a shared SharePoint
folder link (not a per-document deep link), since enterprise search does
not expose a stable per-document URL.

*** THIS REVISION (HD-069) — Strictly Confidential PIN step-up ***
build_policy_summary() / build_certificate_summary() now accept an
optional `pin_session_valid` flag. For any row where
confidentiality_level == "Strictly Confidential", documentUrl is redacted
(replaced with None plus a `requiresStepUp: true` flag) unless the caller
has already passed the PIN check (see auth_api.verify_pin /
validate_pin_session_token). Today none of the 3 seeded certificates are
marked Strictly Confidential (all default to "Internal"), so this has NO
visible effect on current production data — it only engages once a
document is explicitly flagged Strictly Confidential (e.g. future CE+
network-scope material).
"""
from __future__ import annotations
from typing import Dict, Any, List

from cmdb_store import CmdbStore, CIBase, CmdbStoreError
from compliance_store import ComplianceStore, DocumentMetadata, ComplianceStoreError, compute_days_remaining

STRICTLY_CONFIDENTIAL = "Strictly Confidential"


def _apply_step_up_gate(document_url, confidentiality_level: str, pin_session_valid: bool) -> Dict[str, Any]:
    """HD-069: shared redaction logic for both policy and certificate rows.
    IMPORTANT: 'requiresStepUp' is only added to the response dict when the
    gate actually triggers (Strictly Confidential + no valid PIN session) —
    it is deliberately omitted otherwise, rather than always present as
    False, so the existing offline test's exact-keys assertion
    (test_compliance_api.py Test 1, pre-dating this revision) continues to
    pass unchanged for every non-Strictly-Confidential row, which is every
    row in production today."""
    if confidentiality_level == STRICTLY_CONFIDENTIAL and not pin_session_valid:
        return {"documentUrl": None, "requiresStepUp": True}
    return {"documentUrl": document_url}


def build_policy_summary(ci: CIBase, metadata: DocumentMetadata, pin_session_valid: bool = False) -> Dict[str, Any]:
    """HD-050: joins a Document CI (name/status) with its
    document_metadata row (version/approval/review date/documentUrl) into
    a single flat response shape. HD-069: documentUrl is redacted for
    Strictly Confidential rows unless pin_session_valid is True."""
    gate = _apply_step_up_gate(metadata.document_url, metadata.confidentiality_level, pin_session_valid)
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "approvalStatus": metadata.approval_status,
        "nextReviewDate": metadata.next_review_date,
        **gate,
    }


def build_policies_response(store: CmdbStore, compliance_store: ComplianceStore, pin_session_valid: bool = False) -> Dict[str, Any]:
    """HD-050. Lists every Policy-type Document CI. Skips (rather than
    errors on) any document_metadata row whose corresponding ci_base row
    has gone missing."""
    metadata_rows = compliance_store.list_metadata_by_type("Policy")
    results = []
    for metadata in metadata_rows:
        try:
            ci = store.get_ci(metadata.ci_id)
        except CmdbStoreError:
            continue
        results.append(build_policy_summary(ci, metadata, pin_session_valid))
    return {"count": len(results), "policies": results}


def build_certificate_summary(ci: CIBase, metadata: DocumentMetadata, pin_session_valid: bool = False) -> Dict[str, Any]:
    """HD-051. Adds the computed daysRemaining field (never stored,
    always live-computed at read time). HD-069: documentUrl is redacted
    for Strictly Confidential rows unless pin_session_valid is True."""
    days_remaining = compute_days_remaining(metadata.expiry_date)
    gate = _apply_step_up_gate(metadata.document_url, metadata.confidentiality_level, pin_session_valid)
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "expiryDate": metadata.expiry_date,
        "daysRemaining": days_remaining,
        "isExpired": (days_remaining is not None and days_remaining < 0),
        "confidentialityLevel": metadata.confidentiality_level,
        **gate,
    }


def build_certificates_response(store: CmdbStore, compliance_store: ComplianceStore, pin_session_valid: bool = False) -> Dict[str, Any]:
    """HD-051. Lists every Certificate-type Document CI with a live
    days-remaining countdown. Same defensive skip-on-missing-CI guard as
    build_policies_response."""
    metadata_rows = compliance_store.list_metadata_by_type("Certificate")
    results = []
    for metadata in metadata_rows:
        try:
            ci = store.get_ci(metadata.ci_id)
        except CmdbStoreError:
            continue
        results.append(build_certificate_summary(ci, metadata, pin_session_valid))
    return {"count": len(results), "certificates": results}
