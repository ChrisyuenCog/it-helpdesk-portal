
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
"""
from __future__ import annotations
from typing import Dict, Any, List

from cmdb_store import CmdbStore, CIBase, CmdbStoreError
from compliance_store import ComplianceStore, DocumentMetadata, ComplianceStoreError, compute_days_remaining


def build_policy_summary(ci: CIBase, metadata: DocumentMetadata) -> Dict[str, Any]:
    """HD-050: joins a Document CI (name/status) with its
    document_metadata row (version/approval/review date/documentUrl) into
    a single flat response shape."""
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "approvalStatus": metadata.approval_status,
        "nextReviewDate": metadata.next_review_date,
        "documentUrl": metadata.document_url,
    }


def build_policies_response(store: CmdbStore, compliance_store: ComplianceStore) -> Dict[str, Any]:
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
        results.append(build_policy_summary(ci, metadata))
    return {"count": len(results), "policies": results}


def build_certificate_summary(ci: CIBase, metadata: DocumentMetadata) -> Dict[str, Any]:
    """HD-051. Adds the computed daysRemaining field (never stored,
    always live-computed at read time)."""
    days_remaining = compute_days_remaining(metadata.expiry_date)
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "expiryDate": metadata.expiry_date,
        "daysRemaining": days_remaining,
        "isExpired": (days_remaining is not None and days_remaining < 0),
        "confidentialityLevel": metadata.confidentiality_level,
        "documentUrl": metadata.document_url,
    }


def build_certificates_response(store: CmdbStore, compliance_store: ComplianceStore) -> Dict[str, Any]:
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
        results.append(build_certificate_summary(ci, metadata))
    return {"count": len(results), "certificates": results}
