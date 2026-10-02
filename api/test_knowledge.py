"""
Offline tests for Knowledge Base v2 (knowledge_api, knowledge_store,
knowledge_seed, sql_knowledge_store) plus end-to-end route tests when the
azure-functions package is installed. Run: python test_knowledge.py
"""
import base64
import datetime
import json
import os

import knowledge_api as k
from knowledge_seed import SEED_ARTICLES, render_sql
from knowledge_store import InMemoryKnowledgeStore, SearchLogEntry
import sql_knowledge_store as sqlk

NOW = datetime.datetime(2026, 10, 2, 9, 0, 0)
TODAY = NOW.date()


def store_with_approved(*ids):
    s = InMemoryKnowledgeStore()
    for aid in ids:
        s.upsert_article(k.approve(s.get_article(aid), "it@x", NOW))
    return s


def test_seed_shape():
    ids = [a["articleId"] for a in SEED_ARTICLES]
    assert len(ids) == len(set(ids)) >= 30
    for a in SEED_ARTICLES:
        assert a["title"] and a["summary"] and a["body"] and a["keywords"], a["articleId"]
    print(f"PASS: {len(ids)} seed articles, unique ids, every field filled")


def test_search_synonyms_and_ranking():
    arts = InMemoryKnowledgeStore().list_articles()
    cases = {
        "2fa": "set-up-mfa", "two-factor authentication": "set-up-mfa", "forgot my password": "reset-your-password",
        "laptop stolen": "lost-or-stolen-device", "phishing email": "spot-and-report-phishing",
        "where do I save files": "where-to-save-files", "recover deleted email": "recover-deleted-email-file",
        "can I use chatgpt": "approved-ai-tools", "internet not working": "internet-down",
        "usb stick": "usb-drives", "new laptop": "request-new-hardware", "first day": "new-starter-first-day",
        "bitlocker recovery key": "bitlocker-encryption", "change bank details email": "payment-fraud",
        "someone called pretending to be IT": "fake-it-calls", "sent email to wrong person": "wrong-recipient",
        "subject access request": "subject-access-request", "teams is down": "microsoft-365-outage",
        "office closed snow": "cant-get-to-office", "request access to sharepoint folder": "request-system-access",
        "laptop broken": "laptop-broken", "travelling abroad with laptop": "travelling-with-devices",
        "api key in code": "secrets-in-code", "give contractor access": "contractor-access",
        "request new ai tool": "request-ai-tool", "pasted data into chatgpt": "report-ai-incident",
        "dpia": "dpia-new-project", "phone calls not working": "phones-not-working",
    }
    for q, want in cases.items():
        got = k.search(q, arts, include_drafts=True)
        assert got and got[0][0].article_id == want, (q, [a.article_id for a, _ in got[:3]])
    for off_topic in ("annual leave policy", "expenses claim", "book a meeting room", "payroll question"):
        assert k.search(off_topic, arts, include_drafts=True) == [], off_topic
    print(f"PASS: {len(cases)} everyday queries find the right article (incl. synonyms); 4 off-topic queries find nothing")


def test_no_generic_single_word_keywords():
    from tender_api import tokens
    generic = {"policy", "data", "security", "inform", "information", "process", "staff", "system", "service", "plan", "use", "work"}
    bad = [(a["articleId"], kw) for a in SEED_ARTICLES for kw in a["keywords"] if len(tokens(kw)) == 1 and tokens(kw)[0] in generic]
    assert not bad, bad
    print(f"PASS: no article uses a generic single-word keyword ({len(SEED_ARTICLES)} checked)")


def test_readers_see_only_approved():
    s = store_with_approved("screen-lock")
    arts = s.list_articles()
    assert [a.article_id for a, _ in k.search("lock screen", arts, include_drafts=False)] == ["screen-lock"]
    assert k.search("password", arts, include_drafts=False) == []
    home = k.build_home_response(arts, include_drafts=False)
    assert home["total"] == 1 and home["categories"] == [{"name": "Devices", "count": 1}]
    try:
        k.build_article_response(s.get_article("reset-your-password"), arts, [], False, TODAY)
        assert False
    except k.KnowledgeRequestError:
        pass
    print("PASS: readers see only approved articles; drafts are hidden from search, home and direct links")


def test_approval_rules_and_versioning():
    s = InMemoryKnowledgeStore()
    try:
        k.approve(s.get_article("set-up-mfa"), "it@x", NOW)  # contains [confirm]
        assert False
    except k.KnowledgeRequestError as e:
        assert "[confirm" in str(e)
    a = k.approve(s.get_article("screen-lock"), "it@x", NOW)
    assert a.status == "Approved" and a.review_date == "2027-10-02", a.review_date
    s.upsert_article(a)
    ids = [x.article_id for x in s.list_articles(True)]
    edited = k.apply_edit({**a.to_api(), "body": a.body + "\n\nExtra line."}, s.get_article("screen-lock"), "ed@x", ids)
    assert edited.status == "Draft" and edited.version == 2 and edited.approved_by is None
    same = k.apply_edit({**a.to_api(), "keywords": a.keywords + ["lock"]}, s.get_article("screen-lock"), "ed@x", ids)
    assert same.status == "Approved" and same.version == 1, "keyword-only edits do not need re-approval"
    try:
        k.apply_edit({"title": "T", "summary": "S", "category": "C", "body": "B", "status": "Approved"}, None, "x", ids)
        assert False
    except k.KnowledgeRequestError:
        pass
    new = k.apply_edit({"title": "Reset your password", "summary": "S", "category": "C", "body": "B"}, None, "x", ids)
    assert new.article_id == "reset-your-password-2" and new.status == "Draft"
    print("PASS: [confirm] blocks publishing; wording edits re-draft and bump version; new ids never collide")


def test_feedback_validation():
    arts = {a.article_id: a for a in InMemoryKnowledgeStore().list_articles()}
    fb = k.parse_feedback({"articleId": "screen-lock", "helpful": True, "reason": "unclear"}, arts, "u@x")
    assert fb.helpful and fb.reason is None and fb.user == "u@x"
    for bad in ({"articleId": "nope", "helpful": True}, {"articleId": "screen-lock", "helpful": "yes"},
                {"articleId": "screen-lock", "helpful": False}, {"articleId": "screen-lock", "helpful": False, "reason": "x"}):
        try:
            k.parse_feedback(bad, arts, "u")
            assert False, bad
        except k.KnowledgeRequestError:
            pass
    print("PASS: feedback needs a real article, a yes/no, and a reason when not helpful")


def test_insights():
    s = store_with_approved("screen-lock", "usb-drives")
    arts = {a.article_id: a for a in s.list_articles()}
    for helpful, reason in [(False, "outdated"), (False, "unclear"), (True, None), (False, "outdated")]:
        s.add_feedback(k.parse_feedback({"articleId": "usb-drives", "helpful": helpful, "reason": reason,
                                         "comment": "Mentions old process" if reason == "outdated" else None}, arts, "u"))
    for q, n in [("vpn setup", 0), ("vpn setup", 0), ("printer", 0), ("lock screen", 1)]:
        s.log_search(SearchLogEntry(query=q, result_count=n))
    a = s.get_article("screen-lock"); a.review_date = "2026-01-01"; s.upsert_article(a)
    ins = k.build_insights(s.list_articles(True), s.list_feedback(), s.list_search_log(), TODAY)
    assert ins["zeroResultSearches"][0] == {"query": "vpn setup", "count": 2}
    assert ins["zeroResultRate"] == 75 and ins["searches"] == 4
    assert ins["lowestRated"][0]["articleId"] == "usb-drives" and ins["lowestRated"][0]["helpfulPercent"] == 25
    assert ins["notHelpfulReasons"] == {"outdated": 2, "unclear": 1}
    assert [x["articleId"] for x in ins["reviewOverdue"]] == ["screen-lock"]
    assert ins["recentComments"][0]["comment"] == "Mentions old process"
    assert ins["counts"]["Approved"] == 2 and len(ins["draftsWithPlaceholders"]) >= 10
    print("PASS: insights report zero-result searches, lowest rated, reasons, overdue reviews and drafts to finish")


def test_related_articles():
    s = InMemoryKnowledgeStore()
    rel = k.related(s.get_article("set-up-mfa"), s.list_articles(), include_drafts=True)
    ids = [r["articleId"] for r in rel]
    assert "set-up-mfa" not in ids and ("new-phone-mfa" in ids or "reset-your-password" in ids), ids
    print("PASS: related articles exclude the article itself and find its neighbours")


def test_sql():
    sql = render_sql()
    assert sql.count("INSERT INTO dbo.knowledge_article") == len(SEED_ARTICLES)
    assert "AND updatedBy IS NULL AND approvedBy IS NULL" in sql
    def cols_vs_marks(stmt):
        return stmt[stmt.index("(") + 1: stmt.index(")")].count(",") + 1, stmt.split("VALUES")[1].count("?")
    for name in ("INSERT_SQL", "FEEDBACK_SQL", "SEARCH_SQL"):
        c, m = cols_vs_marks(getattr(sqlk, name))
        assert c == m, (name, c, m)
    upd = sqlk.UPDATE_SQL
    assert upd.count("?") == upd.split("WHERE")[0].count("= ?") + 1
    print("PASS: seed SQL is re-runnable and every statement has matching columns and placeholders")


def test_routes():
    try:
        import azure.functions as func
        import azure.durable_functions  # noqa: F401
    except ImportError:
        print("SKIP: route tests need azure-functions")
        return
    group = "49cab434-8d81-44fd-b871-ecead72becdc"
    os.environ["IT_HELPDESK_ACCESS_GROUP_ID"] = group
    os.environ.pop("AZURE_SQL_SERVER", None)
    import function_app as fa
    p = base64.b64encode(json.dumps({"userId": "u", "claims": [{"typ": "preferred_username", "val": "cyuen@cognitionlearninggroup.com"},
                                                               {"typ": "groups", "val": group}]}).encode()).decode()

    def call(fn, method="GET", body=None, params=None, route=None):
        r = fn(func.HttpRequest(method=method, url="/api/x", headers={"X-MS-CLIENT-PRINCIPAL": p}, params=params or {},
                                route_params=route or {}, body=json.dumps(body).encode() if body is not None else b""))
        return r.status_code, json.loads(r.get_body() or b"{}")

    st, b = call(fa.knowledge_approve, "POST", route={"articleId": "screen-lock"})
    assert st == 200 and b["article"]["approvedBy"] == "cyuen@cognitionlearninggroup.com"
    st, b = call(fa.knowledge_search, params={"q": "lock my screen"})
    assert st == 200 and b["results"][0]["articleId"] == "screen-lock"
    call(fa.knowledge_search, params={"q": "printer jammed"})
    st, b = call(fa.knowledge_get, route={"articleId": "screen-lock"})
    assert st == 200 and b["article"]["status"] == "Approved"
    st, b = call(fa.knowledge_get, route={"articleId": "set-up-mfa"})
    assert st == 400, "drafts are not readable without drafts=true"
    st, _ = call(fa.knowledge_feedback, "POST", {"articleId": "screen-lock", "helpful": False, "reason": "unclear"})
    assert st == 201
    st, ins = call(fa.knowledge_insights)
    assert st == 200 and {"query": "printer jammed", "count": 1} in ins["zeroResultSearches"]
    st, home = call(fa.knowledge_home)
    assert st == 200 and home["popular"][0]["articleId"] == "screen-lock" and home["popular"][0]["views"] == 1
    st, lst = call(fa.knowledge_list)
    assert st == 200 and lst["count"] == len(SEED_ARTICLES)
    print("PASS: routes end to end — approve, search, view counting, draft protection, feedback, insights")


if __name__ == "__main__":
    test_seed_shape()
    test_search_synonyms_and_ranking()
    test_no_generic_single_word_keywords()
    test_readers_see_only_approved()
    test_approval_rules_and_versioning()
    test_feedback_validation()
    test_insights()
    test_related_articles()
    test_sql()
    test_routes()
    print("\nALL KNOWLEDGE BASE TESTS PASSED")
