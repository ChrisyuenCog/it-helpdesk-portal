
"""
IT Helpdesk Portal — SQL-backed Knowledge Base Store
=======================================================
HD-044/045/046: durable Azure SQL-backed implementation of the KbStore
interface, backed by dbo.kb_article and dbo.kb_feedback (see
sql/schema_and_seed_kb.sql).

Reuses _build_connection() from sql_workflow_store.py rather than
duplicating Managed Identity / access-token connection logic — same
precedent established by sql_cmdb_store.py.

HD-045 search implementation note: uses SQL LIKE with wrapping wildcards
against both title and body columns. At MVP data volumes (4 seeded
articles, a handful more expected before this becomes a real bottleneck),
a full-text index is not warranted — this mirrors sql_workflow_store.py's
own precedent of choosing the simplest correct implementation for MVP
scale rather than pre-optimising for a volume this project doesn't have
yet.
"""
from __future__ import annotations

import logging
from typing import Optional, List

from kb_store import KBArticle, KBFeedbackEntry, KbStore, KbStoreError
from sql_workflow_store import _build_connection


def row_to_article(row: tuple) -> KBArticle:
    """row: (articleId, title, body, category, rank, createdAt)"""
    article_id, title, body, category, rank, created_at = row
    return KBArticle(
        article_id=str(article_id), title=title, body=body, category=category,
        rank=int(rank), created_at=str(created_at),
    )


def row_to_feedback(row: tuple) -> KBFeedbackEntry:
    """row: (feedbackId, articleId, sessionId, helpful, submittedAt)"""
    feedback_id, article_id, session_id, helpful, submitted_at = row
    return KBFeedbackEntry(
        feedback_id=str(feedback_id), article_id=str(article_id), session_id=session_id,
        helpful=bool(helpful), submitted_at=str(submitted_at),
    )


def build_insert_feedback_params(article_id: str, session_id: Optional[str], helpful: bool) -> tuple:
    return (article_id, session_id, helpful)


class SqlKbStore(KbStore):
    """Durable replacement for InMemoryKbStore. Same interface, backed by
    dbo.kb_article and dbo.kb_feedback (see sql/schema_and_seed_kb.sql)."""

    def search_articles(self, query: str) -> List[KBArticle]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            like_pattern = f"%{query}%"
            cursor.execute(
                "SELECT articleId, title, body, category, rank, createdAt "
                "FROM dbo.kb_article "
                "WHERE title LIKE ? OR body LIKE ? "
                "ORDER BY rank ASC",
                like_pattern, like_pattern,
            )
            rows = cursor.fetchall()
            return [row_to_article(tuple(r)) for r in rows]
        finally:
            conn.close()

    def get_article(self, article_id: str) -> KBArticle:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT articleId, title, body, category, rank, createdAt "
                "FROM dbo.kb_article WHERE articleId = ?",
                article_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise KbStoreError(f"Unknown articleId: {article_id}")
            return row_to_article(tuple(row))
        finally:
            conn.close()

    def create_article(self, title: str, body: str, category: str, rank: int) -> KBArticle:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO dbo.kb_article (title, body, category, rank) "
                "OUTPUT INSERTED.articleId, INSERTED.title, INSERTED.body, "
                "INSERTED.category, INSERTED.rank, INSERTED.createdAt "
                "VALUES (?, ?, ?, ?)",
                title, body, category, rank,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_article(tuple(row))
        finally:
            conn.close()

    def append_feedback(self, article_id: str, session_id: Optional[str], helpful: bool) -> KBFeedbackEntry:
        # Validate the article exists first (raises KbStoreError -> 404 in
        # function_app.py if unknown), same precedent as InMemoryKbStore.
        self.get_article(article_id)
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            params = build_insert_feedback_params(article_id, session_id, helpful)
            cursor.execute(
                "INSERT INTO dbo.kb_feedback (articleId, sessionId, helpful) "
                "OUTPUT INSERTED.feedbackId, INSERTED.articleId, INSERTED.sessionId, "
                "INSERTED.helpful, INSERTED.submittedAt "
                "VALUES (?, ?, ?)",
                *params,
            )
            row = cursor.fetchone()
            conn.commit()
            return row_to_feedback(tuple(row))
        finally:
            conn.close()

    def get_feedback_for_article(self, article_id: str) -> List[KBFeedbackEntry]:
        conn = _build_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT feedbackId, articleId, sessionId, helpful, submittedAt "
                "FROM dbo.kb_feedback WHERE articleId = ? ORDER BY submittedAt DESC",
                article_id,
            )
            rows = cursor.fetchall()
            return [row_to_feedback(tuple(r)) for r in rows]
        finally:
            conn.close()
