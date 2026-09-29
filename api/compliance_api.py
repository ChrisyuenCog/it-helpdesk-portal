
"""
IT Helpdesk Portal — Policy & Compliance API request/response logic
(HD-050/051)
========================================================================
Pure response-building logic for:
  GET /api/compliance/policies       (HD-050)
  GET /api/compliance/certificates   (HD-051)
Separated from the Azure Functions HTTP triggers in function_app.py, same
pattern as every other *_api.py module in this repo. Neither endpoint
takes query parameters — both simply return every Document CI of the
relevant type — so unlike most other *_api.py modules here, there is no
request-parsing/validation function; only response-shaping.
"""
from __future__ import annotations
from typing import Dict, Any, List

from cmdb_store import CmdbStore, CIBase, CmdbStoreError
from compliance_store import ComplianceStore, DocumentMetadata, ComplianceStoreError, compute_days_remaining


def build_policy_summary(ci: CIBase, metadata: DocumentMetadata) -> Dict[str, Any]:
    """HD-050: joins a Document CI (name/status) with its
    document_metadata row (version/approval/review date) into a single
    flat response shape — the two-table join happens HERE, once, so
    neither function_app.py nor the frontend needs to know this is backed
    by two separate tables."""
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "approvalStatus": metadata.approval_status,
        "nextReviewDate": metadata.next_review_date,
    }


def build_policies_response(store: CmdbStore, compliance_store: ComplianceStore) -> Dict[str, Any]:
    """HD-050. Lists every Policy-type Document CI. Skips (rather than
    errors on) any document_metadata row whose corresponding ci_base row
    has gone missing — a defensive data-integrity guard, not an expected
    path, matching this repo's precedent of graceful degradation over
    hard failures for read endpoints."""
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
    always live-computed at read time — same design precedent as
    workflow_store.py's SlaClock.breached_flag property)."""
    days_remaining = compute_days_remaining(metadata.expiry_date)
    return {
        "ciId": ci.ci_id,
        "title": ci.name,
        "currentVersion": metadata.current_version,
        "expiryDate": metadata.expiry_date,
        "daysRemaining": days_remaining,
        "isExpired": (days_remaining is not None and days_remaining < 0),
        "confidentialityLevel": metadata.confidentiality_level,
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
