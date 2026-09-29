
"""
IT Helpdesk Portal — SQL-backed Policy & Compliance Store
============================================================
HD-048/049: durable Azure SQL-backed implementation of the ComplianceStore
interface, backed by dbo.document_metadata. Reuses _build_connection()
from sql_workflow_store.py.

THIS REVISION: row_to_metadata() now parses documentUrl as its 8th column
(appended, not inserted in the middle — same "append, don't insert in the
middle" precedent as HD-028's requesterUpn addition to workflow_instance,
so any caller still unpacking the pre-existing 8-tuple shape elsewhere
would fail loudly rather than silently reading the wrong field).

*** BUG FIX (found and corrected while making this revision) ***
create_certificate_document()'s INSERT statement previously specified 6
target columns (ciId, documentType, currentVersion, expiryDate,
confidentialityLevel, documentUrl-equivalent slot) but only 5 VALUES
placeholders — the 'Certificate' literal for documentType was missing
entirely, which would have caused a genuine SQL Server binding error
("Column name or number of supplied values does not match table
definition") the first time this Python method was actually called
against live SQL. This was never caught because every certificate row
seeded so far was inserted via raw SQL scripts, not through this method
— the live smoke test only exercised the READ path
(list_metadata_by_type -> SELECT), never this WRITE path. Fixed by
adding the missing 'Certificate' literal; create_policy_document's
equivalent INSERT was checked and was already correct.
"""
from __future__ import annotations

from typing import Optional, List

from cmdb_store import CmdbStore
from compliance_store import DocumentMetadata, ComplianceStore, ComplianceStoreError
from sql_workflow_store import _build_connection


def row_to_metadata(row: tuple) -> DocumentMetadata:
    """row: (ciId, documentType, currentVersion, approvalStatus, nextReviewDate, expiryDate, confidentialityLevel, documentUrl, updatedAt)"""
    ci_id, document_type, current_version, approval_status, next_review_date, expiry_date, confidentiality_level, document_url, updated_at = row
    return DocumentMetadata(
        ci_id=str(ci_id), document_type=document_type, current_version=current_version,
        approval_status=approval_status,
        next_review_date=str(next_review_date)[:10] if next_review_date else None,
        expiry_date=str(expiry_date)[:10] if expiry_date else None,
        confidentiality_level=confidentiality_level or "Internal",
        document_url=document_url,
        updated_at=str(updated_at),
    )


class SqlComplianceStore(ComplianceStore):
    """Durable replacement for InMemoryComplianceStore."""

    def create_policy_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        approval_status: str, next_review_date: Optional[str],
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.document_metadata "
                "(ciId, documentType, currentVersion, approvalStatus, nextReviewDate, confidentialityLevel, documentUrl) "
                "OUTPUT INSERTED.ciId, INSERTED.documentType, INSERTED.currentVersion, "
                "INSERTED.approvalStatus, INSERTED.nextReviewDate, INSERTED.expiryDate, "
                "INSERTED.confidentialityLevel, INSERTED.documentUrl, INSERTED.updatedAt "
                "VALUES (?, 'Policy', ?, ?, ?, 'Internal', ?)",
                ci.ci_id, current_version, approval_status, next_review_date, document_url,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_metadata(tuple(row))
        finally:
            conn.close()

    def create_certificate_document(
        self, cmdb_store: CmdbStore, title: str, current_version: str,
        expiry_date: str, confidentiality_level: str = "Confidential",
        document_url: Optional[str] = None, owner: Optional[str] = None,
    ) -> DocumentMetadata:
        ci = cmdb_store.create_ci(ci_class="Document", name=title, status="Active", owner=owner, entity="Cognition Learning Group")
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.document_metadata "
                "(ciId, documentType, currentVersion, expiryDate, confidentialityLevel, documentUrl) "
                "OUTPUT INSERTED.ciId, INSERTED.documentType, INSERTED.currentVersion, "
                "INSERTED.approvalStatus, INSERTED.nextReviewDate, INSERTED.expiryDate, "
                "INSERTED.confidentialityLevel, INSERTED.documentUrl, INSERTED.updatedAt "
                "VALUES (?, 'Certificate', ?, ?, ?, ?)",
                ci.ci_id, current_version, expiry_date, confidentiality_level, document_url,
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
                "nextReviewDate, expiryDate, confidentialityLevel, documentUrl, updatedAt "
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
                "nextReviewDate, expiryDate, confidentialityLevel, documentUrl, updatedAt "
                "FROM dbo.document_metadata WHERE documentType = ? ORDER BY updatedAt ASC",
                document_type,
            )
            rows = cursor.fetchall()
            return [row_to_metadata(tuple(r)) for r in rows]
        finally:
            conn.close()
