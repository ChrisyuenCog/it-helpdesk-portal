
"""
IT Helpdesk Portal — Policy & Compliance Store
==================================================
HD-048/049: models POL_001-006 and CE/CE+/ICO as Document CIs, so policy
version/approval/review tracking and certificate expiry countdowns
participate in the same CMDB machinery as every other CI.

*** CRITICAL DESIGN NOTE — why this is a SEPARATE table, not new ci_base
columns *** (unchanged from the original revision — see below.)
HD-048's acceptance criterion asks for 'currentVersion, approvalStatus and
nextReviewDate' per Document CI; HD-049 adds 'expiryDate' for certificates.
None of these exist as ci_base columns. Rather than repeating the EXACT
regression class already hit once this session (HD-028 adding
requesterUpn to workflow_instance broke a hidden test file), this
metadata lives in a BRAND NEW table (dbo.document_metadata, one row per
ciId).

HD-049 confidentiality note: 'confidentialityLevel' distinguishes a
Document CI holding just the CERTIFICATE OF ASSURANCE from any underlying
scoping material.

HD-051 core logic: compute_days_remaining() is a pure, offline-testable
function mirroring workflow_store.py's compute_sla_breached() precedent.

*** NEW THIS REVISION — document_url field ***
Adds an optional 'document_url' field to DocumentMetadata, so policies and
certificates can carry a link back to their real source document,
enabling a "View Document" link in the frontend (Policy Library / Certificate
Status views).
*** IMPORTANT LIMITATION — read before assuming these are deep links ***
Enterprise search does not expose a stable, directly-storable per-document
URL for SharePoint files — search results return filenames, authors, and
in-conversation citation references, but no persistent URL field. Rather
than fabricate individual document links (which risk being wrong or
breaking), every seeded row currently uses the SAME known-good SharePoint
FOLDER link that contains all 9 real source documents (policies +
certificates). This is a genuine, working, clickable link — it just opens
the folder rather than deep-linking straight to one file. If/when exact
per-document "Copy link" URLs are provided, each row's document_url can be
updated individually with a plain UPDATE statement — the column, dataclass
field, API field, and frontend rendering are already fully generic and
require no further code changes to support that upgrade.
"""
from __future__ import annotations

import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from cmdb_store import CmdbStore, CIBase, CmdbStoreError


@dataclass
class DocumentMetadata:
    """HD-048/049: one row per Document CI, joined by ci_id."""
    ci_id: str
    document_type: str  # "Policy" | "Certificate"
    current_version: Optional[str] = None
    approval_status: Optional[str] = None
    next_review_date: Optional[str] = None  # ISO date string, policies only
    expiry_date: Optional[str] = None        # ISO date string, certificates only
    confidentiality_level: str = "Internal"
    document_url: Optional[str] = None       # NEW — link back to the real source document
    updated_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


def compute_days_remaining(expiry_date: Optional[str], as_of: Optional[datetime.date] = None) -> Optional[int]:
    """HD-051: pure, offline-testable. Returns the number of whole days
    between `as_of` (defaults to today, UTC) and expiry_date. A NEGATIVE
    result correctly represents an already-expired/overdue certificate.
    Returns None if expiry_date itself is None."""
    if not expiry_date:
        return None
    expiry = expiry_date
    if isinstance(expiry, str):
        expiry = datetime.date.fromisoformat(expiry[:10])
    reference = as_of if as_of is not None else datetime.datetime.utcnow().date()
    return (expiry - reference).days


class ComplianceStoreError(Exception):
    pass


class ComplianceStore:
    """Abstract interface. SqlComplianceStore implements this exact same
    contract."""

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str],
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        raise NotImplementedError

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential",
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        raise NotImplementedError

    def get_metadata(self, ci_id: str) -> DocumentMetadata:
        raise NotImplementedError

    def list_metadata_by_type(self, document_type: str) -> List[DocumentMetadata]:
        raise NotImplementedError


class InMemoryComplianceStore(ComplianceStore):
    """Safe fallback when Azure SQL is not configured."""

    def __init__(self):
        self._metadata: Dict[str, DocumentMetadata] = {}

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str],
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        metadata = DocumentMetadata(
            ci_id=ci.ci_id, document_type="Policy", current_version=current_version,
            approval_status=approval_status, next_review_date=next_review_date,
            document_url=document_url,
        )
        self._metadata[ci.ci_id] = metadata
        return metadata

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential",
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        metadata = DocumentMetadata(
            ci_id=ci.ci_id, document_type="Certificate", current_version=current_version,
            expiry_date=expiry_date, confidentiality_level=confidentiality_level,
            document_url=document_url,
        )
        self._metadata[ci.ci_id] = metadata
        return metadata

    def get_metadata(self, ci_id: str) -> DocumentMetadata:
        if ci_id not in self._metadata:
            raise ComplianceStoreError(f"Unknown ciId (no document_metadata row): {ci_id}")
        return self._metadata[ci_id]

    def list_metadata_by_type(self, document_type: str) -> List[DocumentMetadata]:
        matches = [m for m in self._metadata.values() if m.document_type == document_type]
        return sorted(matches, key=lambda m: m.updated_at)


_compliance_store_instance: Optional[ComplianceStore] = None


def get_compliance_store() -> ComplianceStore:
    global _compliance_store_instance
    if _compliance_store_instance is not None:
        return _compliance_store_instance
    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_compliance_store import SqlComplianceStore
            _compliance_store_instance = SqlComplianceStore()
            logging.info("get_compliance_store: using SqlComplianceStore (AZURE_SQL_SERVER is set)")
            return _compliance_store_instance
        except Exception:
            logging.exception(
                "get_compliance_store: AZURE_SQL_SERVER is set but SqlComplianceStore "
                "failed to initialise. Falling back to InMemoryComplianceStore."
            )
    _compliance_store_instance = InMemoryComplianceStore()
    return _compliance_store_instance
