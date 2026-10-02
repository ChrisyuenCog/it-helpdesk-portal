"""
IT Helpdesk Portal — Tender Pack logic (Batch I, HD-054–058 widened)
====================================================================
Pure, offline-testable functions behind the /api/tender/* routes:

  parse_questions()      a pasted questionnaire -> clean list of questions
  match_question()       question -> ranked library answers + confidence
  resolve_evidence()     evidence key -> live Policy & Compliance record
  evidence_status()      is that record good on the BID DEADLINE (not today)?
  assess_item()          one question -> status + plain-English reasons
  build_match_response() POST /api/tender/match
  build_pack()           POST /api/tender/packs (server re-checks everything)

*** SAFETY RULES (enforced server-side in build_pack, never trusted from the browser) ***
  1. A certificate that has expired, or will expire before the bid deadline,
     can never be claimed: the item is "blocked" and the pack is refused.
  2. Any answer still containing a "[confirm: ...]" placeholder is refused.
  3. An item that is not "ready" (a draft library answer, a low-confidence
     match, an answer written for this bid, an overdue policy review) needs
     the preparer to tick "reviewed" before it can be issued.
  4. Evidence status is recomputed from live records at issue time, and the
     issued pack is stored as an immutable snapshot with the preparer's
     identity taken from the sign-in token, never from the request body.

Matching is deterministic keyword-and-overlap scoring: explainable, testable
and free to run. AI suggestions can be layered on later (roadmap Phase 4)
without changing these safety rules.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tender_store import TenderAnswer, TenderPack, ANSWER_STATUSES, make_pack_ref, new_pack_id

MAX_QUESTIONS = 200
MAX_QUESTION_CHARS = 2000
PLACEHOLDER_MARK = "[confirm"

STATUS_READY = "ready"
STATUS_REVIEW = "needs_review"
STATUS_BLOCKED = "blocked"
STATUS_UNMATCHED = "unmatched"


class TenderRequestError(Exception):
    """Invalid input; the message is safe to show to the user."""


# ---------------------------------------------------------------------------
# Text normalisation and questionnaire parsing
# ---------------------------------------------------------------------------
_PHRASE_SYNONYMS = [
    (r"\bce\s*\+", " cyber essentials plus "),
    (r"\bce plus\b", " cyber essentials plus "),
    (r"\bcyber essentials\s*\+", " cyber essentials plus "),
    (r"\btwo[\s-]factor\b", " multi-factor "),
    (r"\b2fa\b", " mfa "),
    (r"\bmulti\s+factor\b", " multi-factor "),
    (r"\banti[\s-]virus\b", " antivirus "),
    (r"\banti[\s-]malware\b", " malware "),
    (r"\biso\s*/\s*iec\b", " iso "),
    (r"\biso\s*27001\b", " iso 27001 "),
    (r"\bbcp\b", " business continuity "),
    (r"\bdisaster recovery\b", " disaster recovery "),
    (r"\bdata protection act\b", " data protection act gdpr "),
    (r"\bsub[\s-]?contractors?\b", " subcontractor "),
    (r"\bthird[\s-]part(y|ies)\b", " third party "),
    (r"&", " and "),
]
_STOPWORDS = set("""
a an and are as at be by can could describe detail details do does for from has have how i if in
include including is it its of on or our please provide state that the their there these this to
we what when where whether which who will with would you your yours any all also confirm explain
organisation organization company business ltd limited
""".split())

_NUMBERING = re.compile(r"^\s*(?:q(?:uestion)?\s*)?(?:\d+(?:\.\d+)*|[a-z]|[ivx]+)[\.\):\-]\s+", re.IGNORECASE)
_BULLET = re.compile(r"^\s*[-*\u2022\u25CF]\s+")


def normalise(text: str) -> str:
    t = " " + (text or "").lower() + " "
    for pattern, repl in _PHRASE_SYNONYMS:
        t = re.sub(pattern, repl, t)
    return re.sub(r"\s+", " ", t).strip()


_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ions", "ion", "ies", "ied", "es", "ed", "ly", "s", "e")


def _stem(word: str) -> str:
    """Light, deterministic stemmer: two passes so 'managed', 'management'
    and 'manage' all reduce to the same stem, as do 'encrypted' and
    'encryption'."""
    for _ in range(2):
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
                break
    return word


def tokens(text: str) -> List[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9+]+", normalise(text)) if w not in _STOPWORDS and len(w) > 1]


def parse_questions(raw: Any) -> List[str]:
    """Accepts a list of strings or one pasted block (one question per line;
    numbering like '1.', 'Q3:', 'a)' and bullets are removed)."""
    if isinstance(raw, list):
        lines = [str(x) for x in raw]
    elif isinstance(raw, str):
        lines = raw.splitlines()
    else:
        raise TenderRequestError("Questions must be text or a list of questions.")
    out = []
    for line in lines:
        q = _BULLET.sub("", _NUMBERING.sub("", line)).strip()
        if len(q) < 4:
            continue
        out.append(q[:MAX_QUESTION_CHARS])
    if not out:
        raise TenderRequestError("Add at least one question.")
    if len(out) > MAX_QUESTIONS:
        raise TenderRequestError(f"A pack can hold up to {MAX_QUESTIONS} questions; split larger questionnaires.")
    return out


def parse_deadline(value: Any, today: datetime.date) -> datetime.date:
    try:
        d = datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise TenderRequestError("Enter the submission deadline as a date.")
    if d < today:
        raise TenderRequestError("The submission deadline is in the past.")
    return d


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def _contains_run(haystack: List[str], needle: List[str]) -> bool:
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def score_answer(question: str, answer: TenderAnswer) -> float:
    """0..1. Keyword phrases are the strongest signal (a multi-word keyword
    must appear as a run, so 'cyber essentials plus' only matches when the
    question says plus); overlap with the library question and category
    adds the rest; library words the question never mentions cost a little,
    which separates near-twins such as Cyber Essentials and Cyber Essentials
    Plus."""
    q_list = tokens(question)
    qt = set(q_list)
    if not qt:
        return 0.0
    raw = 0.0
    for kw in answer.keywords:
        kt = tokens(kw)
        if len(kt) > 1:
            if _contains_run(q_list, kt):
                raw += 2.0 + len(kt)
        elif len(kt) == 1 and kt[0] in qt:
            raw += 2.0
    lib = set(tokens(answer.question)) | set(tokens(answer.category))
    raw += 4.0 * len(qt & lib) / len(qt)
    if lib:
        raw -= 0.5 * len(lib - qt) / len(lib)
    return round(max(0.0, raw / 7.0), 3)  # uncapped so near-twins still rank apart; display caps at 1


def confidence_label(score: float) -> str:
    if score >= 0.6:
        return "High"
    if score >= 0.35:
        return "Medium"
    return "Low"


def match_question(question: str, answers: Iterable[TenderAnswer], min_score: float = 0.25) -> List[Tuple[TenderAnswer, float]]:
    ranked = [(a, score_answer(question, a)) for a in answers if a.status != "Retired"]
    ranked = [r for r in ranked if r[1] >= min_score]
    ranked.sort(key=lambda r: (-r[1], r[0].answer_id))
    return ranked


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def build_evidence_index(certificates: List[Dict[str, Any]], policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flattens the existing /compliance responses into one list of
    evidence records. Strictly Confidential URLs are already redacted by
    compliance_api, so they never reach a pack."""
    docs = []
    for c in certificates:
        docs.append({"kind": "Certificate", "title": c.get("title"), "currentVersion": c.get("currentVersion"),
                     "expiryDate": c.get("expiryDate"), "documentUrl": c.get("documentUrl")})
    for p in policies:
        docs.append({"kind": "Policy", "title": p.get("title"), "currentVersion": p.get("currentVersion"),
                     "approvalStatus": p.get("approvalStatus"), "nextReviewDate": p.get("nextReviewDate"),
                     "documentUrl": p.get("documentUrl")})
    return [d for d in docs if d.get("title")]


def resolve_evidence(key: str, docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    k = (key or "").strip().lower()
    if not k:
        return None
    exact = [d for d in docs if d["title"].strip().lower() == k]
    if exact:
        return exact[0]
    prefixed = [d for d in docs if d["title"].strip().lower().startswith(k)]
    if prefixed:
        return sorted(prefixed, key=lambda d: len(d["title"]))[0]
    return None


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def human_date(d: datetime.date) -> str:
    """'22 Sep 2026' — the format the portal shows everywhere."""
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _to_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def evidence_status(key: str, doc: Optional[Dict[str, Any]], deadline: datetime.date, today: datetime.date) -> Dict[str, Any]:
    if doc is None:
        return {"key": key, "title": key, "kind": None, "status": "missing",
                "message": f"No Policy & Compliance record matches “{key}”."}
    base = {"key": key, "title": doc["title"], "kind": doc["kind"], "currentVersion": doc.get("currentVersion"),
            "documentUrl": doc.get("documentUrl")}
    if doc["kind"] == "Certificate":
        expiry = _to_date(doc.get("expiryDate"))
        base["expiryDate"] = doc.get("expiryDate")
        if expiry is None:
            return {**base, "status": "unknown", "message": "No expiry date is recorded for this certificate."}
        if expiry < today:
            return {**base, "status": "expired",
                    "message": f"Expired on {human_date(expiry)}. Do not claim it until it is renewed."}
        if expiry < deadline:
            return {**base, "status": "expires_before_deadline",
                    "message": f"Expires on {human_date(expiry)}, before the submission deadline of {human_date(deadline)}."}
        return {**base, "status": "valid", "message": f"Valid until {human_date(expiry)}."}
    review = _to_date(doc.get("nextReviewDate"))
    base["nextReviewDate"] = doc.get("nextReviewDate")
    base["approvalStatus"] = doc.get("approvalStatus")
    if review is not None and review < today:
        return {**base, "status": "review_overdue", "message": f"Policy review was due on {human_date(review)}."}
    return {**base, "status": "current", "message": "Current, Board approved." if review else "Current."}


BLOCKING_EVIDENCE = {"expired", "expires_before_deadline"}
REVIEW_EVIDENCE = {"missing", "unknown", "review_overdue"}


def assess(answer: Optional[TenderAnswer], answer_text: str, score: Optional[float], evidence: List[Dict[str, Any]],
           custom: bool = False) -> Tuple[str, List[str]]:
    """Status + reasons, worst first. Shared by match and pack building."""
    if answer is None and not custom:
        return STATUS_UNMATCHED, ["No library answer fits this question. Write one, or ask IT Security."]
    reasons: List[str] = []
    blocked = [e for e in evidence if e["status"] in BLOCKING_EVIDENCE]
    for e in blocked:
        reasons.append(f"{e['title']}: {e['message']}")
    if PLACEHOLDER_MARK in (answer_text or "").lower():
        reasons.append("Replace the [confirm: …] text with verified facts.")
    if custom:
        reasons.append("Written for this bid, not from the approved library.")
    elif answer is not None and answer.status != "Approved":
        reasons.append("Library answer is a draft, not yet approved by IT Security.")
    if score is not None and confidence_label(score) == "Low":
        reasons.append("Low-confidence match: check the answer fits the question.")
    for e in evidence:
        if e["status"] in REVIEW_EVIDENCE:
            reasons.append(f"{e['title']}: {e['message']}")
    if blocked:
        return STATUS_BLOCKED, reasons
    if reasons:
        return STATUS_REVIEW, reasons
    return STATUS_READY, []


def _evidence_for(answer: TenderAnswer, docs, deadline, today) -> List[Dict[str, Any]]:
    return [evidence_status(k, resolve_evidence(k, docs), deadline, today) for k in answer.evidence]


def _summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    s = {STATUS_READY: 0, STATUS_REVIEW: 0, STATUS_BLOCKED: 0, STATUS_UNMATCHED: 0}
    for i in items:
        s[i["status"]] = s.get(i["status"], 0) + 1
    s["total"] = len(items)
    return s


def build_match_response(body: Dict[str, Any], answers: List[TenderAnswer], docs: List[Dict[str, Any]],
                         today: datetime.date) -> Dict[str, Any]:
    deadline = parse_deadline(body.get("deadline"), today)
    questions = parse_questions(body.get("questions"))
    items = []
    for idx, q in enumerate(questions, start=1):
        ranked = match_question(q, answers)
        if not ranked:
            status, reasons = assess(None, "", None, [])
            items.append({"index": idx, "question": q, "status": status, "reasons": reasons, "answer": None,
                          "confidence": None, "score": 0, "answerText": "", "evidence": [], "alternatives": []})
            continue
        best, score = ranked[0]
        evidence = _evidence_for(best, docs, deadline, today)
        status, reasons = assess(best, best.answer_text, score, evidence)
        items.append({
            "index": idx, "question": q, "status": status, "reasons": reasons,
            "answer": best.to_api(), "confidence": confidence_label(score), "score": min(score, 1.0),
            "answerText": best.answer_text, "evidence": evidence,
            "alternatives": [{"answerId": a.answer_id, "question": a.question, "confidence": confidence_label(s)}
                             for a, s in ranked[1:4]],
        })
    return {"deadline": deadline.isoformat(), "items": items, "summary": _summary(items)}


def evaluate_answer_choice(question: str, answer: TenderAnswer, docs, deadline, today) -> Dict[str, Any]:
    """Re-assesses one item when the preparer swaps to an alternative answer."""
    score = score_answer(question, answer)
    evidence = _evidence_for(answer, docs, deadline, today)
    status, reasons = assess(answer, answer.answer_text, score, evidence)
    return {"question": question, "status": status, "reasons": reasons, "answer": answer.to_api(),
            "confidence": confidence_label(score), "score": min(score, 1.0), "answerText": answer.answer_text,
            "evidence": evidence}


# ---------------------------------------------------------------------------
# Issuing a pack
# ---------------------------------------------------------------------------
def build_pack(body: Dict[str, Any], answers_by_id: Dict[str, TenderAnswer], docs: List[Dict[str, Any]],
               prepared_by: str, now: datetime.datetime) -> TenderPack:
    today = now.date()
    client = str(body.get("clientName") or "").strip()
    if not client:
        raise TenderRequestError("Enter the client or buyer name.")
    bid_ref = str(body.get("bidReference") or "").strip()[:400] or None
    deadline = parse_deadline(body.get("deadline"), today)
    raw_items = body.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise TenderRequestError("The pack has no questions.")
    if len(raw_items) > MAX_QUESTIONS:
        raise TenderRequestError(f"A pack can hold up to {MAX_QUESTIONS} questions.")

    issued, problems = [], []
    for n, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict) or not raw.get("include", True):
            continue
        question = str(raw.get("question") or "").strip()[:MAX_QUESTION_CHARS]
        text = str(raw.get("answerText") or "").strip()
        if not question:
            problems.append(f"Question {n} is empty.")
            continue
        if not text:
            problems.append(f"Question {n} has no answer. Write one or leave it out of the pack.")
            continue
        answer_id = raw.get("answerId")
        answer = answers_by_id.get(answer_id) if answer_id else None
        if answer_id and answer is None:
            problems.append(f"Question {n} uses a library answer that no longer exists.")
            continue
        evidence = _evidence_for(answer, docs, deadline, today) if answer else []
        score = score_answer(question, answer) if answer else None
        status, reasons = assess(answer, text, score, evidence, custom=answer is None)
        if status == STATUS_BLOCKED:
            problems.append(f"Question {n} relies on evidence that is not valid on the deadline. Leave it out or change the answer.")
            continue
        if PLACEHOLDER_MARK in text.lower():
            problems.append(f"Question {n} still contains [confirm: …] text.")
            continue
        if status == STATUS_REVIEW and not raw.get("reviewed"):
            problems.append(f"Question {n} needs your review: tick “I have checked this answer”.")
            continue
        issued.append({
            "number": n, "question": question, "answerText": text,  # the buyer's own question number
            "answerId": answer.answer_id if answer else None,
            "libraryQuestion": answer.question if answer else None,
            "category": answer.category if answer else "Other",
            "edited": bool(answer) and text != answer.answer_text.strip(),
            "status": status, "reasons": reasons, "reviewedByPreparer": status == STATUS_REVIEW,
            "evidence": evidence,
        })
    if problems:
        raise TenderRequestError(" ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""))
    if not issued:
        raise TenderRequestError("Include at least one answered question.")

    appendix: Dict[str, Dict[str, Any]] = {}
    for item in issued:
        for e in item["evidence"]:
            if e.get("kind"):
                appendix.setdefault(e["title"], e)
    summary = {"questions": len(issued), "fromLibrary": sum(1 for i in issued if i["answerId"]),
               "edited": sum(1 for i in issued if i["edited"]), "reviewedByPreparer": sum(1 for i in issued if i["reviewedByPreparer"]),
               "evidence": len(appendix)}
    pack_id = new_pack_id()
    created = now.replace(microsecond=0)
    pack_ref = make_pack_ref(created, pack_id)
    snapshot = {
        "packRef": pack_ref, "clientName": client, "bidReference": bid_ref, "deadline": deadline.isoformat(),
        "preparedBy": prepared_by, "createdAt": created.isoformat() + "Z", "items": issued,
        "evidenceAppendix": sorted(appendix.values(), key=lambda e: (e["kind"] != "Certificate", e["title"])),
        "summary": summary,
    }
    return TenderPack(pack_id=pack_id, pack_ref=pack_ref, client_name=client, bid_reference=bid_ref,
                      deadline=deadline.isoformat(), prepared_by=prepared_by, created_at=created.isoformat() + "Z",
                      summary=summary, snapshot=snapshot)


# ---------------------------------------------------------------------------
# Library maintenance
# ---------------------------------------------------------------------------
def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or "answer"


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        raise TenderRequestError("Keywords and evidence must be lists.")
    return [str(v).strip() for v in value if str(v).strip()][:50]


def apply_answer_edit(body: Dict[str, Any], existing: Optional[TenderAnswer], editor: str,
                      existing_ids: Iterable[str]) -> TenderAnswer:
    question = str(body.get("question") or "").strip()
    category = str(body.get("category") or "").strip()
    text = str(body.get("answerText") or "").strip()
    if not question or not category or not text:
        raise TenderRequestError("Category, question and answer are all required.")
    status = str(body.get("status") or (existing.status if existing else "Draft"))
    if status not in ANSWER_STATUSES:
        raise TenderRequestError("Status must be Draft, Approved or Retired.")
    if status == "Approved" and (existing is None or existing.status != "Approved"):
        raise TenderRequestError("Use Approve to approve an answer.")
    answer_id = existing.answer_id if existing else _slug(question)
    if not existing:
        taken = set(existing_ids)
        base, n = answer_id, 2
        while answer_id in taken:
            answer_id, n = f"{base}-{n}", n + 1
    text_changed = existing is None or text != existing.answer_text or _as_list(body.get("evidence")) != existing.evidence
    a = TenderAnswer(
        answer_id=answer_id, category=category[:200], question=question[:2000],
        keywords=_as_list(body.get("keywords")), answer_text=text, evidence=_as_list(body.get("evidence")),
        owner=str(body.get("owner") or (existing.owner if existing else "IT Security"))[:400],
        status=status, review_date=(str(body.get("reviewDate"))[:10] if body.get("reviewDate") else None),
        approved_by=existing.approved_by if existing else None, approved_at=existing.approved_at if existing else None,
        updated_by=editor,
    )
    if existing and existing.status == "Approved" and text_changed and status == "Approved":
        a.status, a.approved_by, a.approved_at = "Draft", None, None  # wording or evidence changed: needs re-approval
    return a


def approve_answer(answer: TenderAnswer, approver: str, now: datetime.datetime) -> TenderAnswer:
    if PLACEHOLDER_MARK in answer.answer_text.lower():
        raise TenderRequestError("Replace the [confirm: …] text before approving this answer.")
    if answer.status == "Retired":
        raise TenderRequestError("A retired answer cannot be approved.")
    answer.status = "Approved"
    answer.approved_by = approver
    answer.approved_at = now.replace(microsecond=0).isoformat() + "Z"
    answer.updated_by = approver
    return answer
