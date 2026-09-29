
"""
IT Helpdesk Portal — Knowledge Base API request/response logic (HD-045/046)
==============================================================================
Pure request-validation and response-building logic for:
  GET /api/kb/search?query=      (HD-045)
  POST /api/kb/feedback          (HD-046)
Separated from the Azure Functions HTTP triggers in function_app.py, same
"logic lives in its own module, HTTP trigger is just plumbing" pattern used
by every other endpoint in this repo, so this ticket is offline-testable
without a live Function host or a live database.
"""
from __future__ import annotations
import json
from typing import Optional, Dict, Any, List

from kb_store import KbStore, KBArticle, KBFeedbackEntry, KbStoreError
from workflow_api import build_error_response  # reused for a single, consistent error shape


class SearchValidationError(Exception):
    """Raised when the required ?query= parameter is missing or blank —
    maps to HTTP 400 in function_app.py."""
    pass


class FeedbackRequestValidationError(Exception):
    """Raised for any problem with the incoming feedback request body's
    own SHAPE — maps to HTTP 400 in function_app.py."""
    pass


class ArticleNotFoundError(Exception):
    """Raised when a feedback submission references an articleId that
    does not exist — maps to HTTP 404 in function_app.py. Kept as its own
    exception (rather than reusing KbStoreError directly) so the HTTP
    trigger's except clause reads the same way as every other endpoint's
    404 mapping in this repo (CiNotFoundError, InstanceNotFoundError)."""
    pass


# ---------------------------------------------------------------------------
# HD-045: GET /api/kb/search?query=
# ---------------------------------------------------------------------------
def parse_search_query(query_params: Dict[str, str]) -> str:
    """Returns the validated, whitespace-stripped query string, or raises
    SearchValidationError. A missing/blank ?query= is a caller error (400)
    — distinct from a well-formed query that simply matches nothing, which
    is a valid 200 response with an empty result list (see
    build_search_response below)."""
    query = query_params.get("query")
    if not query or not query.strip():
        raise SearchValidationError(
            "'query' query parameter is required, e.g. ?query=password"
        )
    return query.strip()


def build_article_summary(article: KBArticle) -> Dict[str, Any]:
    return {
        "articleId": article.article_id,
        "title": article.title,
        "body": article.body,
        "category": article.category,
        "rank": article.rank,
        "createdAt": article.created_at,
    }


def build_search_response(articles: List[KBArticle], query: str) -> Dict[str, Any]:
    """HD-045's core acceptance criterion: an unmatched query returns an
    empty result, not an error — this function has no error path at all;
    an empty `articles` list simply produces `count: 0, results: []`."""
    return {
        "query": query,
        "count": len(articles),
        "results": [build_article_summary(a) for a in articles],
    }


# ---------------------------------------------------------------------------
# HD-046: POST /api/kb/feedback
# ---------------------------------------------------------------------------
def _normalize_helpful(raw_value: Any) -> Optional[bool]:
    """Accepts either a native JSON boolean (true/false) or a "Yes"/"No"
    string (case-insensitive) for the 'helpful' field, since the backlog's
    own wording ("Was this helpful? Yes/No responses") suggests a UI might
    reasonably send either shape. Returns None for anything else, which
    parse_feedback_request treats as a validation error — this function
    itself never raises, keeping it a pure, simple normalizer."""
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        lowered = raw_value.strip().lower()
        if lowered == "yes":
            return True
        if lowered == "no":
            return False
    return None


def parse_feedback_request(raw_body: Optional[bytes]) -> Dict[str, Any]:
    """Validates the request body shape. Does not check whether articleId
    refers to a real article — that is a separate, subsequent step
    (load_feedback_target below), matching this repo's established "each
    distinct failure reason maps to its own error" principle."""
    if not raw_body:
        raise FeedbackRequestValidationError("Request body is required and must be JSON.")
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise FeedbackRequestValidationError(f"Request body must be valid JSON: {e}")
    if not isinstance(body, dict):
        raise FeedbackRequestValidationError("Request body must be a JSON object.")
    article_id = body.get("articleId")
    if not article_id or not isinstance(article_id, str):
        raise FeedbackRequestValidationError("'articleId' is required and must be a non-empty string.")
    helpful = _normalize_helpful(body.get("helpful"))
    if helpful is None:
        raise FeedbackRequestValidationError(
            "'helpful' is required and must be a boolean (true/false) or the string 'Yes'/'No'."
        )
    session_id = body.get("sessionId")
    if session_id is not None and not isinstance(session_id, str):
        raise FeedbackRequestValidationError("'sessionId', if provided, must be a string.")
    return {"articleId": article_id, "helpful": helpful, "sessionId": session_id}


def submit_feedback(store: KbStore, article_id: str, session_id: Optional[str], helpful: bool) -> KBFeedbackEntry:
    """The single entry point this ticket's HTTP trigger calls. Raises
    ArticleNotFoundError (-> 404) if articleId is unknown; any other
    KbStoreError is left to propagate as-is, matching this repo's
    precedent of surfacing unexpected store errors rather than masking
    them behind a misleading 404."""
    try:
        return store.append_feedback(article_id, session_id, helpful)
    except KbStoreError as e:
        raise ArticleNotFoundError(str(e))


def build_feedback_response(entry: KBFeedbackEntry) -> Dict[str, Any]:
    return {
        "status": "recorded",
        "feedbackId": entry.feedback_id,
        "articleId": entry.article_id,
        "helpful": entry.helpful,
        "submittedAt": entry.submitted_at,
    }
