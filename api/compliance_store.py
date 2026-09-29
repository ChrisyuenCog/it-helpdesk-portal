
"""
IT Helpdesk Portal — Policy & Compliance Store
==================================================
HD-048/049: models POL_001-006 and CE/CE+ as Document CIs, so policy
version/approval/review tracking and certificate expiry countdowns
participate in the same CMDB and SLA-style machinery as every other CI
(Hardware included) — per the MVP Specification's explicit design intent
for Section 7 (Policy & Compliance Hub).

*** CRITICAL DESIGN NOTE — why this is a SEPARATE table, not new ci_base
columns ***
HD-048's acceptance criterion asks for 'currentVersion, approvalStatus and
nextReviewDate' per Document CI; HD-049 adds 'expiryDate' for certificates.
None of these exist as ci_base columns (Batch A's schema: ciId, ciClass,
name, status, owner, entity, createdAt only). Rather than repeating the
EXACT regression class already hit once this session (HD-028 adding
requesterUpn to workflow_instance broke a hidden test file that unpacked
the old 6-tuple shape), this metadata lives in a BRAND NEW table
(dbo.document_metadata, one row per ciId) that ci_base's own row shape,
SELECT statements, and row_to_ci() parser NEVER need to change to support.
Batch A's CmdbStore/SqlCmdbStore interface is used completely unmodified
to create the underlying Document CI itself — this module only ADDS a
sibling table and its own store, joined by ciId at the point of use.

HD-049 confidentiality note: 'confidentialityLevel' distinguishes a
Document CI holding just the CERTIFICATE OF ASSURANCE (proof of a passed
assessment — informational, "Confidential" is sufficient) from any
underlying CE+ SCOPING material (network diagrams naming in-scope systems,
which the backlog explicitly calls out as "Strictly Confidential"). This
module seeds only the former (the certificates themselves); no scoping
documents were provided as a source, so none are seeded — see this
project's "must not implement from assumptions" standing rule.

HD-051 core logic: compute_days_remaining() is a pure, offline-testable
function mirroring workflow_store.py's compute_sla_breached() precedent
exactly — a negative value correctly represents an already-overdue/expired
certificate, matching HD-051's literal acceptance criterion ("correctly
showing a negative/overdue value if a certificate's expiryDate has
passed").
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
    """HD-048/049: one row per Document CI, joined by ci_id. Distinct from
    CIBase itself — see module docstring for why this is a separate table
    rather than new ci_base columns."""
    ci_id: str
    document_type: str  # "Policy" | "Certificate"
    current_version: Optional[str] = None
    approval_status: Optional[str] = None
    next_review_date: Optional[str] = None  # ISO date string, policies only
    expiry_date: Optional[str] = None        # ISO date string, certificates only
    confidentiality_level: str = "Internal"
    updated_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


def compute_days_remaining(expiry_date: Optional[str], as_of: Optional[datetime.date] = None) -> Optional[int]:
    """HD-051: pure, offline-testable. Returns the number of whole days
    between `as_of` (defaults to today, UTC) and expiry_date. A NEGATIVE
    result correctly represents an already-expired/overdue certificate —
    this is the literal acceptance criterion, not an error state. Returns
    None (not 0, not an error) if expiry_date itself is None, e.g. for a
    Document CI that is a policy, not a certificate, and therefore has no
    expiry concept at all."""
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
    contract. Mirrors every other *Store class in this repo — abstract
    interface, InMemory fallback, get_*_store() singleton."""

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str], owner: Optional[str] = None,
    ) -> DocumentMetadata:
        raise NotImplementedError

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential", owner: Optional[str] = None,
    ) -> DocumentMetadata:
        raise NotImplementedError

    def get_metadata(self, ci_id: str) -> DocumentMetadata:
        raise NotImplementedError

    def list_metadata_by_type(self, document_type: str) -> List[DocumentMetadata]:
        raise NotImplementedError


class InMemoryComplianceStore(ComplianceStore):
    """Safe fallback when Azure SQL is not configured. Data does not
    persist across Function App restarts."""

    def __init__(self):
        self._metadata: Dict[str, DocumentMetadata] = {}

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str], owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        metadata = DocumentMetadata(
            ci_id=ci.ci_id, document_type="Policy", current_version=current_version,
            approval_status=approval_status, next_review_date=next_review_date,
        )
        self._metadata[ci.ci_id] = metadata
        return metadata

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential", owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        metadata = DocumentMetadata(
            ci_id=ci.ci_id, document_type="Certificate", current_version=current_version,
            expiry_date=expiry_date, confidentiality_level=confidentiality_level,
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
