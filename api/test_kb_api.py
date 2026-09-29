
"""
Offline tests for kb_api.py's pure request-parsing and response-building
logic (HD-045/046). Uses InMemoryKbStore as the store fixture — no live
database or Azure Functions host required.
"""
import json
from kb_store import InMemoryKbStore
from kb_api import (
    parse_search_query,
    build_article_summary,
    build_search_response,
    parse_feedback_request,
    submit_feedback,
    build_feedback_response,
    SearchValidationError,
    FeedbackRequestValidationError,
    ArticleNotFoundError,
)

# ---------------------------------------------------------------------------
# HD-045: GET /api/kb/search?query=
# ---------------------------------------------------------------------------
print("=== Test 1 (HD-045): parse_search_query returns the validated, trimmed query ===")
assert parse_search_query({"query": "  password  "}) == "password"
print("PASS — query parsed and whitespace-stripped\n")

print("=== Test 2 (HD-045): parse_search_query raises SearchValidationError when query is missing ===")
try:
    parse_search_query({})
    raise AssertionError("Expected SearchValidationError")
except SearchValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 3 (HD-045): parse_search_query raises SearchValidationError for a blank/whitespace query ===")
try:
    parse_search_query({"query": "   "})
    raise AssertionError("Expected SearchValidationError")
except SearchValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

store = InMemoryKbStore()

print("=== Test 4 (HD-045): build_search_response wraps matched results with query/count/results ===")
matches = store.search_articles("password")
response = build_search_response(matches, "password")
assert response["query"] == "password"
assert response["count"] == len(matches)
assert response["results"][0]["title"] == matches[0].title
print(f"PASS — response correctly wrapped: count={response['count']}\n")

print("=== Test 5 (HD-045): build_search_response returns an EMPTY results list, not an error, for zero matches ===")
empty_response = build_search_response([], "xyznonexistent")
assert empty_response["count"] == 0
assert empty_response["results"] == []
print("PASS — empty result correctly represented, matching HD-045's core acceptance criterion\n")

print("=== Test 6: build_article_summary produces the expected shape ===")
summary = build_article_summary(matches[0])
assert set(summary.keys()) == {"articleId", "title", "body", "category", "rank", "createdAt"}
print(f"PASS — summary shape correct: {sorted(summary.keys())}\n")

# ---------------------------------------------------------------------------
# HD-046: POST /api/kb/feedback
# ---------------------------------------------------------------------------
print("=== Test 7 (HD-046): parse_feedback_request accepts a valid body with boolean helpful=true ===")
body = json.dumps({"articleId": "abc-123", "helpful": True}).encode("utf-8")
parsed = parse_feedback_request(body)
assert parsed["articleId"] == "abc-123"
assert parsed["helpful"] is True
assert parsed["sessionId"] is None
print(f"PASS — parsed: {parsed}\n")

print("=== Test 8 (HD-046): parse_feedback_request accepts helpful as the string 'Yes' or 'No' (case-insensitive) ===")
body_yes = json.dumps({"articleId": "abc-123", "helpful": "yes"}).encode("utf-8")
assert parse_feedback_request(body_yes)["helpful"] is True
body_no = json.dumps({"articleId": "abc-123", "helpful": "NO"}).encode("utf-8")
assert parse_feedback_request(body_no)["helpful"] is False
print("PASS — both 'yes' and 'NO' string forms correctly normalized to booleans\n")

print("=== Test 9 (HD-046): parse_feedback_request accepts an optional sessionId ===")
body = json.dumps({"articleId": "abc-123", "helpful": True, "sessionId": "sess-1"}).encode("utf-8")
parsed = parse_feedback_request(body)
assert parsed["sessionId"] == "sess-1"
print(f"PASS — sessionId correctly passed through: {parsed['sessionId']}\n")

print("=== Test 10 (HD-046): parse_feedback_request rejects a missing articleId ===")
try:
    parse_feedback_request(json.dumps({"helpful": True}).encode("utf-8"))
    raise AssertionError("Expected FeedbackRequestValidationError")
except FeedbackRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 11 (HD-046): parse_feedback_request rejects a missing/invalid helpful value ===")
for bad_body in (
    json.dumps({"articleId": "abc-123"}).encode("utf-8"),
    json.dumps({"articleId": "abc-123", "helpful": "maybe"}).encode("utf-8"),
    json.dumps({"articleId": "abc-123", "helpful": 123}).encode("utf-8"),
):
    try:
        parse_feedback_request(bad_body)
        raise AssertionError(f"Expected FeedbackRequestValidationError for {bad_body!r}")
    except FeedbackRequestValidationError:
        pass
print("PASS — missing/invalid helpful values all correctly rejected\n")

print("=== Test 12 (HD-046): parse_feedback_request rejects an empty request body ===")
try:
    parse_feedback_request(None)
    raise AssertionError("Expected FeedbackRequestValidationError")
except FeedbackRequestValidationError as e:
    print(f"PASS — correctly rejected: {e}\n")

print("=== Test 13 (HD-046): submit_feedback succeeds for a known article ===")
real_article = store.search_articles("password")[0]
entry = submit_feedback(store, real_article.article_id, "sess-1", True)
assert entry.article_id == real_article.article_id
assert entry.helpful is True
print(f"PASS — feedback submitted: {entry.feedback_id}\n")

print("=== Test 14 (HD-046): submit_feedback raises ArticleNotFoundError for an unknown articleId (maps to 404) ===")
try:
    submit_feedback(store, "not-a-real-article-id", "sess-1", True)
    raise AssertionError("Expected ArticleNotFoundError")
except ArticleNotFoundError as e:
    print(f"PASS — correctly raised, function_app.py maps this to HTTP 404: {e}\n")

print("=== Test 15 (HD-046): build_feedback_response produces the expected shape ===")
response = build_feedback_response(entry)
assert response["status"] == "recorded"
assert response["feedbackId"] == entry.feedback_id
assert response["helpful"] is True
print(f"PASS — response shape correct: {response}\n")

print("=== Test 16 (HD-046): FULL END-TO-END — repeated feedback from the same session both persist ===")
submit_feedback(store, real_article.article_id, "sess-repeat", True)
submit_feedback(store, real_article.article_id, "sess-repeat", False)
all_feedback = store.get_feedback_for_article(real_article.article_id)
repeat_session_entries = [f for f in all_feedback if f.session_id == "sess-repeat"]
assert len(repeat_session_entries) == 2, "Both submissions from 'sess-repeat' must be preserved, not overwritten"
print(f"PASS — {len(repeat_session_entries)} entries preserved for the same repeated session\n")

print("=" * 60)
print("ALL KB API OFFLINE TESTS PASSED")
