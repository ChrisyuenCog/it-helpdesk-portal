
"""
IT Helpdesk Portal — SQL-backed Policy & Compliance Store
============================================================
HD-048/049: durable Azure SQL-backed implementation of the ComplianceStore
interface, backed by dbo.document_metadata (see
schema_and_seed_compliance.sql). Reuses _build_connection() from
sql_workflow_store.py — same precedent already established by
sql_cmdb_store.py and sql_kb_store.py.
"""
from __future__ import annotations

from typing import Optional, List

from cmdb_store import CmdbStore
from compliance_store import DocumentMetadata, ComplianceStore, ComplianceStoreError
from sql_workflow_store import _build_connection


def row_to_metadata(row: tuple) -> DocumentMetadata:
    """row: (ciId, documentType, currentVersion, approvalStatus, nextReviewDate, expiryDate, confidentialityLevel, updatedAt)"""
    ci_id, document_type, current_version, approval_status, next_review_date, expiry_date, confidentiality_level, updated_at = row
    return DocumentMetadata(
        ci_id=str(ci_id), document_type=document_type, current_version=current_version,
        approval_status=approval_status,
        next_review_date=str(next_review_date)[:10] if next_review_date else None,
        expiry_date=str(expiry_date)[:10] if expiry_date else None,
        confidentiality_level=confidentiality_level or "Internal",
        updated_at=str(updated_at),
    )


class SqlComplianceStore(ComplianceStore):
    """Durable replacement for InMemoryComplianceStore. Same interface,
    backed by dbo.document_metadata, joined to dbo.ci_base (Batch A) by
    ciId at read time."""

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str], owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.document_metadata "
                "(ciId, documentType, currentVersion, approvalStatus, nextReviewDate, confidentialityLevel) "
                "OUTPUT INSERTED.ciId, INSERTED.documentType, INSERTED.currentVersion, "
                "INSERTED.approvalStatus, INSERTED.nextReviewDate, INSERTED.expiryDate, "
                "INSERTED.confidentialityLevel, INSERTED.updatedAt "
                "VALUES (?, 'Policy', ?, ?, ?, 'Internal')",
                ci.ci_id, current_version, approval_status, next_review_date,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_metadata(tuple(row))
        finally:
            conn.close()

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential", owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.document_metadata "
                "(ciId, documentType, currentVersion, expiryDate, confidentialityLevel) "
                "OUTPUT INSERTED.ciId, INSERTED.documentType, INSERTED.currentVersion, "
                "INSERTED.approvalStatus, INSERTED.nextReviewDate, INSERTED.expiryDate, "
                "INSERTED.confidentialityLevel, INSERTED.updatedAt "
                "VALUES (?, 'Certificate', ?, ?, ?)",
                ci.ci_id, current_version, expiry_date, confidentiality_level,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_metadata(tuple(row))
        finally:
            conn.close()

    def get_metadata(self, ci_id: str) -> DocumentMetadata:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ciId, documentType, currentVersion, approvalStatus, "
                "nextReviewDate, expiryDate, confidentialityLevel, updatedAt "
                "FROM dbo.document_metadata WHERE ciId = ?",
                ci_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise ComplianceStoreError(f"Unknown ciId (no document_metadata row): {ci_id}")
            return row_to_metadata(tuple(row))
        finally:
            conn.close()

    def list_metadata_by_type(self, document_type: str) -> List[DocumentMetadata]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ciId, documentType, currentVersion, approvalStatus, "
                "nextReviewDate, expiryDate, confidentialityLevel, updatedAt "
                "FROM dbo.document_metadata WHERE documentType = ? ORDER BY updatedAt ASC",
                document_type,
            )
            rows = cursor.fetchall()
            return [row_to_metadata(tuple(r)) for r in rows]
        finally:
            conn.close()
