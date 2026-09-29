
"""
Offline tests for cmdb_api.py's pure request-parsing and response-building
logic (HD-019/020/021). Uses InMemoryCmdbStore as the store fixture — no
live database or Azure Functions host required, matching
test_workflow_list_api.py's pattern for its sibling list endpoints.
"""
from cmdb_store import InMemoryCmdbStore
from cmdb_api import (
    parse_ci_id,
    load_ci_view,
    build_ci_summary,
    parse_list_ci_query,
    build_ci_list_response,
    parse_relationships_query,
    build_relationship_summary,
    build_relationships_response,
    CiNotFoundError,
    RelationshipsValidationError,
)

# ---------------------------------------------------------------------------
# HD-019: GET /api/cmdb/ci/{ciId}
# ---------------------------------------------------------------------------
print("=== Test 1 (HD-019): parse_ci_id returns the route parameter when present ===")
assert parse_ci_id("some-ci-id") == "some-ci-id"
print("PASS — valid route parameter returned unchanged\n")

print("=== Test 2 (HD-019): parse_ci_id raises CiNotFoundError when the route parameter is missing ===")
try:
    parse_ci_id(None)
    raise AssertionError("Expected CiNotFoundError, none was raised")
except CiNotFoundError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 3 (HD-019): load_ci_view returns the correct shape for a known CI ===")
store = InMemoryCmdbStore()
seeded_ci = store.list_ci()[0]
view = load_ci_view(store, seeded_ci.ci_id)
assert view["ciId"] == seeded_ci.ci_id
assert view["ciClass"] == "Hardware"
assert view["owner"] == "demo.user@cognitionlearninggroup.com"
assert set(view.keys()) == {"ciId", "ciClass", "name", "status", "owner", "entity", "createdAt"}
print(f"PASS — view correctly shaped: {sorted(view.keys())}\n")

print("=== Test 4 (HD-019): load_ci_view raises CiNotFoundError for an unknown ciId (maps to 404) ===")
try:
    load_ci_view(store, "not-a-real-ci-id")
    raise AssertionError("Expected CiNotFoundError, none was raised")
except CiNotFoundError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 5: build_ci_summary produces the same shape used by both HD-019 and HD-020 ===")
summary = build_ci_summary(seeded_ci)
assert summary == view
print("PASS — single-CI view (HD-019) and list-row shape (HD-020) are identical, by construction\n")

# ---------------------------------------------------------------------------
# HD-020: GET /api/cmdb/ci?class=&owner=
# ---------------------------------------------------------------------------
print("=== Test 6 (HD-020): parse_list_ci_query returns both filters when present ===")
filters = parse_list_ci_query({"class": "Hardware", "owner": "demo.user@cognitionlearninggroup.com"})
assert filters == {"ci_class": "Hardware", "owner": "demo.user@cognitionlearninggroup.com"}
print(f"PASS — filters parsed: {filters}\n")

print("=== Test 7 (HD-020): parse_list_ci_query returns None for filters when absent (no validation error) ===")
no_filters = parse_list_ci_query({})
assert no_filters == {"ci_class": None, "owner": None}
print("PASS — an unfiltered query is valid, matching the MVP spec's optional-filter design\n")

print("=== Test 8 (HD-020): parse_list_ci_query treats an empty-string filter the same as absent ===")
empty_filters = parse_list_ci_query({"class": "", "owner": ""})
assert empty_filters == {"ci_class": None, "owner": None}
print("PASS — empty-string query params normalise to None, not an empty-string filter\n")

print("=== Test 9 (HD-020): build_ci_list_response wraps results with class/owner/count/items ===")
cis = store.list_ci(ci_class="Hardware")
response = build_ci_list_response(cis, "Hardware", None)
assert response["class"] == "Hardware"
assert response["owner"] is None
assert response["count"] == len(cis)
assert response["items"][0]["ciId"] == cis[0].ci_id
print(f"PASS — response correctly wrapped: count={response['count']}\n")

print("=== Test 10 (HD-020): build_ci_list_response returns an empty items list, not an error, for zero matches ===")
empty_response = build_ci_list_response([], "Document", None)
assert empty_response["count"] == 0
assert empty_response["items"] == []
print("PASS — empty list correctly represented\n")

# ---------------------------------------------------------------------------
# HD-021: GET /api/cmdb/relationships?ciId=
# ---------------------------------------------------------------------------
print("=== Test 11 (HD-021): parse_relationships_query returns the validated ciId ===")
assert parse_relationships_query({"ciId": " some-ci-id "}) == "some-ci-id"
print("PASS — ciId parsed and whitespace-stripped\n")

print("=== Test 12 (HD-021): parse_relationships_query raises RelationshipsValidationError when ciId is missing ===")
try:
    parse_relationships_query({})
    raise AssertionError("Expected RelationshipsValidationError, none was raised")
except RelationshipsValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 13 (HD-021): parse_relationships_query raises RelationshipsValidationError for an empty/whitespace ciId ===")
try:
    parse_relationships_query({"ciId": "   "})
    raise AssertionError("Expected RelationshipsValidationError, none was raised")
except RelationshipsValidationError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 14 (HD-021): build_relationship_summary / build_relationships_response shape correctly ===")
relationships = store.get_relationships_for_ci(seeded_ci.ci_id)
rel_summary = build_relationship_summary(relationships[0])
assert set(rel_summary.keys()) == {"relationshipId", "fromCiId", "toCiId", "relationshipType", "createdAt"}
rel_response = build_relationships_response(relationships, seeded_ci.ci_id)
assert rel_response["ciId"] == seeded_ci.ci_id
assert rel_response["count"] == 1
assert rel_response["relationships"][0]["relationshipType"] == "user has"
print(f"PASS — relationships response correctly shaped: {rel_response['count']} relationship(s)\n")

print("=== Test 15 (HD-021): build_relationships_response returns an empty list, not an error, for zero relationships ===")
empty_rel_response = build_relationships_response([], "some-ci-with-no-relationships")
assert empty_rel_response["count"] == 0
assert empty_rel_response["relationships"] == []
print("PASS — empty relationships list correctly represented\n")

print("=" * 60)
print("ALL CMDB API OFFLINE TESTS PASSED")
