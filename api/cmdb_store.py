
"""
IT Helpdesk Portal — CMDB Store
==================================
HD-003/004: ci_base / ci_relationship abstractions.
HD-019/020/021 (this revision): the store methods that back the 3 generic
CMDB read endpoints — GET /api/cmdb/ci/{ciId}, GET /api/cmdb/ci?class=&owner=,
GET /api/cmdb/relationships?ciId=.

Design principle (matches workflow_store.py exactly): this module defines the
abstract CmdbStore interface + dataclasses + an InMemoryCmdbStore fallback.
sql_cmdb_store.py implements the SAME interface against Azure SQL — the API
layer (cmdb_api.py) and function_app.py depend only on this contract, never
on a specific storage technology.

HD-003 scope note — system-versioned temporal tables:
  ci_base is a SQL Server system-versioned temporal table (see
  sql/schema_hd003_hd004.sql). System-versioning gives an automatic history
  row on every UPDATE with zero application code — CIBase/InMemoryCmdbStore
  therefore expose only the CURRENT row shape (ciId, ciClass, name, status,
  owner, entity, createdAt); the ValidFrom/ValidTo period columns are a SQL
  Server implementation detail of "how history is captured", not part of
  this MVP's read API contract (no backlog item asks for a history endpoint
  yet). This mirrors compute_sla_breached()'s precedent in workflow_store.py
  of keeping computed/implementation-only concerns out of the dataclass
  surface exposed to the rest of the app.

HD-004 scope note — 'user has' relationships and point-in-time queries:
  ci_relationship is ALSO system-versioned (same schema file), so a
  relationship that is later superseded (e.g. a laptop reassigned to a new
  user) still answers "what was true as of a past date" correctly via
  SQL Server's FOR SYSTEM_TIME AS OF, without a second, hand-rolled
  validFrom/validTo bookkeeping scheme. HD-004's acceptance criterion is
  satisfied by SQL Server's own temporal query support at the SQL layer;
  this store's get_relationships_for_ci() always returns the CURRENT state
  (exactly like get_ci()/list_ci() only ever return current CI state) —
  point-in-time historical queries are a data-layer capability already
  proven by the schema, not yet a separate backlog item requiring its own
  Python method.

HD-020/021 traversal design:
  'owner' on GET /api/cmdb/ci?class=&owner= is resolved via ci_relationship,
  NOT via a plain ci_base.owner string match. This matches the backlog's
  literal acceptance wording: "Hardware CIs linked to that user via
  ci_relationship, and no others." A User CI's ciId is the user's UPN for
  MVP purposes (no separate identity-to-CI mapping table exists yet — see
  MVP Specification's CI classes: Hardware, Document; User is an implicit,
  UPN-keyed CI referenced only as a relationship endpoint, never separately
  stored in ci_base, since nothing in the MVP backlog asks for User CIs to
  be independently CRUD-able). list_ci(owner=...) therefore means: "find
  every 'user has' relationship whose fromCiId equals this UPN, then return
  the matching Hardware CIs" — exactly the join HD-020 describes.
  get_relationships_for_ci() is direction-agnostic (matches fromCiId OR
  toCiId) so that querying either the User CI or the Hardware CI side of a
  relationship returns the same row, per HD-021's "Querying a User CI ...
  returns the ... relationship row referencing the correct Hardware CI."
"""
from __future__ import annotations

import os
import uuid
import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class CIBase:
    """HD-003: one row per Configuration Item, regardless of class. The
    'current' view only — see module docstring for why ValidFrom/ValidTo
    system-time period columns are a SQL-layer concern, not part of this
    dataclass."""
    ci_id: str
    ci_class: str  # e.g. "Hardware", "Document"
    name: str
    status: str
    owner: Optional[str] = None  # UPN, informational only — NOT used for HD-020 filtering
    entity: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


@dataclass
class CIRelationship:
    """HD-004: one row per relationship between two CIs, e.g. a 'user has'
    edge from a User CI (ciId = UPN) to a Hardware CI."""
    relationship_id: str
    from_ci_id: str
    to_ci_id: str
    relationship_type: str  # e.g. "user has"
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class CmdbStoreError(Exception):
    pass


class CmdbStore:
    """Abstract interface. SqlCmdbStore implements this exact same contract
    — cmdb_api.py and function_app.py depend only on this, never on a
    specific storage technology. Mirrors workflow_store.py's WorkflowStore
    pattern."""

    def get_ci(self, ci_id: str) -> CIBase:
        raise NotImplementedError

    def list_ci(self, ci_class: Optional[str] = None, owner: Optional[str] = None) -> List[CIBase]:
        """HD-020. If owner is provided, results are restricted to CIs
        reachable via a 'user has' ci_relationship from that owner's UPN
        (see module docstring) — NOT a plain ci_base.owner string match.
        If ci_class is provided, results are further restricted to that
        class. Either, both, or neither filter may be supplied; supplying
        neither returns every CI."""
        raise NotImplementedError

    def create_ci(
        self,
        ci_class: str,
        name: str,
        status: str,
        owner: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> CIBase:
        raise NotImplementedError

    def create_relationship(
        self, from_ci_id: str, to_ci_id: str, relationship_type: str
    ) -> CIRelationship:
        raise NotImplementedError

    def get_relationships_for_ci(self, ci_id: str) -> List[CIRelationship]:
        """HD-021. Direction-agnostic: returns every relationship where
        ci_id appears as EITHER fromCiId OR toCiId, so querying from either
        side of a 'user has' edge returns the same row."""
        raise NotImplementedError


class InMemoryCmdbStore(CmdbStore):
    """Safe fallback when Azure SQL is not configured. Data does not
    persist across Function App restarts. Seeds one demonstration
    User -> Hardware 'user has' relationship, mirroring
    InMemoryWorkflowStore's TEST/TEST_APPROVAL seeding precedent, so the
    end-to-end pattern (HD-019/020/021) is provable via API calls alone
    with no manual data entry."""

    def __init__(self):
        self._cis: Dict[str, CIBase] = {}
        self._relationships: Dict[str, CIRelationship] = {}
        self._seed_demo_data()

    def _seed_demo_data(self) -> None:
        hardware = CIBase(
            ci_id=str(uuid.uuid4()),
            ci_class="Hardware",
            name="Demo Laptop — HD-019/020/021 seed",
            status="InService",
            owner="demo.user@cognitionlearninggroup.com",
            entity="Cognition Learning Group",
        )
        self._cis[hardware.ci_id] = hardware
        relationship = CIRelationship(
            relationship_id=str(uuid.uuid4()),
            from_ci_id="demo.user@cognitionlearninggroup.com",
            to_ci_id=hardware.ci_id,
            relationship_type="user has",
        )
        self._relationships[relationship.relationship_id] = relationship
        logging.info(
            f"InMemoryCmdbStore: seeded demo Hardware CI {hardware.ci_id} "
            f"with a 'user has' relationship from demo.user@cognitionlearninggroup.com"
        )

    def get_ci(self, ci_id: str) -> CIBase:
        if ci_id not in self._cis:
            raise CmdbStoreError(f"Unknown ciId: {ci_id}")
        return self._cis[ci_id]

    def list_ci(self, ci_class: Optional[str] = None, owner: Optional[str] = None) -> List[CIBase]:
        candidates = list(self._cis.values())
        if owner:
            reachable_ci_ids = {
                rel.to_ci_id
                for rel in self._relationships.values()
                if rel.from_ci_id == owner and rel.relationship_type == "user has"
            }
            candidates = [ci for ci in candidates if ci.ci_id in reachable_ci_ids]
        if ci_class:
            candidates = [ci for ci in candidates if ci.ci_class == ci_class]
        return sorted(candidates, key=lambda ci: ci.created_at, reverse=True)

    def create_ci(
        self,
        ci_class: str,
        name: str,
        status: str,
        owner: Optional[str] = None,
        entity: Optional[str] = None,
    ) -> CIBase:
        ci = CIBase(
            ci_id=str(uuid.uuid4()),
            ci_class=ci_class,
            name=name,
            status=status,
            owner=owner,
            entity=entity,
        )
        self._cis[ci.ci_id] = ci
        return ci

    def create_relationship(
        self, from_ci_id: str, to_ci_id: str, relationship_type: str
    ) -> CIRelationship:
        relationship = CIRelationship(
            relationship_id=str(uuid.uuid4()),
            from_ci_id=from_ci_id,
            to_ci_id=to_ci_id,
            relationship_type=relationship_type,
        )
        self._relationships[relationship.relationship_id] = relationship
        return relationship

    def get_relationships_for_ci(self, ci_id: str) -> List[CIRelationship]:
        matches = [
            rel for rel in self._relationships.values()
            if rel.from_ci_id == ci_id or rel.to_ci_id == ci_id
        ]
        return sorted(matches, key=lambda r: r.created_at, reverse=True)


# Module-level singleton. NOTE: for InMemoryCmdbStore, this is not reliable
# across concurrent Flex Consumption worker instances — this is why
# SqlCmdbStore exists. Once AZURE_SQL_SERVER is set, get_cmdb_store()
# returns a SqlCmdbStore instead. Mirrors workflow_store.py's get_store().
_cmdb_store_instance: Optional[CmdbStore] = None


def get_cmdb_store() -> CmdbStore:
    global _cmdb_store_instance
    if _cmdb_store_instance is not None:
        return _cmdb_store_instance
    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_cmdb_store import SqlCmdbStore
            _cmdb_store_instance = SqlCmdbStore()
            logging.info("get_cmdb_store: using SqlCmdbStore (AZURE_SQL_SERVER is set)")
            return _cmdb_store_instance
        except Exception:
            logging.exception(
                "get_cmdb_store: AZURE_SQL_SERVER is set but SqlCmdbStore failed to "
                "initialise. Falling back to InMemoryCmdbStore."
            )
    _cmdb_store_instance = InMemoryCmdbStore()
    return _cmdb_store_instance
