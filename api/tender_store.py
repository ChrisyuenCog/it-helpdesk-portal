"""
IT Helpdesk Portal — Tender Pack Store (Batch I, HD-054–058 widened)
====================================================================
Two record types:
  * TenderAnswer — one approved (or draft) answer in the answer library,
    pointing at Policy & Compliance records as its evidence.
  * TenderPack — an issued pack. Stored as an immutable JSON snapshot of
    exactly what was sent (answers, evidence status, who prepared it), so a
    later audit or bid challenge sees the pack as issued, even after the
    library or a certificate has changed.

Same pattern as every other store in this project: abstract interface,
InMemory implementation for offline tests (seeded from tender_seed.py),
SQL implementation selected when AZURE_SQL_SERVER is set.
"""
from __future__ import annotations

import copy
import datetime
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tender_seed import SEED_ANSWERS

ANSWER_STATUSES = ("Draft", "Approved", "Retired")


class TenderStoreError(Exception):
    pass


def _now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class TenderAnswer:
    answer_id: str
    category: str
    question: str
    keywords: List[str]
    answer_text: str
    evidence: List[str]
    owner: str = "IT Security"
    status: str = "Draft"
    review_date: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: str = field(default_factory=_now)

    def to_api(self) -> Dict[str, Any]:
        return {
            "answerId": self.answer_id, "category": self.category, "question": self.question,
            "keywords": list(self.keywords), "answerText": self.answer_text, "evidence": list(self.evidence),
            "owner": self.owner, "status": self.status, "reviewDate": self.review_date,
            "approvedBy": self.approved_by, "approvedAt": self.approved_at,
            "updatedBy": self.updated_by, "updatedAt": self.updated_at,
        }


@dataclass
class TenderPack:
    pack_id: str
    pack_ref: str
    client_name: str
    bid_reference: Optional[str]
    deadline: str
    prepared_by: str
    created_at: str
    summary: Dict[str, int]
    snapshot: Dict[str, Any]

    def to_list_item(self) -> Dict[str, Any]:
        return {
            "packId": self.pack_id, "packRef": self.pack_ref, "clientName": self.client_name,
            "bidReference": self.bid_reference, "deadline": self.deadline, "preparedBy": self.prepared_by,
            "createdAt": self.created_at, "summary": dict(self.summary),
        }


def answer_from_seed(seed: Dict[str, Any]) -> TenderAnswer:
    return TenderAnswer(
        answer_id=seed["answerId"], category=seed["category"], question=seed["question"],
        keywords=list(seed["keywords"]), answer_text=seed["answerText"], evidence=list(seed["evidence"]),
    )


def make_pack_ref(created: datetime.datetime, pack_id: str) -> str:
    """Human-friendly reference printed on the pack cover, e.g. TP-20261002-4F3A."""
    return f"TP-{created.strftime('%Y%m%d')}-{pack_id.replace('-', '')[:4].upper()}"


class TenderStore:
    def list_answers(self, include_retired: bool = False) -> List[TenderAnswer]:
        raise NotImplementedError

    def get_answer(self, answer_id: str) -> TenderAnswer:
        raise NotImplementedError

    def upsert_answer(self, answer: TenderAnswer) -> TenderAnswer:
        raise NotImplementedError

    def create_pack(self, pack: TenderPack) -> TenderPack:
        raise NotImplementedError

    def list_packs(self, limit: int = 50) -> List[TenderPack]:
        raise NotImplementedError

    def get_pack(self, pack_id: str) -> TenderPack:
        raise NotImplementedError


class InMemoryTenderStore(TenderStore):
    def __init__(self, seed: bool = True):
        self._answers: Dict[str, TenderAnswer] = {}
        self._packs: Dict[str, TenderPack] = {}
        if seed:
            for s in SEED_ANSWERS:
                a = answer_from_seed(s)
                self._answers[a.answer_id] = a

    def list_answers(self, include_retired: bool = False) -> List[TenderAnswer]:
        items = [copy.deepcopy(a) for a in self._answers.values()
                 if include_retired or a.status != "Retired"]
        return sorted(items, key=lambda a: (a.category.lower(), a.question.lower()))

    def get_answer(self, answer_id: str) -> TenderAnswer:
        if answer_id not in self._answers:
            raise TenderStoreError(f"Answer '{answer_id}' not found.")
        return copy.deepcopy(self._answers[answer_id])

    def upsert_answer(self, answer: TenderAnswer) -> TenderAnswer:
        answer.updated_at = _now()
        self._answers[answer.answer_id] = copy.deepcopy(answer)
        return copy.deepcopy(answer)

    def create_pack(self, pack: TenderPack) -> TenderPack:
        if pack.pack_id in self._packs:
            raise TenderStoreError("A pack with this id already exists.")
        self._packs[pack.pack_id] = copy.deepcopy(pack)
        return copy.deepcopy(pack)

    def list_packs(self, limit: int = 50) -> List[TenderPack]:
        packs = sorted(self._packs.values(), key=lambda p: p.created_at, reverse=True)
        return [copy.deepcopy(p) for p in packs[:limit]]

    def get_pack(self, pack_id: str) -> TenderPack:
        if pack_id not in self._packs:
            raise TenderStoreError("Pack not found.")
        return copy.deepcopy(self._packs[pack_id])


_tender_store_instance: Optional[TenderStore] = None


def get_tender_store() -> TenderStore:
    global _tender_store_instance
    if _tender_store_instance is not None:
        return _tender_store_instance
    if os.environ.get("AZURE_SQL_SERVER"):
        try:
            from sql_tender_store import SqlTenderStore
            _tender_store_instance = SqlTenderStore()
            logging.info("get_tender_store: using SqlTenderStore (AZURE_SQL_SERVER is set)")
            return _tender_store_instance
        except Exception:
            logging.exception("get_tender_store: SqlTenderStore failed to initialise; falling back to in-memory.")
    _tender_store_instance = InMemoryTenderStore()
    return _tender_store_instance


def new_pack_id() -> str:
    return str(uuid.uuid4())
