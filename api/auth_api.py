"""
IT Helpdesk Portal — Access Control (Batch K, brought forward)
================================================================
HD-066/067/068/069 — SCOPE CHANGE from the original MVP Specification.

*** WHY THIS DIFFERS FROM THE MVP SPEC'S 5-ROLE MODEL ***
The MVP Specification (Section 3) defined 5 Entra ID App Roles (Requester,
Approver, ITAgent, ITAdmin, Executive) so every CLG employee could submit
requests, with IT staff/execs getting elevated views. Chris has now
explicitly narrowed this: for this phase, the ENTIRE portal (frontend +
every API route) is restricted to members of a single Entra ID security
group — CLG - IT and Digital Transformation — rather than being open to
all employees. This is a deliberate simplification, not an oversight:
  - No "Requester" self-service for the wider business yet.
  - No dynamic per-request Approver resolution (Graph manager lookup) —
    deferred, since only the IT team itself can reach the portal at all.
  - HD-013/014 (5 App Roles, 3 separate Entra groups) are superseded by a
    single group gate. If/when the portal re-opens to all employees, the
    original 5-role model can be layered back in without re-architecting
    this module — group_id below just becomes one of several recognised
    groups instead of the only one.

*** THE GROUP ***
CLG - IT and Digital Transformation
Object ID: 49cab434-8d81-44fd-b871-ecead72becdc
(Confirmed directly from Entra admin center — Groups | All groups.)

*** HOW ACCESS IS ENFORCED ***
Two layers, matching the MVP spec's "defence in depth" principle (Section
3.3), adapted for a single-group model:
  1. Platform layer: Azure Function App "Easy Auth" (App Service
     Authentication) is configured with the Azure AD provider and
     "Require authentication" = On. This rejects any unauthenticated
     caller before this code ever runs.
  2. Application layer (this module): even though Easy Auth guarantees the
     caller is *some* authenticated CLG user, it does NOT by itself
     guarantee group membership unless Conditional Access/App Roles are
     also configured. This module independently re-checks the caller's
     group claim from the X-MS-CLIENT-PRINCIPAL header Easy Auth injects,
     so a Function App misconfiguration at the Portal layer cannot
     silently grant access to the whole of CLG.

*** IT_HELPDESK_ADMIN_PIN STEP-UP (HD-067/068/069) ***
Independent of group-gating above: Strictly Confidential Document CIs
(e.g. Cyber Essentials Plus network-scope material) require an
*additional* PIN step-up, same pattern as every other CLG dashboard
(Asset Register, HR Dashboard, Impact Dashboard) — a signed HMAC session
token, 8-hour TTL, no server-side session store. The PIN whitespace-
stripping fix (HD-068) is applied proactively here from the start, since
this exact bug has recurred at least twice elsewhere at CLG.

*** health ROUTE EXCEPTION ***
GET /api/health intentionally stays on func.AuthLevel.ANONYMOUS and does
NOT call require_access_group() — it is a liveness probe with no CLG data
in its response body (see function_app.py), and gating it would break
existing uptime/monitoring checks that call it unauthenticated.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, List

try:
    import azure.functions as func  # type: ignore
except ImportError:  # pragma: no cover - allows offline unit testing without the azure-functions package installed
    func = None  # type: ignore

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# The Entra ID security group whose members are the ONLY users permitted to
# reach any route in this portal. Set via Function App Application Setting
# IT_HELPDESK_ACCESS_GROUP_ID.
#
# >>> CONFIRMED real value for CLG - IT and Digital Transformation: <<<
#     49cab434-8d81-44fd-b871-ecead72becdc
# Set this exact value as the IT_HELPDESK_ACCESS_GROUP_ID app setting — do
# not hardcode it here, so the same code works unmodified in any future
# environment (e.g. a test slot) that might gate on a different group.
ACCESS_GROUP_SETTING_NAME = "IT_HELPDESK_ACCESS_GROUP_ID"

PIN_SETTING_NAME = "IT_HELPDESK_ADMIN_PIN"
TOKEN_SECRET_SETTING_NAME = "IT_HELPDESK_PIN_TOKEN_SECRET"
PIN_SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours, matches every other CLG dashboard
PIN_SESSION_HEADER_NAME = "X-Pin-Session-Token"


class AccessDeniedError(Exception):
    """Raised when the caller is not a member of the required Entra group."""
    pass


class PinVerificationError(Exception):
    """Raised when a submitted PIN is wrong, or a session token is invalid/expired."""
    pass


@dataclass
class CallerIdentity:
    user_id: str
    user_name: Optional[str]
    group_ids: List[str]


# ---------------------------------------------------------------------------
# Easy Auth claim parsing
# ---------------------------------------------------------------------------
def _parse_client_principal(req: "func.HttpRequest") -> Optional[CallerIdentity]:
    """
    Azure App Service Authentication ("Easy Auth") injects a base64-encoded
    JSON blob in the X-MS-CLIENT-PRINCIPAL header once "Require
    authentication" is enabled on the Function App. Returns None if the
    header is absent (e.g. local testing without Easy Auth) — callers must
    decide how to treat that case; in production, Easy Auth's own "Require
    authentication" setting means this should never actually be None for a
    real request.
    """
    header_value = req.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header_value:
        return None
    try:
        decoded = base64.b64decode(header_value).decode("utf-8")
        claims_payload = json.loads(decoded)
    except Exception:
        logging.exception("auth_api: failed to parse X-MS-CLIENT-PRINCIPAL header")
        return None

    user_id = claims_payload.get("userId") or claims_payload.get("name")
    claims = claims_payload.get("claims", [])
    user_name = None
    group_ids: List[str] = []
    for claim in claims:
        claim_type = claim.get("typ", "")
        claim_value = claim.get("val", "")
        if claim_type in ("name", "preferred_username", "upn"):
            user_name = user_name or claim_value
        # Entra ID issues group membership as "groups" claims (or the full
        # "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
        # URI, depending on token version/overage behaviour) — check both.
        if claim_type in ("groups", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"):
            group_ids.append(claim_value)

    return CallerIdentity(user_id=user_id or "unknown", user_name=user_name, group_ids=group_ids)


def require_access_group(req: "func.HttpRequest") -> CallerIdentity:
    """
    HD-066 (adapted): call this at the top of EVERY route in function_app.py
    (except the unauthenticated /api/health liveness probe).
    Raises AccessDeniedError unless the caller's token contains the CLG -
    IT and Digital Transformation group's Object ID
    (49cab434-8d81-44fd-b871-ecead72becdc), read from the
    IT_HELPDESK_ACCESS_GROUP_ID app setting.
    """
    required_group_id = os.environ.get(ACCESS_GROUP_SETTING_NAME)
    if not required_group_id:
        # Fail CLOSED, not open: if the app setting is missing, nobody
        # gets access rather than everybody getting access. A misconfigured
        # deployment must never silently become an open portal.
        logging.error(
            f"auth_api: {ACCESS_GROUP_SETTING_NAME} app setting is not configured — "
            f"denying all access until this is set."
        )
        raise AccessDeniedError(
            "Access control is not yet configured for this deployment. Contact the IT and Digital Transformation team."
        )

    identity = _parse_client_principal(req)
    if identity is None:
        raise AccessDeniedError("No authenticated identity found on the request.")

    if required_group_id not in identity.group_ids:
        logging.warning(
            f"auth_api: access denied for user '{identity.user_name or identity.user_id}' "
            f"— not a member of the required group."
        )
        raise AccessDeniedError(
            "This portal is restricted to the CLG IT and Digital Transformation team."
        )

    return identity


def build_access_denied_response(message: str) -> "func.HttpResponse":
    return func.HttpResponse(
        json.dumps({"error": message}),
        mimetype="application/json",
        status_code=403,
    )


# ---------------------------------------------------------------------------
# HD-067/068 — PIN step-up for Strictly Confidential documents
# ---------------------------------------------------------------------------
def _pin_matches(submitted_pin: str, stored_pin: str) -> bool:
    """
    HD-068: proactively applies the whitespace-stripping fix already hit
    twice elsewhere at CLG (CLG HR Dashboard's NOTES_ADMIN_PIN, IT Asset
    Register's ASSET_REGISTER_ADMIN_PIN) — strip BOTH sides before an
    exact, constant-time comparison.
    """
    return hmac.compare_digest((submitted_pin or "").strip(), (stored_pin or "").strip())


def _sign_token(payload: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_pin(submitted_pin: str) -> str:
    """
    HD-067: verifies the submitted PIN against IT_HELPDESK_ADMIN_PIN and,
    on success, returns a signed, stateless session token good for 8 hours.
    Raises PinVerificationError on an incorrect PIN or missing configuration.
    """
    stored_pin = os.environ.get(PIN_SETTING_NAME)
    token_secret = os.environ.get(TOKEN_SECRET_SETTING_NAME)
    if not stored_pin or not token_secret:
        raise PinVerificationError("PIN step-up is not configured for this deployment.")

    if not _pin_matches(submitted_pin, stored_pin):
        raise PinVerificationError("Incorrect PIN.")

    expires_at = int(time.time()) + PIN_SESSION_TTL_SECONDS
    payload = f"strictly-confidential-access|{expires_at}"
    return _sign_token(payload, token_secret)


def validate_pin_session_token(token: Optional[str]) -> bool:
    """
    HD-069: validates a previously-issued PIN session token. Returns True
    only if the signature is valid AND the token has not expired.
    """
    token_secret = os.environ.get(TOKEN_SECRET_SETTING_NAME)
    if not token_secret or not token:
        return False
    try:
        payload, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected_signature = hmac.new(token_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False
    try:
        _, expires_at_str = payload.split("|")
        expires_at = int(expires_at_str)
    except (ValueError, IndexError):
        return False
    return time.time() < expires_at


def get_pin_session_token_from_request(req: "func.HttpRequest") -> Optional[str]:
    """HD-069 helper: reads the step-up token from the agreed request header."""
    return req.headers.get(PIN_SESSION_HEADER_NAME)
