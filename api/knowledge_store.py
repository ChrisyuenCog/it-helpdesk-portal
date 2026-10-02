"""
IT Helpdesk Portal — Knowledge Base v2 store
============================================
Commercial-grade knowledge base: articles with a governed lifecycle (Draft,
Approved, Retired), owners, review dates, versions and policy evidence;
structured feedback; and a search log that powers the zero-result report.

*** Why new tables rather than changing dbo.kb_article ***
Same regression-avoidance rule as every batch in this project: the HD-044–047
tables, endpoints (/api/kb/search, /api/kb/feedback) and tests are left exactly
as they are. v2 lives in dbo.knowledge_article, dbo.knowledge_feedback and
dbo.knowledge_search_log, created by db/schema_and_seed_knowledge.sql.

Privacy: the search log stores the query text and result count only, never
who searched. Feedback stores the signed-in user, as it may need follow-up.
"""
from __future__ import annotations

import copy
import datetime
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from knowledge_seed import SEED_ARTICLES

ARTICLE_STATUSES = ("Draft", "Approved", "Retired")
ARTICLE_TYPES = ("How-to", "Troubleshooting", "Known issue", "Policy summary")
AUDIENCES = ("All staff", "IT only")
FEEDBACK_REASONS = ("outdated", "unclear", "did_not_solve", "other")


class KnowledgeStoreError(Exception):
    pass


def _now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class Article:
    article_id: str
    title: str
    summary: str
    category: str
    article_type: str
    body: str
    keywords: List[str]
    evidence: List[str]
    audience: str = "All staff"
    status: str = "Draft"
    owner: str = "IT"
    review_date: Optional[str] = None
    version: int = 1
    views: int = 0
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: str = field(default_factory=_now)

    def to_api(self, include_body: bool = True) -> Dict:
        d = {
            "articleId": self.article_id, "title": self.title, "summary": self.summary, "category": self.category,
            "articleType": self.article_type, "keywords": list(self.keywords), "evidence": list(self.evidence),
            "audience": self.audience, "status": self.status, "owner": self.owner, "reviewDate": self.review_date,
            "version": self.version, "views": self.views, "approvedBy": self.approved_by,
            "approvedAt": self.approved_at, "updatedBy": self.updated_by, "updatedAt": self.updated_at,
        }
        if include_body:
            d["body"] = self.body
        return d


@dataclass
class Feedback:
    feedback_id: str
    article_id: str
    helpful: bool
    reason: Optional[str]
    comment: Optional[str]
    user: Optional[str]
    created_at: str = field(default_factory=_now)


@dataclass
class SearchLogEntry:
    query: str
    result_count: int
    created_at: str = field(default_factory=_now)


def article_from_seed(s: Dict) -> Article:
    return Article(
        article_id=s["articleId"], title=s["title"], summary=s["summary"], category=s["category"],
        article_type=s["articleType"], body=s["body"], keywords=list(s["keywords"]), evidence=list(s["evidence"]),
        audience=s.get("audience", "All staff"),
    )


class KnowledgeStore:
    def list_articles(self, include_retired: bool = False) -> List[Article]: raise NotImplementedError
    def get_article(self, article_id: str) -> Article: raise NotImplementedError
    def upsert_article(self, article: Article) -> Article: raise NotImplementedError
    def increment_views(self, article_id: str) -> None: raise NotImplementedError
    def add_feedback(self, fb: Feedback) -> Feedback: raise NotImplementedError
    def list_feedback(self) -> List[Feedback]: raise NotImplementedError
    def log_search(self, entry: SearchLogEntry) -> None: raise NotImplementedError
    def list_search_log(self, since_days: int = 90) -> List[SearchLogEntry]: raise NotImplementedError


class InMemoryKnowledgeStore(KnowledgeStore):
    def __init__(self, seed: bool = True):
        self._articles: Dict[str, Article] = {}
        self._feedback: List[Feedback] = []
        self._searches: List[SearchLogEntry] = []
        if seed:
            for s in SEED_ARTICLES:
                a = article_from_seed(s)
                self._articles[a.article_id] = a

    def list_articles(self, include_retired: bool = False) -> List[Article]:
        items = [copy.deepcopy(a) for a in self._articles.values() if include_retired or a.status != "Retired"]
        return sorted(items, key=lambda a: (a.category.lower(), a.title.lower()))

    def get_article(self, article_id: str) -> Article:
        if article_id not in self._articles:
            raise KnowledgeStoreError("Article not found.")
        return copy.deepcopy(self._articles[article_id])

    def upsert_article(self, article: Article) -> Article:
        article.updated_at = _now()
        self._articles[article.article_id] = copy.deepcopy(article)
        return copy.deepcopy(article)

    def increment_views(self, article_id: str) -> None:
        if article_id in self._articles:
            self._articles[article_id].views += 1

    def add_feedback(self, fb: Feedback) -> Feedback:
        self._feedback.append(copy.deepcopy(fb))
        return fb

    def list_feedback(self) -> List[Feedback]:
        return [copy.deepcopy(f) for f in self._feedback]

    def log_search(self, entry: SearchLogEntry) -> None:
        self._searches.append(copy.deepcopy(entry))

    def list_search_log(self, since_days: int = 90) -> List[SearchLogEntry]:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=since_days)).isoformat()
        return [copy.deepcopy(s) for s in self._searches if s.created_at >= cutoff]


def new_id() -> str:
    return str(uuid.uuid4())


_instance: Optional[KnowledgeStore] = None


def get_knowledge_store() -> KnowledgeStore:
    global _instance
    if _instance is not None:
        return _instance
    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_knowledge_store import SqlKnowledgeStore
            _instance = SqlKnowledgeStore()
            logging.info("get_knowledge_store: using SqlKnowledgeStore")
            return _instance
        except Exception:
            logging.exception("get_knowledge_store: SqlKnowledgeStore failed to initialise; using in-memory.")
    _instance = InMemoryKnowledgeStore()
    return _instance
