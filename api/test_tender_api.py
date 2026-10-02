"""
Offline tests for the Tender Pack (tender_api.py, tender_store.py,
tender_seed.py, sql_tender_store.py). Run: python test_tender_api.py
Picked up automatically by deploy.yml's "Run offline test suites" step.
"""
import datetime
import re

import tender_api as t
from tender_seed import SEED_ANSWERS, render_sql
from tender_store import InMemoryTenderStore, TenderAnswer
import sql_tender_store

TODAY = datetime.date(2026, 10, 2)
NOW = datetime.datetime(2026, 10, 2, 9, 30, 0)

# Mirrors the live Policy & Compliance records described in the continuation pack.
CERTS = [
    {"title": "Cyber Essentials Plus", "currentVersion": "CE+ cert", "expiryDate": "2026-09-23", "documentUrl": "https://x/ceplus"},
    {"title": "Cyber Essentials", "currentVersion": "CE cert", "expiryDate": "2027-09-12", "documentUrl": "https://x/ce"},
    {"title": "ICO Data Protection Registration", "currentVersion": "ZA211766", "expiryDate": "2026-10-15", "documentUrl": "https://x/ico"},
]
POLICIES = [
    {"title": "CLG_SEC_POL_001 ISMS Policy", "currentVersion": "V1.0", "approvalStatus": "Board approved",
     "nextReviewDate": "2027-04-01", "documentUrl": "https://x/pol1"},
]
DOCS = t.build_evidence_index(CERTS, POLICIES)


def approved(answer_id):
    a = InMemoryTenderStore().get_answer(answer_id)
    a.status = "Approved"
    return a


def lib(*answers):
    return {a.answer_id: a for a in answers}


def test_parse_questions_strips_numbering_and_bullets():
    qs = t.parse_questions("1. Do you hold CE+?\n\nQ2: Are you ISO certified?\n  a) Who owns security?\n- Bullet question here\nok")
    assert qs == ["Do you hold CE+?", "Are you ISO certified?", "Who owns security?", "Bullet question here"], qs
    print("PASS: questionnaire numbering, bullets and blank lines are cleaned")


def test_parse_questions_limits():
    for bad in ("", "   \n  ", 42):
        try:
            t.parse_questions(bad)
            assert False
        except t.TenderRequestError:
            pass
    try:
        t.parse_questions(["Question number %d here" % i for i in range(t.MAX_QUESTIONS + 1)])
        assert False
    except t.TenderRequestError:
        pass
    print("PASS: empty, non-text and oversized questionnaires are refused")


def test_cyber_essentials_vs_plus_disambiguation():
    answers = InMemoryTenderStore().list_answers()
    assert t.match_question("Do you hold Cyber Essentials?", answers)[0][0].answer_id == "cert-cyber-essentials"
    assert t.match_question("Do you hold Cyber Essentials Plus?", answers)[0][0].answer_id == "cert-cyber-essentials-plus"
    assert t.match_question("Are you CE+ certified?", answers)[0][0].answer_id == "cert-cyber-essentials-plus"
    print("PASS: Cyber Essentials and Cyber Essentials Plus are told apart")


def test_realistic_questions_match_expected_answers():
    answers = InMemoryTenderStore().list_answers()
    expected = {
        "Is two-factor authentication enforced for remote access?": "access-mfa",
        "Describe how you protect personal data in line with UK GDPR": "dp-uk-gdpr",
        "How do you ensure laptops are encrypted and managed?": "device-management",
        "What is your process for reporting a data breach to the client?": "incident-response",
        "Where will our data be stored, and is it backed up?": "hosting-backup",
        "How is access to systems restricted when staff leave?": "access-control",
        "How do you vet subcontractors who will access our data?": "supplier-security",
    }
    for q, want in expected.items():
        got = t.match_question(q, answers)[0][0].answer_id
        assert got == want, (q, got)
    print(f"PASS: {len(expected)} realistic tender questions match the right library answer")


def test_off_topic_questions_find_nothing():
    answers = InMemoryTenderStore().list_answers()
    for q in ("What is your annual turnover?", "Do you have an environmental sustainability policy?"):
        assert t.match_question(q, answers) == [], q
    print("PASS: off-topic questions are left unmatched rather than forced onto an answer")


def test_evidence_resolution_prefers_exact_then_shortest_prefix():
    assert t.resolve_evidence("Cyber Essentials", DOCS)["title"] == "Cyber Essentials"
    assert t.resolve_evidence("ICO", DOCS)["title"] == "ICO Data Protection Registration"
    assert t.resolve_evidence("CLG_SEC_POL_001", DOCS)["title"] == "CLG_SEC_POL_001 ISMS Policy"
    assert t.resolve_evidence("Nonexistent", DOCS) is None
    print("PASS: evidence keys resolve exactly first, then by shortest prefix")


def test_certificate_judged_on_bid_deadline_not_today():
    ico = t.resolve_evidence("ICO", DOCS)
    assert t.evidence_status("ICO", ico, datetime.date(2026, 10, 10), TODAY)["status"] == "valid"
    assert t.evidence_status("ICO", ico, datetime.date(2026, 10, 30), TODAY)["status"] == "expires_before_deadline"
    ceplus = t.resolve_evidence("Cyber Essentials Plus", DOCS)
    assert t.evidence_status("x", ceplus, datetime.date(2026, 10, 10), TODAY)["status"] == "expired"
    assert t.evidence_status("x", None, datetime.date(2026, 10, 10), TODAY)["status"] == "missing"
    print("PASS: certificates are checked against the bid deadline (ICO valid for 10 Oct, not for 30 Oct)")


def test_policy_review_overdue_needs_review():
    old = t.build_evidence_index([], [{"title": "CLG_SEC_POL_009 Old", "nextReviewDate": "2026-01-01"}])
    e = t.evidence_status("CLG_SEC_POL_009", old[0], datetime.date(2026, 11, 1), TODAY)
    assert e["status"] == "review_overdue"
    print("PASS: a policy past its review date is flagged")


def test_statuses_ready_review_blocked_unmatched():
    deadline = datetime.date(2026, 10, 10)
    ce = approved("cert-cyber-essentials")
    ev = t._evidence_for(ce, DOCS, deadline, TODAY)
    assert t.assess(ce, ce.answer_text, 0.9, ev)[0] == t.STATUS_READY
    draft = InMemoryTenderStore().get_answer("cert-cyber-essentials")
    assert t.assess(draft, draft.answer_text, 0.9, ev)[0] == t.STATUS_REVIEW
    ceplus = approved("cert-cyber-essentials-plus")
    status, reasons = t.assess(ceplus, ceplus.answer_text, 0.9, t._evidence_for(ceplus, DOCS, deadline, TODAY))
    assert status == t.STATUS_BLOCKED and "Expired" in reasons[0], reasons
    iso = approved("cert-iso-27001")
    assert t.assess(iso, iso.answer_text, 0.9, [])[0] == t.STATUS_REVIEW  # [confirm: ...] placeholder
    assert t.assess(None, "", None, [])[0] == t.STATUS_UNMATCHED
    print("PASS: ready, needs-review, blocked and unmatched statuses are assigned correctly")


def test_match_response_shape_and_summary():
    body = {"deadline": "2026-10-10", "questions": "Do you hold Cyber Essentials?\nDo you hold Cyber Essentials Plus?\nWhat is your annual turnover?"}
    r = t.build_match_response(body, InMemoryTenderStore().list_answers(), DOCS, TODAY)
    assert [i["status"] for i in r["items"]] == ["needs_review", "blocked", "unmatched"], [i["status"] for i in r["items"]]
    assert r["summary"] == {"ready": 0, "needs_review": 1, "blocked": 1, "unmatched": 1, "total": 3}
    assert r["items"][0]["evidence"][0]["status"] == "valid"
    print("PASS: /tender/match returns per-question status, evidence and a summary")


def test_deadline_validation():
    for bad in ("", "not a date", "2026-09-01"):
        try:
            t.parse_deadline(bad, TODAY)
            assert False, bad
        except t.TenderRequestError:
            pass
    print("PASS: missing, malformed and past deadlines are refused")


def _pack_body(items):
    return {"clientName": "Example Council", "bidReference": "EC-2026-14", "deadline": "2026-10-10", "items": items}


def test_pack_refuses_blocked_placeholder_and_unreviewed():
    ceplus, iso, draft = approved("cert-cyber-essentials-plus"), approved("cert-iso-27001"), InMemoryTenderStore().get_answer("cert-cyber-essentials")
    cases = [
        ([{"question": "CE+?", "answerId": ceplus.answer_id, "answerText": ceplus.answer_text}], "not valid on the deadline"),
        ([{"question": "ISO?", "answerId": iso.answer_id, "answerText": iso.answer_text, "reviewed": True}], "[confirm"),
        ([{"question": "CE?", "answerId": draft.answer_id, "answerText": draft.answer_text}], "needs your review"),
        ([{"question": "Turnover?", "answerId": None, "answerText": ""}], "has no answer"),
        ([{"question": "CE?", "answerId": "deleted-answer", "answerText": "x"}], "no longer exists"),
    ]
    for items, expect in cases:
        try:
            t.build_pack(_pack_body(items), lib(ceplus, iso, draft), DOCS, "cyuen@cognitionlearninggroup.com", NOW)
            assert False, expect
        except t.TenderRequestError as e:
            assert expect in str(e), (expect, str(e))
    print("PASS: packs are refused for expired evidence, placeholders, unreviewed items, empty and stale answers")


def test_pack_issues_snapshot_with_server_side_identity_and_evidence():
    ce, draft_mfa = approved("cert-cyber-essentials"), InMemoryTenderStore().get_answer("dp-ico-registration")
    items = [
        {"question": "Do you hold Cyber Essentials?", "answerId": ce.answer_id, "answerText": ce.answer_text,
         "evidence": [{"status": "forged"}], "preparedBy": "someone.else@example.com"},
        {"question": "ICO number?", "answerId": draft_mfa.answer_id, "answerText": draft_mfa.answer_text + " Edited.", "reviewed": True},
        {"question": "Turnover?", "answerId": None, "answerText": "See our published accounts.", "reviewed": True},
        {"question": "Left out", "answerId": None, "answerText": "", "include": False},
    ]
    items.insert(1, {"question": "Excluded earlier question", "answerId": None, "answerText": "x", "include": False})
    pack = t.build_pack(_pack_body(items), lib(ce, draft_mfa), DOCS, "cyuen@cognitionlearninggroup.com", NOW)
    snap = pack.snapshot
    assert pack.prepared_by == snap["preparedBy"] == "cyuen@cognitionlearninggroup.com"
    assert re.fullmatch(r"TP-20261002-[0-9A-F]{4}", pack.pack_ref), pack.pack_ref
    assert [i["number"] for i in snap["items"]] == [1, 3, 4], "keeps the buyer's own question numbers"
    assert snap["items"][0]["evidence"][0]["status"] == "valid"           # recomputed, not the forged value
    assert snap["items"][1]["edited"] is True and snap["items"][1]["reviewedByPreparer"] is True
    assert snap["items"][2]["answerId"] is None and snap["items"][2]["category"] == "Other"
    assert [e["title"] for e in snap["evidenceAppendix"]] == ["Cyber Essentials", "ICO Data Protection Registration"]
    assert pack.summary == {"questions": 3, "fromLibrary": 2, "edited": 1, "reviewedByPreparer": 2, "evidence": 2}
    print("PASS: an issued pack is a snapshot with server-side identity, recomputed evidence and a deduplicated appendix")


def test_store_pack_round_trip_and_ordering():
    store = InMemoryTenderStore()
    ce = approved("cert-cyber-essentials")
    body = _pack_body([{"question": "Do you hold Cyber Essentials?", "answerId": ce.answer_id, "answerText": ce.answer_text}])
    p1 = store.create_pack(t.build_pack(body, lib(ce), DOCS, "a@x", NOW))
    p2 = store.create_pack(t.build_pack(body, lib(ce), DOCS, "b@x", NOW + datetime.timedelta(minutes=5)))
    assert [p.pack_id for p in store.list_packs()] == [p2.pack_id, p1.pack_id]
    assert store.get_pack(p1.pack_id).snapshot["preparedBy"] == "a@x"
    print("PASS: packs are stored and listed newest first")


def test_library_edit_approve_rules():
    store = InMemoryTenderStore()
    ids = [a.answer_id for a in store.list_answers(include_retired=True)]
    try:
        t.approve_answer(store.get_answer("cert-iso-27001"), "it@x", NOW)
        assert False
    except t.TenderRequestError:
        pass
    a = t.approve_answer(store.get_answer("cert-cyber-essentials"), "it@x", NOW)
    assert a.status == "Approved" and a.approved_by == "it@x"
    store.upsert_answer(a)
    edited = t.apply_answer_edit({**a.to_api(), "answerText": a.answer_text + " Updated."}, store.get_answer(a.answer_id), "it@x", ids)
    assert edited.status == "Draft" and edited.approved_by is None, "changed wording must be re-approved"
    try:
        t.apply_answer_edit({"category": "X", "question": "New?", "answerText": "Y", "status": "Approved"}, None, "it@x", ids)
        assert False
    except t.TenderRequestError:
        pass
    new = t.apply_answer_edit({"category": "Certifications", "question": "Do you hold Cyber Essentials?", "answerText": "Yes."}, None, "it@x", ids + ["do-you-hold-cyber-essentials"])
    assert new.answer_id == "do-you-hold-cyber-essentials-2"
    print("PASS: placeholders block approval, edits reset approval, new ids never collide")


def test_seed_sql_matches_seed_and_is_rerunnable():
    sql = render_sql()
    for a in SEED_ANSWERS:
        assert f"WHERE answerId = N'{a['answerId']}'" in sql, a["answerId"]
    assert sql.count("INSERT INTO dbo.tender_answer") == len(SEED_ANSWERS)
    assert "IF OBJECT_ID('dbo.tender_answer', 'U') IS NULL" in sql
    assert len({a["answerId"] for a in SEED_ANSWERS}) == len(SEED_ANSWERS)
    print(f"PASS: seed SQL holds all {len(SEED_ANSWERS)} answers, each inserted only if absent")


def test_sql_statements_have_matching_columns_and_placeholders():
    def count(sql):
        cols = sql[sql.index("(") + 1: sql.index(")")].count(",") + 1
        return cols, sql.split("VALUES")[1].count("?")
    for name in ("INSERT_ANSWER_SQL", "INSERT_PACK_SQL"):
        cols, marks = count(getattr(sql_tender_store, name))
        assert cols == marks, (name, cols, marks)
    upd = sql_tender_store.UPDATE_ANSWER_SQL
    assert upd.count("?") == upd.split("WHERE")[0].count("= ?") + 1
    print("PASS: every SQL INSERT/UPDATE has as many placeholders as columns (Batch H lesson)")


if __name__ == "__main__":
    test_parse_questions_strips_numbering_and_bullets()
    test_parse_questions_limits()
    test_cyber_essentials_vs_plus_disambiguation()
    test_realistic_questions_match_expected_answers()
    test_off_topic_questions_find_nothing()
    test_evidence_resolution_prefers_exact_then_shortest_prefix()
    test_certificate_judged_on_bid_deadline_not_today()
    test_policy_review_overdue_needs_review()
    test_statuses_ready_review_blocked_unmatched()
    test_match_response_shape_and_summary()
    test_deadline_validation()
    test_pack_refuses_blocked_placeholder_and_unreviewed()
    test_pack_issues_snapshot_with_server_side_identity_and_evidence()
    test_store_pack_round_trip_and_ordering()
    test_library_edit_approve_rules()
    test_seed_sql_matches_seed_and_is_rerunnable()
    test_sql_statements_have_matching_columns_and_placeholders()
    print("\nALL TENDER PACK OFFLINE TESTS PASSED")
