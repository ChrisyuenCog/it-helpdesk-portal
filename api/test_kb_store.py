
"""
Offline tests for kb_store.py (InMemoryKbStore + dataclasses) and the PURE
logic in sql_kb_store.py (row parsing, parameter-building). None of these
require pyodbc, azure-identity, or a live database connection.
"""
import os

assert "AZURE_SQL_SERVER" not in os.environ, \
    "Test assumes AZURE_SQL_SERVER is not set in this environment"

from kb_store import InMemoryKbStore, KbStoreError, get_kb_store, KBArticle, KBFeedbackEntry
from sql_kb_store import row_to_article, row_to_feedback, build_insert_feedback_params

print("=== Test 0: get_kb_store() falls back to InMemoryKbStore when AZURE_SQL_SERVER is unset ===")
store = get_kb_store()
assert isinstance(store, InMemoryKbStore), f"Expected InMemoryKbStore, got {type(store)}"
print("PASS — get_kb_store() correctly falls back when SQL is not configured\n")

print("=== Test 1 (HD-044): InMemoryKbStore seeds exactly the 4 real CLG top ticket categories ===")
store = InMemoryKbStore()
all_articles = store.search_articles("")  # empty string matches everything via substring logic
assert len(all_articles) == 4, f"Expected 4 seeded articles, got {len(all_articles)}"
categories = {a.category for a in all_articles}
assert categories == {"login-password", "admin-access", "certificates", "course-enrolment"}, \
    f"Unexpected categories: {categories}"
print(f"PASS — 4 articles seeded: {sorted(categories)}\n")

print("=== Test 2 (HD-044): seeded articles are ranked 1-4 matching the backlog's stated category order ===")
ranks = sorted(a.rank for a in all_articles)
assert ranks == [1, 2, 3, 4], f"Expected ranks 1-4, got {ranks}"
rank_1_article = next(a for a in all_articles if a.rank == 1)
assert rank_1_article.category == "login-password", "Rank 1 must be login/password per the backlog's stated order"
print(f"PASS — ranks correctly assigned 1-4, rank 1 = {rank_1_article.category}\n")

print("=== Test 3 (HD-045): search_articles matches a keyword present in an article's TITLE ===")
results = store.search_articles("Password")
assert len(results) >= 1
assert any("password" in a.title.lower() for a in results)
print(f"PASS — {len(results)} article(s) matched on title keyword\n")

print("=== Test 4 (HD-045): search_articles matches a keyword present ONLY in an article's BODY ===")
# "aka.ms/sspr" appears in the password article's body, not its title.
results = store.search_articles("aka.ms/sspr")
assert len(results) == 1
assert results[0].category == "login-password"
print(f"PASS — body-only keyword correctly matched: {results[0].title}\n")

print("=== Test 5 (HD-045): search_articles is case-insensitive ===")
results_lower = store.search_articles("certificate")
results_upper = store.search_articles("CERTIFICATE")
assert len(results_lower) == len(results_upper) and len(results_lower) >= 1
print(f"PASS — case-insensitive match confirmed: {len(results_lower)} result(s) either way\n")

print("=== Test 6 (HD-045): search_articles returns an EMPTY list for an unmatched query, not an error ===")
results = store.search_articles("xyznonexistentkeyword12345")
assert results == []
print("PASS — empty list correctly returned, not an error, for zero matches\n")

print("=== Test 7 (HD-045): search_articles results are ordered by rank ascending ===")
results = store.search_articles("")
ranks_in_order = [a.rank for a in results]
assert ranks_in_order == sorted(ranks_in_order), f"Expected ascending rank order, got {ranks_in_order}"
print(f"PASS — results correctly ordered by rank: {ranks_in_order}\n")

print("=== Test 8: get_article returns the correct article by ID ===")
target = all_articles[0]
fetched = store.get_article(target.article_id)
assert fetched.article_id == target.article_id
print(f"PASS — fetched article matches: {fetched.title}\n")

print("=== Test 9: get_article raises KbStoreError for an unknown articleId (no silent failure) ===")
try:
    store.get_article("not-a-real-article-id")
    raise AssertionError("Expected KbStoreError, none was raised")
except KbStoreError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 10 (HD-046): append_feedback raises KbStoreError for feedback against an unknown article ===")
try:
    store.append_feedback("not-a-real-article-id", "session-1", True)
    raise AssertionError("Expected KbStoreError, none was raised")
except KbStoreError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 11 (HD-046): append_feedback / get_feedback_for_article round-trip correctly ===")
entry = store.append_feedback(target.article_id, "session-1", True)
assert entry.article_id == target.article_id
assert entry.session_id == "session-1"
assert entry.helpful is True
chain = store.get_feedback_for_article(target.article_id)
assert len(chain) == 1
assert chain[0].feedback_id == entry.feedback_id
print(f"PASS — feedback recorded and retrieved: {entry.feedback_id}\n")

print("=== Test 12 (HD-046): repeated submissions from the SAME session do NOT overwrite prior feedback ===")
entry2 = store.append_feedback(target.article_id, "session-1", False)  # same session, different answer
chain = store.get_feedback_for_article(target.article_id)
assert len(chain) == 2, "Both the original and the repeat submission must both be preserved as separate rows"
assert entry.feedback_id != entry2.feedback_id
print(f"PASS — {len(chain)} feedback entries preserved for the same session, no overwrite occurred\n")

print("=== Test 13: get_feedback_for_article returns an empty list for an article with no feedback yet ===")
fresh_article = store.create_article("Test Article", "Test body content", "test-category", 99)
assert store.get_feedback_for_article(fresh_article.article_id) == []
print("PASS — empty list correctly returned, not an error, for an article with no feedback\n")

# ---------------------------------------------------------------------------
# sql_kb_store.py pure logic — row parsing / parameter building
# ---------------------------------------------------------------------------
print("=== Test 14: row_to_article parses a kb_article row correctly ===")
article_row = (
    "11111111-1111-1111-1111-111111111111",
    "SQL Test Article",
    "SQL test body",
    "test-category",
    5,
    "2026-09-29 10:00:00",
)
parsed = row_to_article(article_row)
assert isinstance(parsed, KBArticle)
assert parsed.article_id == "11111111-1111-1111-1111-111111111111"
assert parsed.rank == 5
print(f"PASS — parsed article: {parsed.title}\n")

print("=== Test 15: row_to_feedback parses a kb_feedback row correctly ===")
feedback_row = (
    "22222222-2222-2222-2222-222222222222",
    "11111111-1111-1111-1111-111111111111",
    "session-abc",
    1,  # SQL bit column often surfaces as int
    "2026-09-29 10:05:00",
)
parsed_fb = row_to_feedback(feedback_row)
assert isinstance(parsed_fb, KBFeedbackEntry)
assert parsed_fb.helpful is True
print(f"PASS — parsed feedback: helpful={parsed_fb.helpful}\n")

print("=== Test 16: row_to_feedback correctly parses helpful=False (SQL bit 0) ===")
feedback_row_false = (
    "33333333-3333-3333-3333-333333333333",
    "11111111-1111-1111-1111-111111111111",
    None,  # sessionId can be NULL
    0,
    "2026-09-29 10:06:00",
)
parsed_fb_false = row_to_feedback(feedback_row_false)
assert parsed_fb_false.helpful is False
assert parsed_fb_false.session_id is None
print("PASS — helpful=False and NULL sessionId both correctly parsed\n")

print("=== Test 17: build_insert_feedback_params produces the right parameter order ===")
params = build_insert_feedback_params("article-1", "session-1", True)
assert params == ("article-1", "session-1", True)
print(f"PASS — insert feedback params: {params}\n")

print("=" * 60)
print("ALL KB STORE OFFLINE TESTS PASSED")
print("(Connection-dependent SqlKbStore methods still require manual")
print(" validation against the live Azure SQL Database — see runbook.md Section 6.)")
