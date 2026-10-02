"""
IT Helpdesk Portal — SQL Knowledge Store (Knowledge Base v2)
============================================================
Backed by dbo.knowledge_article, dbo.knowledge_feedback and
dbo.knowledge_search_log (db/schema_and_seed_knowledge.sql). Uses the shared
_build_connection(). Every INSERT/UPDATE lists as many placeholders as columns;
test_knowledge.py checks this statically (the Batch H binding-bug lesson).
"""
from __future__ import annotations

import json
from typing import List

from sql_workflow_store import _build_connection
from knowledge_store import Article, Feedback, KnowledgeStore, KnowledgeStoreError, SearchLogEntry

COLS = ("articleId, title, summary, category, articleType, body, keywords, evidence, audience, status, owner, "
        "reviewDate, version, views, approvedBy, approvedAt, updatedBy, updatedAt")
UPDATE_SQL = (
    "UPDATE dbo.knowledge_article SET title = ?, summary = ?, category = ?, articleType = ?, body = ?, keywords = ?, "
    "evidence = ?, audience = ?, status = ?, owner = ?, reviewDate = ?, version = ?, approvedBy = ?, approvedAt = ?, "
    "updatedBy = ?, updatedAt = SYSUTCDATETIME() WHERE articleId = ?"
)
INSERT_SQL = (
    "INSERT INTO dbo.knowledge_article (articleId, title, summary, category, articleType, body, keywords, evidence, "
    "audience, status, owner, reviewDate, version, approvedBy, approvedAt, updatedBy) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
FEEDBACK_SQL = (
    "INSERT INTO dbo.knowledge_feedback (feedbackId, articleId, helpful, reason, comment, userName) VALUES (?, ?, ?, ?, ?, ?)"
)
SEARCH_SQL = "INSERT INTO dbo.knowledge_search_log (query, resultCount) VALUES (?, ?)"


def _iso(v):
    return None if v is None else str(v).replace(" ", "T")


def row_to_article(r) -> Article:
    (aid, title, summary, category, a_type, body, keywords, evidence, audience, status, owner,
     review_date, version, views, approved_by, approved_at, updated_by, updated_at) = r
    return Article(article_id=aid, title=title, summary=summary, category=category, article_type=a_type, body=body,
                   keywords=json.loads(keywords or "[]"), evidence=json.loads(evidence or "[]"), audience=audience,
                   status=status, owner=owner, review_date=str(review_date)[:10] if review_date else None,
                   version=int(version or 1), views=int(views or 0), approved_by=approved_by,
                   approved_at=_iso(approved_at), updated_by=updated_by, updated_at=_iso(updated_at))


class SqlKnowledgeStore(KnowledgeStore):
    def _q(self, sql, *params, fetch=None, commit=False):
        conn = _build_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, *params)
            result = cur.fetchall() if fetch == "all" else cur.fetchone() if fetch == "one" else cur.rowcount
            if commit:
                conn.commit()
            return result
        finally:
            conn.close()

    def list_articles(self, include_retired: bool = False) -> List[Article]:
        sql = f"SELECT {COLS} FROM dbo.knowledge_article" + ("" if include_retired else " WHERE status <> 'Retired'")
        return [row_to_article(tuple(r)) for r in self._q(sql + " ORDER BY category, title", fetch="all")]

    def get_article(self, article_id: str) -> Article:
        row = self._q(f"SELECT {COLS} FROM dbo.knowledge_article WHERE articleId = ?", article_id, fetch="one")
        if not row:
            raise KnowledgeStoreError("Article not found.")
        return row_to_article(tuple(row))

    def upsert_article(self, a: Article) -> Article:
        common = (a.title, a.summary, a.category, a.article_type, a.body, json.dumps(a.keywords), json.dumps(a.evidence),
                  a.audience, a.status, a.owner, a.review_date, a.version, a.approved_by,
                  a.approved_at.rstrip("Z") if a.approved_at else None, a.updated_by)
        if self._q(UPDATE_SQL, *common, a.article_id, commit=True) == 0:
            self._q(INSERT_SQL, a.article_id, *common, commit=True)
        return self.get_article(a.article_id)

    def increment_views(self, article_id: str) -> None:
        self._q("UPDATE dbo.knowledge_article SET views = views + 1 WHERE articleId = ?", article_id, commit=True)

    def add_feedback(self, fb: Feedback) -> Feedback:
        self._q(FEEDBACK_SQL, fb.feedback_id, fb.article_id, 1 if fb.helpful else 0, fb.reason, fb.comment, fb.user, commit=True)
        return fb

    def list_feedback(self) -> List[Feedback]:
        rows = self._q("SELECT feedbackId, articleId, helpful, reason, comment, userName, createdAt FROM dbo.knowledge_feedback",
                       fetch="all")
        return [Feedback(feedback_id=r[0], article_id=r[1], helpful=bool(r[2]), reason=r[3], comment=r[4], user=r[5],
                         created_at=_iso(r[6])) for r in rows]

    def log_search(self, entry: SearchLogEntry) -> None:
        self._q(SEARCH_SQL, entry.query[:400], int(entry.result_count), commit=True)

    def list_search_log(self, since_days: int = 90) -> List[SearchLogEntry]:
        rows = self._q("SELECT query, resultCount, createdAt FROM dbo.knowledge_search_log "
                       "WHERE createdAt >= DATEADD(day, -?, SYSUTCDATETIME())", int(since_days), fetch="all")
        return [SearchLogEntry(query=r[0], result_count=int(r[1]), created_at=_iso(r[2])) for r in rows]
