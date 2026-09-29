
"""
IT Helpdesk Portal — Knowledge Base Store
=============================================
HD-044/045/046: Knowledge Base abstractions. Mirrors cmdb_store.py's exact
pattern (abstract KbStore + dataclasses + InMemoryKbStore fallback +
get_kb_store() singleton) so this batch requires zero new architectural
concepts — same "abstract interface, in-memory fallback, SQL implementation
implements the identical contract" shape as every prior store in this repo.

HD-044 scope note — the seeded top-4 categories:
  The backlog's own acceptance criterion names the exact 4 categories to
  seed and their rank order: "login/password, admin access, certificates,
  course enrolment" — this ordering IS the real CLG ticket-volume ranking
  referenced by the ticket description itself, not a value invented here.
  InMemoryKbStore._seed_top_4_articles() below seeds exactly these 4, in
  this exact order, with `rank` 1-4 matching that ordering. No other
  ticket-volume data source was available or assumed.

HD-046 scope note — feedback is APPEND-ONLY, never an upsert:
  "repeated submissions from the same session do not silently overwrite
  prior feedback" (HD-046's acceptance criterion) means every feedback
  submission — even a duplicate Yes/Yes from the same session on the same
  article — becomes its own new KBFeedbackEntry row. This mirrors
  ApprovalChainEntry's precedent in workflow_store.py: an audit-style log
  of every decision made, not a single mutable "current answer" field.
  Deduplication/analysis of repeat submissions (if ever needed) is left to
  a future reporting query over this append-only log, not to write-time
  logic here.
"""
from __future__ import annotations

import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class KBArticle:
    """HD-044: one Knowledge Base article. `rank` is the 1-based
    ticket-volume ranking from CLG's real helpdesk category data (see
    module docstring) — used only for informational/ordering purposes,
    never for search relevance scoring (HD-045's search is a simple
    keyword match, not a ranked-relevance search engine, per its
    acceptance criterion's literal wording)."""
    article_id: str
    title: str
    body: str
    category: str
    rank: int
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


@dataclass
class KBFeedbackEntry:
    """HD-046: one row per feedback submission. Deliberately has NO
    natural key preventing duplicates — see module docstring for why this
    must be append-only, not an upsert."""
    feedback_id: str
    article_id: str
    session_id: Optional[str]
    helpful: bool
    submitted_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class KbStoreError(Exception):
    pass


class KbStore:
    """Abstract interface. SqlKbStore implements this exact same contract
    — kb_api.py and function_app.py depend only on this, never on a
    specific storage technology. Mirrors cmdb_store.py's CmdbStore
    pattern."""

    def search_articles(self, query: str) -> List[KBArticle]:
        """HD-045. Case-insensitive substring match against EITHER title
        OR body. Returns an empty list (never raises, never None) for a
        query with zero matches — per the acceptance criterion's literal
        wording: 'an unmatched query returns an empty result, not an
        error.'"""
        raise NotImplementedError

    def get_article(self, article_id: str) -> KBArticle:
        raise NotImplementedError

    def create_article(self, title: str, body: str, category: str, rank: int) -> KBArticle:
        raise NotImplementedError

    def append_feedback(self, article_id: str, session_id: Optional[str], helpful: bool) -> KBFeedbackEntry:
        raise NotImplementedError

    def get_feedback_for_article(self, article_id: str) -> List[KBFeedbackEntry]:
        raise NotImplementedError


class InMemoryKbStore(KbStore):
    """Safe fallback when Azure SQL is not configured. Data does not
    persist across Function App restarts. Seeds the real top-4 CLG ticket
    categories (see module docstring) so HD-045/046/047 are provable via
    API calls alone with no manual data entry, matching every prior
    store's seeding precedent."""

    def __init__(self):
        self._articles: Dict[str, KBArticle] = {}
        self._feedback: Dict[str, List[KBFeedbackEntry]] = {}
        self._seed_top_4_articles()

    def _seed_top_4_articles(self) -> None:
        seed_data = [
            (
                "Reset Your Password or Unlock Your Account",
                "If you've forgotten your password or your account is locked, use Self-Service "
                "Password Reset (SSPR) at aka.ms/sspr — no need to contact IT. You'll need at "
                "least one registered authentication method (Microsoft Authenticator, a phone "
                "number, or a security key) for this to work. If you have zero methods registered, "
                "visit the Password / SSPR tile in this portal to register one before you get "
                "locked out.",
                "login-password",
                1,
            ),
            (
                "Request Additional System or Application Access",
                "To request access to a system, folder, or application you don't currently have "
                "permission for, submit a request via your line manager, who will approve access "
                "in line with least-privilege principles. Include the specific system name and "
                "business justification. Admin-level access requests require additional IT "
                "Security sign-off and may take longer to action.",
                "admin-access",
                2,
            ),
            (
                "Understanding IT Security Certificates and Compliance",
                "CLG maintains Cyber Essentials, Cyber Essentials Plus, and a Business Continuity "
                "Plan, each with a renewal/review date tracked centrally. You can view current "
                "certificate status and expiry countdowns under the Certificates tile. If a "
                "certificate is shown as expired or expiring soon and you need documentation for "
                "a client or tender, use the Tender Pack request instead of emailing IT directly.",
                "certificates",
                3,
            ),
            (
                "How to Enrol in a Course via the Learning Platform",
                "Course enrolment is self-service through the Learning Platform. Search for the "
                "course by name, click Enrol, and your progress will sync automatically. If a "
                "course you need isn't listed, or enrolment fails with an error, raise a ticket "
                "with the exact course name and the error message shown.",
                "course-enrolment",
                4,
            ),
        ]
        for title, body, category, rank in seed_data:
            self.create_article(title=title, body=body, category=category, rank=rank)

    def search_articles(self, query: str) -> List[KBArticle]:
        query_lower = query.lower()
        matches = [
            a for a in self._articles.values()
            if query_lower in a.title.lower() or query_lower in a.body.lower()
        ]
        return sorted(matches, key=lambda a: a.rank)

    def get_article(self, article_id: str) -> KBArticle:
        if article_id not in self._articles:
            raise KbStoreError(f"Unknown articleId: {article_id}")
        return self._articles[article_id]

    def create_article(self, title: str, body: str, category: str, rank: int) -> KBArticle:
        article = KBArticle(
            article_id=str(uuid.uuid4()), title=title, body=body, category=category, rank=rank,
        )
        self._articles[article.article_id] = article
        return article

    def append_feedback(self, article_id: str, session_id: Optional[str], helpful: bool) -> KBFeedbackEntry:
        # Validate the article exists BEFORE recording feedback against it —
        # matches the same "validate referenced entity exists" precedent
        # used by append_approval_entry's implicit reliance on a real
        # instance_id elsewhere in this repo.
        self.get_article(article_id)
        entry = KBFeedbackEntry(
            feedback_id=str(uuid.uuid4()), article_id=article_id, session_id=session_id, helpful=helpful,
        )
        self._feedback.setdefault(article_id, []).append(entry)
        return entry

    def get_feedback_for_article(self, article_id: str) -> List[KBFeedbackEntry]:
        return list(self._feedback.get(article_id, []))


# Module-level singleton. NOTE: for InMemoryKbStore, this is not reliable
# across concurrent Flex Consumption worker instances. Once AZURE_SQL_SERVER
# is set, get_kb_store() returns a SqlKbStore instead. Mirrors
# cmdb_store.py's get_cmdb_store() / workflow_store.py's get_store().
_kb_store_instance: Optional[KbStore] = None


def get_kb_store() -> KbStore:
    global _kb_store_instance
    if _kb_store_instance is not None:
        return _kb_store_instance
    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_kb_store import SqlKbStore
            _kb_store_instance = SqlKbStore()
            logging.info("get_kb_store: using SqlKbStore (AZURE_SQL_SERVER is set)")
            return _kb_store_instance
        except Exception:
            logging.exception(
                "get_kb_store: AZURE_SQL_SERVER is set but SqlKbStore failed to "
                "initialise. Falling back to InMemoryKbStore."
            )
    _kb_store_instance = InMemoryKbStore()
    return _kb_store_instance
