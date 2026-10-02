"""
IT Helpdesk Portal — who may see and act on a request (Phase 1 identity)
========================================================================
Replaces the MVP's caller-asserted identity. Until now the browser sent
"requesterUpn", "callerUpn" and "callerRole" and the API believed them, so
anyone could file requests as someone else or approve as any role (review
finding 1). Everything here works from the signed-in identity instead:

  build_caller()       UPN, display name and roles, from the token + app settings
  caller_can()         may this caller take this transition on this request?
  available_actions()  the buttons this caller should see on a request
  can_view()           may this caller open this request at all?
  summarise()          the request as the portal shows it: title, progress
                       stages, timeline, available actions
  parse_start_fields() validates a new request's details (stored on the server
                       now, not in the requester's browser)

Roles
  Approver   not a standing role: the manager named on (or resolved for) a
             request may approve or reject THAT request, and never their own.
  ITAgent    IT approval. Every portal user is in the IT access group today, so
             all are IT agents unless IT_HELPDESK_ITAGENT_UPNS lists specific
             people (set it when the portal opens to all staff).
  ITAdmin    ordering and serial capture: UPNs in IT_HELPDESK_ITADMIN_UPNS, or
             an "ITAdmin" Entra app role in the token. An IT admin may also
             approve a request that has no manager recorded at all.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from workflow_store import WorkflowDefinition, WorkflowInstance, normalize_required_roles

KNOWN_ROLES = ("Approver", "ITAgent", "ITAdmin")
ADMIN_SETTING = "IT_HELPDESK_ITADMIN_UPNS"
AGENT_SETTING = "IT_HELPDESK_ITAGENT_UPNS"

WORKFLOW_LABELS = {"HARDWARE_REQUEST": "Hardware request"}
STATE_LABELS = {
    "Submitted": "Submitted", "ManagerApproval": "Manager approval", "ITApproval": "IT approval",
    "Procurement": "Ordering", "AwaitingSerialCapture": "Awaiting delivery", "Fulfilled": "Delivered",
    "Rejected": "Rejected",
}
ACTION_LABELS = {"approve": "Approve", "reject": "Reject", "markOrdered": "Mark as ordered",
                 "captureSerial": "Record serial and complete"}
FIELD_LABELS = {"serialNumber": "Serial number"}
ROLE_LABELS = {"Approver": "Manager", "ITAgent": "IT", "ITAdmin": "IT administrator"}
NEGATIVE_TERMINALS = {"Rejected", "Cancelled"}
DECISION_ACTIONS = {"approve", "reject"}
APPROVED_TEXT = {"ManagerApproval": "Approved by manager", "ITApproval": "Approved by IT"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RequestValidationError(Exception):
    """Invalid request details; message is safe to show."""


class NotPermittedError(Exception):
    """The caller may not see or do this; message is safe to show."""


@dataclass
class Caller:
    upn: str
    display_name: Optional[str]
    roles: Set[str] = field(default_factory=set)

    def to_api(self) -> Dict[str, Any]:
        roles = sorted(self.roles)
        return {"upn": self.upn, "displayName": self.display_name, "roles": roles,
                "roleLabels": [ROLE_LABELS.get(r, r) for r in roles]}


def _upn_list(value: Optional[str]) -> Set[str]:
    return {p.strip().lower() for p in re.split(r"[,;\s]+", value or "") if p.strip()}


def build_caller(identity, environ) -> Caller:
    """identity: auth_api.CallerIdentity (already through the group check)."""
    upn = (getattr(identity, "upn", None) or identity.user_name or identity.user_id or "").strip().lower()
    roles = {r for r in (getattr(identity, "roles", None) or []) if r in KNOWN_ROLES and r != "Approver"}
    agents = _upn_list(environ.get(AGENT_SETTING))
    if not agents or upn in agents:
        roles.add("ITAgent")
    if upn in _upn_list(environ.get(ADMIN_SETTING)):
        roles.add("ITAdmin")
    return Caller(upn=upn, display_name=getattr(identity, "display_name", None), roles=roles)


# ---------------------------------------------------------------- permissions
def expected_approver(instance: WorkflowInstance) -> Optional[str]:
    """The manager for this request: resolved from Entra (Graph) when that is
    available, otherwise the manager the requester named on the form."""
    resolved = instance.get_expected_approver_upn()
    if resolved:
        return resolved.strip().lower()
    named = instance.get_fields().get("approverUpn")
    return named.strip().lower() if isinstance(named, str) and named.strip() else None


def fallback_approver(transition: Dict[str, Any], instance: WorkflowInstance) -> Optional[str]:
    """Used when Graph manager lookup returns nothing: the named manager."""
    if transition.get("resolveApprover") != "requesterManager":
        return None
    named = instance.get_fields().get("approverUpn")
    return named.strip().lower() if isinstance(named, str) and named.strip() else None


def caller_can(transition: Dict[str, Any], instance: WorkflowInstance, caller: Caller) -> Tuple[bool, str]:
    required = normalize_required_roles(transition.get("requiredRole"))
    if not required:
        return True, ""
    requester = (instance.requester_upn or "").lower()
    # Nobody decides on their own request, at any approval stage. (Everyone in
    # the IT group is an IT agent today, so without this a requester could
    # approve their own request at IT approval.) Fulfilment steps such as
    # recording a serial number are not decisions and stay allowed.
    if caller.upn == requester and transition.get("action") in DECISION_ACTIONS:
        return False, "You can't approve or reject your own request."
    # Separation of duties: each approval stage needs a different person, so one
    # person can't approve as manager and then again as IT.
    if transition.get("action") in DECISION_ACTIONS and any(
            (e.get("by") or "").lower() == caller.upn and e.get("action") in DECISION_ACTIONS
            for e in (getattr(instance, "history", None) or [])):
        return False, "You've already decided an earlier step of this request; another person must decide this one."
    if "Approver" in required:
        manager = expected_approver(instance)
        if manager and caller.upn == manager:
            if caller.upn == requester:
                return False, "You can't approve your own request."
            return True, ""
        if not manager and "ITAdmin" in caller.roles:
            return True, ""
    if caller.roles & {r for r in required if r != "Approver"}:
        return True, ""
    if "Approver" in required:
        manager = expected_approver(instance)
        return False, (f"Only {manager} can approve this request." if manager
                       else "No manager is recorded for this request; an IT administrator must approve it.")
    needed = " or ".join(ROLE_LABELS.get(r, r) for r in required)
    return False, f"This step needs the {needed} role."


def available_actions(definition: WorkflowDefinition, instance: WorkflowInstance, caller: Caller) -> List[Dict[str, Any]]:
    if definition.is_terminal(instance.current_state):
        return []
    out = []
    for t in definition.transitions:
        if t["from"] != instance.current_state or not normalize_required_roles(t.get("requiredRole")):
            continue  # role-free transitions are taken automatically by the orchestrator
        if caller_can(t, instance, caller)[0]:
            out.append({
                "action": t["action"], "label": ACTION_LABELS.get(t["action"], t["action"]),
                "to": t["to"], "toLabel": STATE_LABELS.get(t["to"], t["to"]),
                "requiresComment": t["to"] in NEGATIVE_TERMINALS,
                "requiredFields": [{"name": f, "label": FIELD_LABELS.get(f, f)} for f in t.get("requiredFields", [])],
                "style": "danger" if t["to"] in NEGATIVE_TERMINALS else "primary",
            })
    return out


def can_view(instance: WorkflowInstance, caller: Caller) -> bool:
    return (caller.upn == (instance.requester_upn or "").lower()
            or caller.upn == (expected_approver(instance) or "")
            or bool(caller.roles & {"ITAgent", "ITAdmin"}))


def pending_for(instances: Iterable[WorkflowInstance], definitions: Dict[str, WorkflowDefinition], caller: Caller) -> List[WorkflowInstance]:
    seen, out = set(), []
    for i in instances:
        d = definitions.get(i.workflow_def_id)
        if i.instance_id in seen or d is None:
            continue
        seen.add(i.instance_id)
        if available_actions(d, i, caller):
            out.append(i)
    return sorted(out, key=lambda i: i.created_at)  # oldest first: longest waiting at the top


# ---------------------------------------------------------------- presentation
def _stages(definition: WorkflowDefinition, instance: WorkflowInstance) -> List[Dict[str, str]]:
    path = [s for s in definition.states if s not in NEGATIVE_TERMINALS]
    cur = instance.current_state
    stopped_at = None
    if cur in NEGATIVE_TERMINALS:
        stopped_at = next((e.get("from") for e in reversed(instance.history) if e.get("to") == cur), None)
    out, reached = [], True
    for s in path:
        if cur in NEGATIVE_TERMINALS:
            if s == stopped_at:
                status, reached = "rejected", False
            else:
                status = "done" if reached else "todo"
        elif s == cur:
            status, reached = ("done" if definition.is_terminal(cur) else "current"), False
        else:
            status = "done" if reached else "todo"
        out.append({"state": s, "label": STATE_LABELS.get(s, s), "status": status})
    return out


def _timeline(instance: WorkflowInstance) -> List[Dict[str, Any]]:
    out = []
    for e in instance.history:
        action, to = e.get("action"), e.get("to")
        if action == "submit":
            text = "Request submitted"
        elif action == "advance":
            text = f"Sent for {STATE_LABELS.get(to, to).lower()}"
            if e.get("expectedApproverUpn"):
                text += f" to {e['expectedApproverUpn']}"
        elif action == "approve":
            text = APPROVED_TEXT.get(e.get("from"), f"Approved at {STATE_LABELS.get(e.get('from'), e.get('from')).lower()}")
        elif action == "reject":
            text = f"Rejected at {STATE_LABELS.get(e.get('from'), e.get('from')).lower()}"
        elif action == "markOrdered":
            text = "Ordered"
        elif action == "captureSerial":
            serial = (e.get("fields") or {}).get("serialNumber")
            text = "Delivered and registered" + (f" (serial {serial})" if serial else "")
        else:
            text = f"{ACTION_LABELS.get(action, action)}: {STATE_LABELS.get(to, to)}"
        out.append({"at": e.get("at"), "text": text, "by": e.get("by"), "comment": e.get("comment")})
    return out


def reference(instance: WorkflowInstance) -> str:
    return "REQ-" + re.sub(r"[^A-Za-z0-9]", "", str(instance.instance_id))[:6].upper()


def summarise(instance: WorkflowInstance, definition: Optional[WorkflowDefinition], caller: Caller,
              detail: bool = False) -> Dict[str, Any]:
    f = instance.get_fields()
    cur = instance.current_state
    terminal = definition.is_terminal(cur) if definition else False
    label = WORKFLOW_LABELS.get(instance.workflow_def_id, instance.workflow_def_id.replace("_", " ").title())
    out = {
        "instanceId": instance.instance_id, "reference": reference(instance), "workflowDefId": instance.workflow_def_id,
        "workflowLabel": label, "title": f.get("itemDescription") or label,
        "quantity": f.get("quantity"), "justification": f.get("justification"), "neededBy": f.get("neededBy"),
        "requesterUpn": instance.requester_upn, "approverUpn": expected_approver(instance),
        "state": cur, "stateLabel": STATE_LABELS.get(cur, cur),
        "status": "rejected" if cur in NEGATIVE_TERMINALS else ("completed" if terminal else "open"),
        "createdAt": instance.created_at, "updatedAt": instance.updated_at,
        "stages": _stages(definition, instance) if definition else [],
        "availableActions": available_actions(definition, instance, caller) if definition else [],
        "serialNumber": f.get("serialNumber"),
    }
    if detail:
        out["timeline"] = _timeline(instance)
    return out


# ---------------------------------------------------------------- new requests
def parse_start_fields(workflow_def_id: str, body: Dict[str, Any], caller: Caller,
                       today: Optional[datetime.date] = None) -> Dict[str, Any]:
    raw = body.get("fields") if isinstance(body.get("fields"), dict) else {}
    today = today or datetime.datetime.utcnow().date()
    if workflow_def_id != "HARDWARE_REQUEST":
        return {k: str(v)[:500] for k, v in raw.items() if isinstance(v, (str, int, float))}
    item = str(raw.get("itemDescription") or "").strip()
    if not item:
        raise RequestValidationError("Describe the item you need.")
    approver = str(raw.get("approverUpn") or "").strip().lower()
    if not EMAIL_RE.match(approver):
        raise RequestValidationError("Enter your manager's email address, so they can approve the request.")
    if approver == caller.upn:
        raise RequestValidationError("You can't approve your own request. Enter your manager's email address.")
    raw_qty = raw.get("quantity")
    try:
        # Blank means 1; an explicit 0 must be rejected, not silently become 1.
        qty = 1 if raw_qty in (None, "") else int(raw_qty)
    except (TypeError, ValueError):
        raise RequestValidationError("Quantity must be a whole number.")
    if not 1 <= qty <= 50:
        raise RequestValidationError("Quantity must be between 1 and 50.")
    needed = str(raw.get("neededBy") or "").strip()
    if needed:
        try:
            if datetime.date.fromisoformat(needed[:10]) < today:
                raise RequestValidationError("The needed-by date is in the past.")
        except ValueError:
            raise RequestValidationError("Enter the needed-by date as a date.")
    out = {"itemDescription": item[:300], "approverUpn": approver, "quantity": qty}
    justification = str(raw.get("justification") or "").strip()
    if justification:
        out["justification"] = justification[:2000]
    if needed:
        out["neededBy"] = needed[:10]
    return out


def parse_comment(body: Dict[str, Any], required: bool) -> Optional[str]:
    comment = str(body.get("comment") or "").strip()[:1000] or None
    if required and not comment:
        raise RequestValidationError("Give a reason, so the requester knows what to do next.")
    return comment
