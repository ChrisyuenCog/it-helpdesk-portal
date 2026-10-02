"""
IT Helpdesk Portal — SQL Tender Store
=====================================
Durable replacement for InMemoryTenderStore, backed by dbo.tender_answer and
dbo.tender_pack (created by schema_and_seed_tender.sql). Reuses the shared
_build_connection() so it authenticates exactly like the other SQL stores.

Column widths are deliberately generous (NVARCHAR(MAX) for answer text,
keywords, evidence and the pack snapshot): this project has hit
"String or binary data would be truncated" on real data three times.

Every INSERT/UPDATE below lists its target columns and placeholders in the
same order and count; test_sql_tender_store.py checks this statically, the
lesson from the Batch H create_certificate_document() binding bug.
"""
from __future__ import annotations

import json
from typing import List

from sql_workflow_store import _build_connection
from tender_store import TenderAnswer, TenderPack, TenderStore, TenderStoreError

ANSWER_COLUMNS = (
    "answerId, category, question, keywords, answerText, evidence, owner, status, "
    "reviewDate, approvedBy, approvedAt, updatedBy, updatedAt"
)

UPDATE_ANSWER_SQL = (
    "UPDATE dbo.tender_answer SET category = ?, question = ?, keywords = ?, answerText = ?, evidence = ?, "
    "owner = ?, status = ?, reviewDate = ?, approvedBy = ?, approvedAt = ?, updatedBy = ?, "
    "updatedAt = SYSUTCDATETIME() WHERE answerId = ?"
)
INSERT_ANSWER_SQL = (
    "INSERT INTO dbo.tender_answer (answerId, category, question, keywords, answerText, evidence, owner, "
    "status, reviewDate, approvedBy, approvedAt, updatedBy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
INSERT_PACK_SQL = (
    "INSERT INTO dbo.tender_pack (packId, packRef, clientName, bidReference, deadline, preparedBy, "
    "createdAt, summary, snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _iso(value):
    if value is None:
        return None
    s = str(value)
    return s.replace(" ", "T")


def row_to_answer(row) -> TenderAnswer:
    (answer_id, category, question, keywords, answer_text, evidence, owner, status,
     review_date, approved_by, approved_at, updated_by, updated_at) = row
    return TenderAnswer(
        answer_id=answer_id, category=category, question=question,
        keywords=json.loads(keywords or "[]"), answer_text=answer_text, evidence=json.loads(evidence or "[]"),
        owner=owner, status=status, review_date=str(review_date)[:10] if review_date else None,
        approved_by=approved_by, approved_at=_iso(approved_at), updated_by=updated_by, updated_at=_iso(updated_at),
    )


def row_to_pack(row) -> TenderPack:
    pack_id, pack_ref, client_name, bid_reference, deadline, prepared_by, created_at, summary, snapshot = row
    return TenderPack(
        pack_id=pack_id, pack_ref=pack_ref, client_name=client_name, bid_reference=bid_reference,
        deadline=str(deadline)[:10], prepared_by=prepared_by, created_at=_iso(created_at),
        summary=json.loads(summary or "{}"), snapshot=json.loads(snapshot or "{}"),
    )


class SqlTenderStore(TenderStore):
    def list_answers(self, include_retired: bool = False) -> List[TenderAnswer]:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            sql = f"SELECT {ANSWER_COLUMNS} FROM dbo.tender_answer"
            if not include_retired:
                sql += " WHERE status <> 'Retired'"
            sql += " ORDER BY category, question"
            cur.execute(sql)
            return [row_to_answer(tuple(r)) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_answer(self, answer_id: str) -> TenderAnswer:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT {ANSWER_COLUMNS} FROM dbo.tender_answer WHERE answerId = ?", answer_id)
            row = cur.fetchone()
            if not row:
                raise TenderStoreError(f"Answer '{answer_id}' not found.")
            return row_to_answer(tuple(row))
        finally:
            conn.close()

    def upsert_answer(self, a: TenderAnswer) -> TenderAnswer:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                UPDATE_ANSWER_SQL,
                a.category, a.question, json.dumps(a.keywords), a.answer_text, json.dumps(a.evidence),
                a.owner, a.status, a.review_date, a.approved_by, a.approved_at, a.updated_by, a.answer_id,
            )
            if cur.rowcount == 0:
                cur.execute(
                    INSERT_ANSWER_SQL,
                    a.answer_id, a.category, a.question, json.dumps(a.keywords), a.answer_text,
                    json.dumps(a.evidence), a.owner, a.status, a.review_date, a.approved_by, a.approved_at,
                    a.updated_by,
                )
            conn.commit()
        finally:
            conn.close()
        return self.get_answer(a.answer_id)

    def create_pack(self, p: TenderPack) -> TenderPack:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                INSERT_PACK_SQL,
                p.pack_id, p.pack_ref, p.client_name, p.bid_reference, p.deadline, p.prepared_by,
                p.created_at.rstrip("Z"), json.dumps(p.summary), json.dumps(p.snapshot),
            )
            conn.commit()
            return p
        finally:
            conn.close()

    def list_packs(self, limit: int = 50) -> List[TenderPack]:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT TOP (?) packId, packRef, clientName, bidReference, deadline, preparedBy, createdAt, "
                "summary, '{}' FROM dbo.tender_pack ORDER BY createdAt DESC",
                int(limit),
            )
            return [row_to_pack(tuple(r)) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_pack(self, pack_id: str) -> TenderPack:
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT packId, packRef, clientName, bidReference, deadline, preparedBy, createdAt, summary, "
                "snapshot FROM dbo.tender_pack WHERE packId = ?",
                pack_id,
            )
            row = cur.fetchone()
            if not row:
                raise TenderStoreError("Pack not found.")
            return row_to_pack(tuple(row))
        finally:
            conn.close()
