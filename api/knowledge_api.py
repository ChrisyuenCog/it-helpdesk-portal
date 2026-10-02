"""
IT Helpdesk Portal — Knowledge Base v2 logic
============================================
Pure, offline-testable functions behind /api/knowledge/*.

Search reuses the tender matcher's normalisation (synonyms, stemming, phrase
runs, stopwords) so "2FA", "two-factor" and "MFA" find the same article, and
results are ranked by keyword phrases, then title, summary and body overlap.

Lifecycle rules mirror the tender answer library:
  * Readers see Approved articles only; editors can see drafts.
  * An article containing "[confirm" cannot be approved.
  * Editing the wording of an Approved article sends it back to Draft and
    bumps the version, so changed guidance is always re-approved.
  * Identity for updatedBy / approvedBy / feedback comes from the sign-in
    token (passed in by function_app.py), never from the request body.
"""
from __future__ import annotations

import datetime
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from knowledge_store import (
    ARTICLE_STATUSES, ARTICLE_TYPES, AUDIENCES, FEEDBACK_REASONS,
    Article, Feedback, SearchLogEntry, new_id,
)
from tender_api import tokens, _contains_run, PLACEHOLDER_MARK

MAX_QUERY = 200
LOW_RATING_MIN_VOTES = 3


class KnowledgeRequestError(Exception):
    """Invalid input; message is safe to show."""


# ---------------------------------------------------------------- search
def score_article(query: str, a: Article) -> float:
    q_list = tokens(query)
    qt = set(q_list)
    if not qt:
        return 0.0
    raw, keyword_hit = 0.0, False
    for kw in a.keywords:
        kt = tokens(kw)
        if len(kt) > 1 and _contains_run(q_list, kt):
            raw += 2.0 + len(kt); keyword_hit = True
        elif len(kt) == 1 and kt[0] in qt:
            raw += 2.0; keyword_hit = True
    title, summary, body = set(tokens(a.title)), set(tokens(a.summary)), set(tokens(a.body))
    raw += 3.0 * len(qt & title) / len(qt)
    raw += 1.5 * len(qt & summary) / len(qt)
    raw += 1.0 * len(qt & body) / len(qt)
    # One shared word is a coincidence, not a match: "annual leave policy" must not
    # find "Leaving CLG". Without a keyword hit, the article must contain at least
    # 60% of the query's words to keep its full score.
    if not keyword_hit and len(qt & (title | summary | body)) / len(qt) < 0.6:
        raw *= 0.5
    return round(raw / 7.0, 3)


def visible(a: Article, include_drafts: bool) -> bool:
    if a.status == "Retired":
        return False
    return include_drafts or a.status == "Approved"


def search(query: str, articles: List[Article], include_drafts: bool, limit: int = 10,
           min_score: float = 0.3) -> List[Tuple[Article, float]]:
    ranked = [(a, score_article(query, a)) for a in articles if visible(a, include_drafts)]
    ranked = [r for r in ranked if r[1] >= min_score]
    ranked.sort(key=lambda r: (-r[1], -r[0].views, r[0].title))
    return ranked[:limit]


def clean_query(raw: Any) -> str:
    q = re.sub(r"\s+", " ", str(raw or "")).strip()[:MAX_QUERY]
    if len(q) < 2:
        raise KnowledgeRequestError("Type at least two characters to search.")
    return q


def build_search_response(query: str, articles: List[Article], include_drafts: bool) -> Tuple[Dict, SearchLogEntry]:
    q = clean_query(query)
    results = search(q, articles, include_drafts)
    body = {"query": q, "count": len(results),
            "results": [{**a.to_api(include_body=False), "score": min(s, 1.0)} for a, s in results]}
    return body, SearchLogEntry(query=q.lower(), result_count=len(results))


def related(article: Article, articles: List[Article], include_drafts: bool, limit: int = 4) -> List[Dict]:
    probe = " ".join([article.title] + article.keywords[:4])
    out = [(a, s) for a, s in search(probe, articles, include_drafts, limit=limit + 1, min_score=0.1)
           if a.article_id != article.article_id]
    if len(out) < limit:
        same = [a for a in articles if a.category == article.category and a.article_id != article.article_id
                and visible(a, include_drafts) and a.article_id not in {x.article_id for x, _ in out}]
        out += [(a, 0) for a in same]
    return [a.to_api(include_body=False) for a, _ in out[:limit]]


# ---------------------------------------------------------------- reading
def rating_summary(article_id: str, feedback: List[Feedback]) -> Dict[str, Any]:
    mine = [f for f in feedback if f.article_id == article_id]
    yes = sum(1 for f in mine if f.helpful)
    return {"helpful": yes, "notHelpful": len(mine) - yes, "votes": len(mine),
            "helpfulPercent": round(100 * yes / len(mine)) if mine else None}


def build_article_response(a: Article, articles: List[Article], feedback: List[Feedback],
                           include_drafts: bool, today: datetime.date) -> Dict:
    if not visible(a, include_drafts):
        raise KnowledgeRequestError("This article is not published.")
    overdue = bool(a.review_date and a.review_date < today.isoformat())
    return {"article": {**a.to_api(), "reviewOverdue": overdue},
            "rating": rating_summary(a.article_id, feedback),
            "related": related(a, articles, include_drafts)}


def build_home_response(articles: List[Article], include_drafts: bool) -> Dict:
    live = [a for a in articles if visible(a, include_drafts)]
    cats = Counter(a.category for a in live)
    summary = lambda a: a.to_api(include_body=False)
    return {
        "categories": [{"name": c, "count": n} for c, n in sorted(cats.items())],
        "popular": [summary(a) for a in sorted((a for a in live if a.views), key=lambda a: (-a.views, a.title))[:6]],
        "recent": [summary(a) for a in sorted(live, key=lambda a: a.updated_at, reverse=True)[:6]],
        "knownIssues": [summary(a) for a in live if a.article_type == "Known issue" and a.status == "Approved"],
        "total": len(live),
    }


def build_category_response(category: str, articles: List[Article], include_drafts: bool) -> Dict:
    items = [a.to_api(include_body=False) for a in articles if a.category == category and visible(a, include_drafts)]
    return {"category": category, "count": len(items), "articles": items}


# ---------------------------------------------------------------- feedback
def parse_feedback(body: Dict, articles_by_id: Dict[str, Article], user: str) -> Feedback:
    aid = str(body.get("articleId") or "")
    if aid not in articles_by_id:
        raise KnowledgeRequestError("Article not found.")
    helpful = body.get("helpful")
    if not isinstance(helpful, bool):
        raise KnowledgeRequestError("Say whether the article helped.")
    reason = body.get("reason") or None
    if not helpful and reason not in FEEDBACK_REASONS:
        raise KnowledgeRequestError("Choose why the article did not help.")
    comment = (str(body.get("comment") or "").strip()[:1000]) or None
    return Feedback(feedback_id=new_id(), article_id=aid, helpful=helpful,
                    reason=None if helpful else reason, comment=comment, user=user)


# ---------------------------------------------------------------- editing
def _slug(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:80]) or "article"


def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = v.split(",")
    if not isinstance(v, list):
        raise KnowledgeRequestError("Keywords and evidence must be lists.")
    return [str(x).strip() for x in v if str(x).strip()][:50]


def apply_edit(body: Dict, existing: Optional[Article], editor: str, existing_ids) -> Article:
    title = str(body.get("title") or "").strip()
    category = str(body.get("category") or "").strip()
    text = str(body.get("body") or "").strip()
    summary = str(body.get("summary") or "").strip()
    if not (title and category and text and summary):
        raise KnowledgeRequestError("Title, summary, category and article body are all required.")
    a_type = str(body.get("articleType") or (existing.article_type if existing else "How-to"))
    if a_type not in ARTICLE_TYPES:
        raise KnowledgeRequestError("Choose a valid article type.")
    audience = str(body.get("audience") or (existing.audience if existing else "All staff"))
    if audience not in AUDIENCES:
        raise KnowledgeRequestError("Choose a valid audience.")
    status = str(body.get("status") or (existing.status if existing else "Draft"))
    if status not in ARTICLE_STATUSES:
        raise KnowledgeRequestError("Status must be Draft, Approved or Retired.")
    if status == "Approved" and (existing is None or existing.status != "Approved"):
        raise KnowledgeRequestError("Use Approve to publish an article.")
    if existing:
        aid = existing.article_id
    else:
        taken, base, n = set(existing_ids), _slug(title), 2
        aid = base
        while aid in taken:
            aid, n = f"{base}-{n}", n + 1
    keywords, evidence = _as_list(body.get("keywords")), _as_list(body.get("evidence"))
    a = Article(
        article_id=aid, title=title[:300], summary=summary[:600], category=category[:120], article_type=a_type,
        body=text[:60000], keywords=keywords, evidence=evidence, audience=audience, status=status,
        owner=str(body.get("owner") or (existing.owner if existing else "IT"))[:200],
        review_date=(str(body.get("reviewDate"))[:10] if body.get("reviewDate") else None),
        version=existing.version if existing else 1, views=existing.views if existing else 0,
        approved_by=existing.approved_by if existing else None, approved_at=existing.approved_at if existing else None,
        updated_by=editor,
    )
    if existing:
        changed = (a.title, a.summary, a.body, a.evidence) != (existing.title, existing.summary, existing.body, existing.evidence)
        if changed:
            a.version = existing.version + 1
            if existing.status == "Approved" and a.status == "Approved":
                a.status, a.approved_by, a.approved_at = "Draft", None, None
    return a


def approve(a: Article, approver: str, now: datetime.datetime) -> Article:
    if a.status == "Retired":
        raise KnowledgeRequestError("A retired article cannot be published.")
    if PLACEHOLDER_MARK in (a.body + a.summary).lower():
        raise KnowledgeRequestError("Replace the [confirm: …] text before publishing this article.")
    a.status, a.approved_by = "Approved", approver
    a.approved_at = now.replace(microsecond=0).isoformat() + "Z"
    a.updated_by = approver
    if not a.review_date:
        a.review_date = (now.date() + datetime.timedelta(days=365)).isoformat()
    return a


# ---------------------------------------------------------------- insights
def build_insights(articles: List[Article], feedback: List[Feedback], searches: List[SearchLogEntry],
                   today: datetime.date) -> Dict:
    live = [a for a in articles if a.status != "Retired"]
    zero = Counter(s.query for s in searches if s.result_count == 0)
    top = Counter(s.query for s in searches)
    ratings = {a.article_id: rating_summary(a.article_id, feedback) for a in live}
    low = sorted([(a, ratings[a.article_id]) for a in live if ratings[a.article_id]["votes"] >= LOW_RATING_MIN_VOTES],
                 key=lambda x: (x[1]["helpfulPercent"], -x[1]["votes"]))
    reasons = Counter(f.reason for f in feedback if not f.helpful and f.reason)
    comments = [{"articleId": f.article_id, "title": next((a.title for a in live if a.article_id == f.article_id), f.article_id),
                 "reason": f.reason, "comment": f.comment, "createdAt": f.created_at}
                for f in sorted(feedback, key=lambda f: f.created_at, reverse=True) if not f.helpful and f.comment][:15]
    total_searches = len(searches)
    return {
        "counts": {s: sum(1 for a in articles if a.status == s) for s in ARTICLE_STATUSES},
        "searches": total_searches,
        "zeroResultRate": round(100 * sum(zero.values()) / total_searches) if total_searches else None,
        "zeroResultSearches": [{"query": q, "count": n} for q, n in zero.most_common(20)],
        "topSearches": [{"query": q, "count": n} for q, n in top.most_common(10)],
        "mostViewed": [{**a.to_api(include_body=False), **ratings[a.article_id]} for a in sorted(live, key=lambda a: -a.views)[:10] if a.views],
        "lowestRated": [{**a.to_api(include_body=False), **r} for a, r in low[:10] if r["helpfulPercent"] is not None and r["helpfulPercent"] < 70],
        "notHelpfulReasons": dict(reasons),
        "recentComments": comments,
        "reviewOverdue": [a.to_api(include_body=False) for a in live if a.status == "Approved" and a.review_date and a.review_date < today.isoformat()],
        "draftsWithPlaceholders": [a.to_api(include_body=False) for a in live if a.status == "Draft" and PLACEHOLDER_MARK in a.body.lower()],
    }
