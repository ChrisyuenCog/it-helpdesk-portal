
"""
Offline tests for cmdb_store.py (InMemoryCmdbStore + dataclasses) and the
PURE logic in sql_cmdb_store.py (row parsing, parameter-building). None of
these require pyodbc, azure-identity, or a live database connection —
same "connection-dependent methods validated manually per runbook.md
Section 6" precedent as test_sql_workflow_store.py.
"""
import os

# Guard against accidentally running against a real SqlCmdbStore in CI.
assert "AZURE_SQL_SERVER" not in os.environ, \
    "Test assumes AZURE_SQL_SERVER is not set in this environment"

from cmdb_store import (
    InMemoryCmdbStore,
    CmdbStoreError,
    get_cmdb_store,
    CIBase,
    CIRelationship,
)
from sql_cmdb_store import (
    row_to_ci,
    row_to_relationship,
    build_insert_ci_params,
    build_insert_relationship_params,
)

# ---------------------------------------------------------------------------
# get_cmdb_store() fallback behaviour
# ---------------------------------------------------------------------------
print("=== Test 0: get_cmdb_store() falls back to InMemoryCmdbStore when AZURE_SQL_SERVER is unset ===")
store = get_cmdb_store()
assert isinstance(store, InMemoryCmdbStore), f"Expected InMemoryCmdbStore, got {type(store)}"
print("PASS — get_cmdb_store() correctly falls back when SQL is not configured\n")

# ---------------------------------------------------------------------------
# InMemoryCmdbStore — seeded demo data (HD-019/020/021 provability)
# ---------------------------------------------------------------------------
print("=== Test 1: InMemoryCmdbStore seeds one demo Hardware CI with a 'user has' relationship ===")
store = InMemoryCmdbStore()
seeded_cis = store.list_ci()
assert len(seeded_cis) == 1, f"Expected exactly 1 seeded CI, got {len(seeded_cis)}"
seeded_ci = seeded_cis[0]
assert seeded_ci.ci_class == "Hardware"
assert seeded_ci.owner == "demo.user@cognitionlearninggroup.com"
print(f"PASS — seeded CI: {seeded_ci.ci_id} ({seeded_ci.ci_class}, owner={seeded_ci.owner})\n")

print("=== Test 2: get_ci returns the correct CI by ID (HD-019) ===")
fetched = store.get_ci(seeded_ci.ci_id)
assert fetched.ci_id == seeded_ci.ci_id
assert fetched.name == seeded_ci.name
print(f"PASS — fetched CI matches: {fetched.ci_id}\n")

print("=== Test 3: get_ci raises CmdbStoreError for an unknown ciId (no silent failure) ===")
try:
    store.get_ci("not-a-real-ci-id")
    raise AssertionError("Expected CmdbStoreError, none was raised")
except CmdbStoreError as e:
    print(f"PASS — correctly raised: {e}\n")

print("=== Test 4 (HD-020): list_ci(ci_class='Hardware') returns the seeded Hardware CI ===")
hardware_cis = store.list_ci(ci_class="Hardware")
assert len(hardware_cis) == 1
assert hardware_cis[0].ci_id == seeded_ci.ci_id
print(f"PASS — {len(hardware_cis)} Hardware CI(s) returned\n")

print("=== Test 5 (HD-020): list_ci(ci_class='Document') returns nothing (no Document CIs seeded) ===")
document_cis = store.list_ci(ci_class="Document")
assert document_cis == []
print("PASS — empty list returned, not an error, for a class with no matching CIs\n")

print("=== Test 6 (HD-020): list_ci(owner=...) resolves via ci_relationship, not ci_base.owner ===")
owner_cis = store.list_ci(owner="demo.user@cognitionlearninggroup.com")
assert len(owner_cis) == 1
assert owner_cis[0].ci_id == seeded_ci.ci_id
print(f"PASS — owner filter correctly resolved via 'user has' relationship: {owner_cis[0].ci_id}\n")

print("=== Test 7 (HD-020): list_ci(owner=...) for an unrelated user returns nothing ===")
unrelated_owner_cis = store.list_ci(owner="someone.else@cognitionlearninggroup.com")
assert unrelated_owner_cis == []
print("PASS — no false-positive matches for an unrelated owner\n")

print("=== Test 8 (HD-020): list_ci(ci_class=, owner=) combines both filters (AND, not OR) ===")
combined = store.list_ci(ci_class="Hardware", owner="demo.user@cognitionlearninggroup.com")
assert len(combined) == 1
combined_mismatch = store.list_ci(ci_class="Document", owner="demo.user@cognitionlearninggroup.com")
assert combined_mismatch == [], "A class that doesn't match the owned CI's class should return nothing"
print("PASS — combined class+owner filtering behaves as a logical AND\n")

print("=== Test 9 (HD-021): get_relationships_for_ci is direction-agnostic ===")
from_side = store.get_relationships_for_ci("demo.user@cognitionlearninggroup.com")
to_side = store.get_relationships_for_ci(seeded_ci.ci_id)
assert len(from_side) == 1
assert len(to_side) == 1
assert from_side[0].relationship_id == to_side[0].relationship_id
assert from_side[0].relationship_type == "user has"
assert from_side[0].to_ci_id == seeded_ci.ci_id
print(f"PASS — same relationship {from_side[0].relationship_id} returned from either side\n")

print("=== Test 10 (HD-021): get_relationships_for_ci returns an empty list for a CI with none ===")
new_ci = store.create_ci(ci_class="Document", name="Policy Doc", status="Active")
assert store.get_relationships_for_ci(new_ci.ci_id) == []
print("PASS — empty list returned, not an error, for a CI with no relationships yet\n")

print("=== Test 11: create_ci / create_relationship correctly add new rows (regression check) ===")
new_hardware = store.create_ci(ci_class="Hardware", name="Second Laptop", status="InService", owner="another.user@cognitionlearninggroup.com")
new_relationship = store.create_relationship(
    from_ci_id="another.user@cognitionlearninggroup.com",
    to_ci_id=new_hardware.ci_id,
    relationship_type="user has",
)
assert store.get_ci(new_hardware.ci_id).ci_id == new_hardware.ci_id
assert new_relationship in store.get_relationships_for_ci(new_hardware.ci_id)
all_hardware = store.list_ci(ci_class="Hardware")
assert len(all_hardware) == 2, f"Expected 2 Hardware CIs after adding one, got {len(all_hardware)}"
print(f"PASS — new CI {new_hardware.ci_id} and relationship {new_relationship.relationship_id} correctly added\n")

# ---------------------------------------------------------------------------
# sql_cmdb_store.py pure logic — row parsing / parameter building
# ---------------------------------------------------------------------------
print("=== Test 12: row_to_ci parses a ci_base row correctly ===")
ci_row = (
    "11111111-1111-1111-1111-111111111111",
    "Hardware",
    "SQL Test Laptop",
    "InService",
    "sql.test@cognitionlearninggroup.com",
    "Cognition Education UK Limited",
    "2026-09-25 15:00:00",
)
parsed_ci = row_to_ci(ci_row)
assert isinstance(parsed_ci, CIBase)
assert parsed_ci.ci_id == "11111111-1111-1111-1111-111111111111"
assert parsed_ci.ci_class == "Hardware"
assert parsed_ci.owner == "sql.test@cognitionlearninggroup.com"
print(f"PASS — parsed CI: {parsed_ci.ci_id} ({parsed_ci.ci_class})\n")

print("=== Test 13: row_to_ci handles NULL owner/entity correctly ===")
ci_row_nulls = (
    "22222222-2222-2222-2222-222222222222",
    "Document",
    "SQL Test Doc",
    "Active",
    None,
    None,
    "2026-09-25 15:00:00",
)
parsed_ci_nulls = row_to_ci(ci_row_nulls)
assert parsed_ci_nulls.owner is None
assert parsed_ci_nulls.entity is None
print("PASS — NULL owner/entity correctly become None, not an error\n")

print("=== Test 14: row_to_relationship parses a ci_relationship row correctly ===")
rel_row = (
    "33333333-3333-3333-3333-333333333333",
    "sql.test@cognitionlearninggroup.com",
    "11111111-1111-1111-1111-111111111111",
    "user has",
    "2026-09-25 15:00:01",
)
parsed_rel = row_to_relationship(rel_row)
assert isinstance(parsed_rel, CIRelationship)
assert parsed_rel.from_ci_id == "sql.test@cognitionlearninggroup.com"
assert parsed_rel.to_ci_id == "11111111-1111-1111-1111-111111111111"
assert parsed_rel.relationship_type == "user has"
print(f"PASS — parsed relationship: {parsed_rel.relationship_id}\n")

print("=== Test 15: build_insert_ci_params produces the right parameter order ===")
params = build_insert_ci_params("Hardware", "New Laptop", "InService", "owner@x.com", "CLG")
assert params == ("Hardware", "New Laptop", "InService", "owner@x.com", "CLG")
print(f"PASS — insert CI params: {params}\n")

print("=== Test 16: build_insert_relationship_params produces the right parameter order ===")
rel_params = build_insert_relationship_params("owner@x.com", "some-ci-id", "user has")
assert rel_params == ("owner@x.com", "some-ci-id", "user has")
print(f"PASS — insert relationship params: {rel_params}\n")

print("=" * 60)
print("ALL CMDB STORE OFFLINE TESTS PASSED")
print("(Connection-dependent SqlCmdbStore methods still require manual")
print(" validation against the live Azure SQL Database — see runbook.md Section 6.)")
