"""
Tests for Phase 1 identity on requests and approvals (workflow_access.py and
the /api/workflow/*, /api/me routes). Run: python test_workflow_access.py

The route tests drive one hardware request end to end as four different
signed-in people and check each step is only possible for the right one.
They skip cleanly where azure-functions isn't installed (as in deploy.yml).
"""
import asyncio
import base64
import datetime
import json
import os
import sys

import workflow_access as wa
from auth_api import CallerIdentity
from workflow_store import InMemoryWorkflowStore

ADMIN = "admin@cognitionlearninggroup.com"
os.environ[wa.ADMIN_SETTING] = ADMIN
os.environ.pop(wa.AGENT_SETTING, None)


def caller(upn, roles=()):
    return wa.build_caller(CallerIdentity(user_id=upn, user_name=upn, group_ids=[], upn=upn, roles=list(roles)), os.environ)


def new_request(store, requester="alice@x.com", approver="bob@x.com", advance=True):
    inst = store.create_instance("HARDWARE_REQUEST", requester_upn=requester)
    fields = {"itemDescription": "Dell Latitude 5450", "approverUpn": approver, "quantity": 1}
    inst.record_transition(inst.current_state, inst.current_state, "submit", fields=fields, actor_upn=requester)
    if advance:
        d = store.get_definition("HARDWARE_REQUEST")
        t = d.get_transition("Submitted", "advance")
        inst.record_transition("Submitted", t["to"], "advance", expected_approver_upn=wa.fallback_approver(t, inst))
    store.save_instance(inst)
    return inst


def test_build_caller_roles():
    assert caller("alice@x.com").roles == {"ITAgent"}, "every portal user is an IT agent by default"
    assert caller(ADMIN).roles == {"ITAgent", "ITAdmin"}
    assert "ITAdmin" in caller("someone@x.com", roles=["ITAdmin"]).roles, "Entra app role honoured"
    assert "Approver" not in caller("someone@x.com", roles=["Approver"]).roles, "Approver is per request, not a standing role"
    os.environ[wa.AGENT_SETTING] = "carol@x.com"
    try:
        assert caller("alice@x.com").roles == set() and caller("carol@x.com").roles == {"ITAgent"}
    finally:
        os.environ.pop(wa.AGENT_SETTING)
    ident = CallerIdentity(user_id="u", user_name="Chris Yuen", group_ids=[], upn="CYuen@CLG.com")
    assert wa.build_caller(ident, os.environ).upn == "cyuen@clg.com", "UPN comes from the upn claim and is lower-cased"
    print("PASS: roles come from settings and app roles; Approver is never a standing role; UPN is normalised")


def test_manager_permissions():
    store = InMemoryWorkflowStore()
    inst = new_request(store)
    d = store.get_definition("HARDWARE_REQUEST")
    approve = d.get_transition("ManagerApproval", "approve")
    assert wa.caller_can(approve, inst, caller("bob@x.com"))[0], "named manager may approve"
    ok, why = wa.caller_can(approve, inst, caller("carol@x.com"))
    assert not ok and "bob@x.com" in why, "other people may not"
    assert not wa.caller_can(approve, inst, caller(ADMIN))[0], "admin cannot override when a manager is recorded"
    self_req = new_request(store, requester="bob@x.com", approver="bob@x.com")
    ok, why = wa.caller_can(approve, self_req, caller("bob@x.com"))
    assert not ok and "own" in why, "nobody approves their own request"
    orphan = new_request(store, approver="")
    assert wa.expected_approver(orphan) is None
    assert wa.caller_can(approve, orphan, caller(ADMIN))[0], "IT admin may approve when no manager is recorded"
    assert not wa.caller_can(approve, orphan, caller("carol@x.com"))[0]
    print("PASS: only the named manager approves; no self-approval; IT admin covers requests with no manager")


def test_available_actions_and_pending():
    store = InMemoryWorkflowStore()
    inst = new_request(store)
    d = store.get_definition("HARDWARE_REQUEST")
    acts = wa.available_actions(d, inst, caller("bob@x.com"))
    assert [a["action"] for a in acts] == ["approve", "reject"]
    assert acts[1]["requiresComment"] and acts[1]["style"] == "danger" and not acts[0]["requiresComment"]
    assert wa.available_actions(d, inst, caller("alice@x.com")) == []
    pending = wa.pending_for([inst, inst], {"HARDWARE_REQUEST": d}, caller("bob@x.com"))
    assert [p.instance_id for p in pending] == [inst.instance_id], "deduplicated"
    print("PASS: actions are worked out per caller; approvals list is per person and deduplicated")


def test_stages_and_summary():
    store = InMemoryWorkflowStore()
    inst = new_request(store)
    d = store.get_definition("HARDWARE_REQUEST")
    s = wa.summarise(inst, d, caller("alice@x.com"), detail=True)
    assert s["title"] == "Dell Latitude 5450" and s["approverUpn"] == "bob@x.com" and s["status"] == "open"
    assert [x["status"] for x in s["stages"]] == ["done", "current", "todo", "todo", "todo", "todo"]
    assert s["reference"].startswith("REQ-") and len(s["reference"]) == 10
    assert s["timeline"][0]["text"] == "Request submitted" and s["timeline"][0]["by"] == "alice@x.com"
    assert "bob@x.com" in s["timeline"][1]["text"]
    inst.record_transition("ManagerApproval", "Rejected", "reject", actor_upn="bob@x.com", comment="Use a spare")
    s = wa.summarise(inst, d, caller("alice@x.com"), detail=True)
    assert s["status"] == "rejected"
    assert [x["status"] for x in s["stages"]] == ["done", "rejected", "todo", "todo", "todo", "todo"]
    assert s["timeline"][-1] == {"at": s["timeline"][-1]["at"], "text": "Rejected at manager approval", "by": "bob@x.com", "comment": "Use a spare"}
    print("PASS: summaries show the item, manager, progress stages (including rejection) and a who-did-what timeline")


def test_parse_start_fields():
    c, today = caller("alice@x.com"), datetime.date(2026, 10, 2)
    ok = wa.parse_start_fields("HARDWARE_REQUEST", {"fields": {"itemDescription": " Monitor ", "approverUpn": "Bob@X.com",
                               "quantity": "2", "neededBy": "2026-10-20", "justification": "New starter"}}, c, today)
    assert ok == {"itemDescription": "Monitor", "approverUpn": "bob@x.com", "quantity": 2, "justification": "New starter", "neededBy": "2026-10-20"}
    bad = [{}, {"itemDescription": "x"}, {"itemDescription": "x", "approverUpn": "not-an-email"},
           {"itemDescription": "x", "approverUpn": "alice@x.com"}, {"itemDescription": "x", "approverUpn": "b@x.com", "quantity": 0},
           {"itemDescription": "x", "approverUpn": "b@x.com", "neededBy": "2026-09-01"}]
    for f in bad:
        try:
            wa.parse_start_fields("HARDWARE_REQUEST", {"fields": f}, c, today)
            assert False, f
        except wa.RequestValidationError:
            pass
    print("PASS: new requests need an item and a manager's email (not your own); quantity and dates are checked")


# ---------------------------------------------------------------- routes
def test_routes_end_to_end():
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

    def principal(upn, name=None):
        claims = [{"typ": "preferred_username", "val": upn}, {"typ": "groups", "val": group}]
        if name:
            claims.append({"typ": "name", "val": name})
        return base64.b64encode(json.dumps({"userId": upn, "claims": claims}).encode()).decode()

    def call(fn, who, method="GET", body=None, params=None, route=None, client=None):
        req = func.HttpRequest(method=method, url="/api/x", headers={"X-MS-CLIENT-PRINCIPAL": principal(who)}, params=params or {},
                               route_params=route or {}, body=json.dumps(body).encode() if body is not None else b"")
        # Durable routes: the route object is a FunctionBuilder holding the durable
        # wrapper, which holds the original function. Call the original, so the fake
        # client is used as-is instead of being parsed as Azure's binding string.
        if client:
            inner = fn._function._func if hasattr(fn, "_function") else fn
            r = asyncio.run(getattr(inner, "__wrapped__", inner)(req, client=client))
        else:
            r = fn(req)
        return r.status_code, json.loads(r.get_body() or b"{}")

    class FakeClient:
        async def start_new(self, name, instance_id=None, client_input=None):
            return instance_id

    alice, bob, carol = "alice@x.com", "bob@x.com", "carol@x.com"
    st, b = call(fa.me, alice)
    assert st == 200 and b["upn"] == alice and b["roles"] == ["ITAgent"]
    st, b = call(fa.workflow_start, alice, "POST", {"workflowDefId": "HARDWARE_REQUEST", "requesterUpn": "eve@x.com",
              "fields": {"itemDescription": "Dell Latitude 5450", "approverUpn": bob, "justification": "Old laptop failing"}}, client=FakeClient())
    assert st == 201 and b["reference"].startswith("REQ-"), b
    iid = b["instanceId"]
    fa.advance_workflow_instance(iid)  # what the orchestrator does next
    st, b = call(fa.workflow_my_requests, alice, params={"requesterUpn": "eve@x.com"})
    r = b["requests"][0]
    assert st == 200 and len(b["requests"]) == 1 and r["title"] == "Dell Latitude 5450" and r["state"] == "ManagerApproval"
    assert r["approverUpn"] == bob and r["justification"] == "Old laptop failing"
    assert call(fa.workflow_my_requests, "eve@x.com")[1]["requests"] == [], "spoofed requesterUpn was ignored"
    st, b = call(fa.workflow_my_approvals, bob)
    assert [x["instanceId"] for x in b["requests"]] == [iid] and [a["action"] for a in b["requests"][0]["availableActions"]] == ["approve", "reject"]
    assert call(fa.workflow_my_approvals, alice)[1]["requests"] == [], "requester sees nothing to approve"
    st, b = call(fa.workflow_action, alice, "POST", {"instanceId": iid, "action": "approve", "callerRole": "Approver", "callerUpn": bob})
    assert st == 403, "spoofed callerRole/callerUpn no longer work"
    st, b = call(fa.workflow_action, bob, "POST", {"instanceId": iid, "action": "reject"})
    assert st == 400 and "reason" in b["message"], "reject needs a reason"
    st, b = call(fa.workflow_action, bob, "POST", {"instanceId": iid, "action": "approve", "comment": "Approved, thanks"})
    assert st == 200 and b["request"]["state"] == "ITApproval"
    st, b = call(fa.workflow_my_approvals, carol)
    assert [x["instanceId"] for x in b["requests"]] == [iid], "IT agents now see it"
    assert call(fa.workflow_action, carol, "POST", {"instanceId": iid, "action": "approve"})[0] == 200
    assert call(fa.workflow_action, carol, "POST", {"instanceId": iid, "action": "markOrdered"})[0] == 403, "ordering needs IT admin"
    assert call(fa.workflow_action, ADMIN, "POST", {"instanceId": iid, "action": "markOrdered"})[0] == 200
    st, b = call(fa.workflow_action, ADMIN, "POST", {"instanceId": iid, "action": "captureSerial"})
    assert st == 400 and "serialNumber" in b["message"]
    st, b = call(fa.workflow_action, ADMIN, "POST", {"instanceId": iid, "action": "captureSerial", "fields": {"serialNumber": "SN-ABC123"}})
    assert st == 200 and b["request"]["status"] == "completed" and b["effects"], b
    st, b = call(fa.me_devices, alice)
    assert st == 200 and len(b["items"]) == 1, b
    st, b = call(fa.workflow_get_instance, alice, route={"instanceId": iid})
    tl = b["request"]["timeline"]
    assert st == 200 and [e["by"] for e in tl if e["by"]] == [alice, bob, carol, ADMIN, ADMIN]
    assert tl[2]["comment"] == "Approved, thanks" and "SN-ABC123" in tl[-1]["text"]
    assert [s["status"] for s in b["request"]["stages"]] == ["done"] * 6
    print("PASS: one request end to end as requester, manager, IT agent and IT admin; spoofing blocked; device registered to requester")


def test_no_self_decision_at_any_stage():
    # IT approval: the requester is an IT agent (everyone is, today) but must not decide on their own request.
    t_it = {"from": "ITApproval", "to": "Procurement", "action": "approve", "requiredRole": ["ITAgent", "ITAdmin"]}
    t_rej = {"from": "ITApproval", "to": "Rejected", "action": "reject", "requiredRole": ["ITAgent", "ITAdmin"]}
    t_ship = {"from": "AwaitingSerialCapture", "to": "Fulfilled", "action": "captureSerial", "requiredRole": "ITAdmin"}
    class Inst:
        requester_upn = "alice@x.com"
        def get_expected_approver_upn(self): return "bob@x.com"
        def get_fields(self): return {"approverUpn": "bob@x.com"}
    me = wa.Caller(upn="alice@x.com", display_name=None, roles={"ITAgent", "ITAdmin"})
    other = wa.Caller(upn="carol@x.com", display_name=None, roles={"ITAgent"})
    assert wa.caller_can(t_it, Inst(), me) == (False, "You can't approve or reject your own request.")
    assert wa.caller_can(t_rej, Inst(), me)[0] is False
    assert wa.caller_can(t_ship, Inst(), me)[0] is True, "fulfilment of your own request is allowed"
    assert wa.caller_can(t_it, Inst(), other)[0] is True
    class Approved(Inst):
        history = [{"action": "approve", "from": "ManagerApproval", "to": "ITApproval", "by": "carol@x.com"}]
    assert wa.caller_can(t_it, Approved(), other)[0] is False, "the manager who approved can't also give IT approval"
    print("PASS: nobody decides their own request; each approval stage needs a different person; fulfilment allowed")


if __name__ == "__main__":
    test_build_caller_roles()
    test_manager_permissions()
    test_available_actions_and_pending()
    test_stages_and_summary()
    test_parse_start_fields()
    test_no_self_decision_at_any_stage()
    test_routes_end_to_end()
    print("\nALL WORKFLOW ACCESS TESTS PASSED")
