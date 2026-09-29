
"""
IT Helpdesk Portal — SQL-backed CMDB Store
=============================================
HD-003/004: durable Azure SQL-backed implementation of the CmdbStore
interface, backed by dbo.ci_base and dbo.ci_relationship (see
sql/schema_hd003_hd004.sql — both are SQL Server system-versioned temporal
tables, giving automatic history rows on UPDATE with zero application code,
matching HD-003's acceptance criterion exactly).
HD-019/020/021: the 3 read methods behind the generic CMDB endpoints.

Reuses _build_connection() from sql_workflow_store.py rather than
duplicating Managed Identity / access-token connection logic — same
"single source of truth for how we connect" principle already established
between workflow_store.py and this module's sibling.

Query design note (matches sql_workflow_store.py's get_instances_pending_role
precedent): list_ci(owner=...) and get_relationships_for_ci() both query
dbo.ci_relationship directly with simple indexed-friendly WHERE clauses —
there is no need for the "fetch broadly, filter in Python" pattern used for
workflow_definition's JSON transitions column, because ci_relationship's
fromCiId/toCiId/relationshipType are plain relational columns, not JSON.
"""
from __future__ import annotations

import logging
from typing import Optional, List

from cmdb_store import CIBase, CIRelationship, CmdbStore, CmdbStoreError
from sql_workflow_store import _build_connection  # single source of truth for connections


# ---------------------------------------------------------------------------
# Pure logic — no DB connection required. Tested offline in
# test_cmdb_store.py without needing pyodbc, azure-identity, or a live
# database, exactly like sql_workflow_store.py's row_to_instance() etc.
# ---------------------------------------------------------------------------
def row_to_ci(row: tuple) -> CIBase:
    """row: (ciId, ciClass, name, status, owner, entity, createdAt)"""
    ci_id, ci_class, name, status, owner, entity, created_at = row
    return CIBase(
        ci_id=str(ci_id),
        ci_class=ci_class,
        name=name,
        status=status,
        owner=owner,
        entity=entity,
        created_at=str(created_at),
    )


def row_to_relationship(row: tuple) -> CIRelationship:
    """row: (relationshipId, fromCiId, toCiId, relationshipType, createdAt)"""
    relationship_id, from_ci_id, to_ci_id, relationship_type, created_at = row
    return CIRelationship(
        relationship_id=str(relationship_id),
        from_ci_id=str(from_ci_id),
        to_ci_id=str(to_ci_id),
        relationship_type=relationship_type,
        created_at=str(created_at),
    )


def build_insert_ci_params(
    ci_class: str, name: str, status: str, owner: Optional[str], entity: Optional[str]
) -> tuple:
    return (ci_class, name, status, owner, entity)


def build_insert_relationship_params(
    from_ci_id: str, to_ci_id: str, relationship_type: str
) -> tuple:
    return (from_ci_id, to_ci_id, relationship_type)


# ---------------------------------------------------------------------------
# SqlCmdbStore — connection-dependent, validated manually against the real
# Azure SQL Database once provisioned, per runbook.md Section 6 (same
# precedent as SqlWorkflowStore).
# ---------------------------------------------------------------------------
class SqlCmdbStore(CmdbStore):
    """Durable replacement for InMemoryCmdbStore. Same interface, backed by
    dbo.ci_base and dbo.ci_relationship (see sql/schema_hd003_hd004.sql)."""

    def get_ci(self, ci_id: str) -> CIBase:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ciId, ciClass, name, status, owner, entity, createdAt "
                "FROM dbo.ci_base WHERE ciId = ?",
                ci_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise CmdbStoreError(f"Unknown ciId: {ci_id}")
            return row_to_ci(tuple(row))
        finally:
            conn.close()

    def list_ci(self, ci_class: Optional[str] = None, owner: Optional[str] = None) -> List[CIBase]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            if owner:
                # HD-020: owner filtering is resolved via ci_relationship's
                # 'user has' edges, NOT a plain ci_base.owner match — see
                # cmdb_store.py's module docstring for the full rationale.
                query = (
                    "SELECT cb.ciId, cb.ciClass, cb.name, cb.status, cb.owner, cb.entity, cb.createdAt "
                    "FROM dbo.ci_base cb "
                    "JOIN dbo.ci_relationship cr ON cr.toCiId = cb.ciId "
                    "WHERE cr.fromCiId = ? AND cr.relationshipType = 'user has'"
                )
                params = [owner]
                if ci_class:
                    query += " AND cb.ciClass = ?"
                    params.append(ci_class)
                query += " ORDER BY cb.createdAt DESC"
                cursor.execute(query, *params)
            else:
                if ci_class:
                    cursor.execute(
                        "SELECT ciId, ciClass, name, status, owner, entity, createdAt "
                        "FROM dbo.ci_base WHERE ciClass = ? ORDER BY createdAt DESC",
                        ci_class,
                    )
                else:
                    cursor.execute(
                        "SELECT ciId, ciClass, name, status, owner, entity, createdAt "
                        "FROM dbo.ci_base ORDER BY createdAt DESC",
                    )
            rows = cursor.fetchall()
            return [row_to_ci(tuple(r)) for r in rows]
        finally:
            conn.close()

    def create_ci(
        self,
        ci_class: str,
        name: str,
        status: str,
        owner: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> CIBase:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_insert_ci_params(ci_class, name, status, owner, entity)
            cursor.execute(
                "INSERT INTO dbo.ci_base (ciClass, name, status, owner, entity) "
                "OUTPUT INSERTED.ciId, INSERTED.ciClass, INSERTED.name, INSERTED.status, "
                "INSERTED.owner, INSERTED.entity, INSERTED.createdAt "
                "VALUES (?, ?, ?, ?, ?)",
                *params,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_ci(tuple(row))
        finally:
            conn.close()

    def create_relationship(
        self, from_ci_id: str, to_ci_id: str, relationship_type: str
    ) -> CIRelationship:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_insert_relationship_params(from_ci_id, to_ci_id, relationship_type)
            cursor.execute(
                "INSERT INTO dbo.ci_relationship (fromCiId, toCiId, relationshipType) "
                "OUTPUT INSERTED.relationshipId, INSERTED.fromCiId, INSERTED.toCiId, "
                "INSERTED.relationshipType, INSERTED.createdAt "
                "VALUES (?, ?, ?)",
                *params,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_relationship(tuple(row))
        finally:
            conn.close()

    def get_relationships_for_ci(self, ci_id: str) -> List[CIRelationship]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT relationshipId, fromCiId, toCiId, relationshipType, createdAt "
                "FROM dbo.ci_relationship WHERE fromCiId = ? OR toCiId = ? "
                "ORDER BY createdAt DESC",
                ci_id, ci_id,
            )
            rows = cursor.fetchall()
            return [row_to_relationship(tuple(r)) for r in rows]
        finally:
            conn.close()
