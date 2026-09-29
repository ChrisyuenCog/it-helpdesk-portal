
"""
IT Helpdesk Portal — Microsoft Graph integration (HD-030, HD-040)
====================================================================
HD-030: resolves a requester's line manager UPN via Microsoft Graph, so
HARDWARE_REQUEST's ManagerApproval state can dynamically address the
correct Approver with zero manual configuration.

HD-040 (this revision): reads a user's registered authentication/SSPR
methods via Microsoft Graph, so HD-041's self-service wizard can show
users their real registration status without an Entra admin-center trip.

*** DEPENDENCY / SCOPE NOTE — READ BEFORE RELYING ON THIS CODE ***
Both functions below require the Entra App Registration IT-Helpdesk-Platform
(HD-012) to exist, with the correct Graph API permissions granted and
admin-consented (Reports.Read.All / User.Read.All for manager lookups;
UserAuthenticationMethod.Read.All for authentication methods). As of this
revision, HD-012 is Batch B — "Manual Portal/Graph work, not a code PR" —
and has NOT yet been provisioned. Both functions are therefore CODE-COMPLETE
and offline-tested, but their LIVE Graph calls cannot be validated
end-to-end until HD-012 ships. Per this project's established MVP-tolerance
pattern, both are deliberately FAIL-SOFT: any error (missing permissions,
network failure, malformed response) results in a clean None return and a
logged warning — neither ever raises, and neither ever blocks the caller.
Once HD-012 lands, no code change is needed here; the Managed Identity will
simply start succeeding where it previously logged a graceful failure.

Deferred imports (azure-identity, requests) inside each function body match
sql_workflow_store.py's established pattern, so this module imports cleanly
in any environment, including an offline test sandbox, where those packages
may not be installed.
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def _manager_upn_from_graph_response(response_json: Dict[str, Any]) -> Optional[str]:
    """Pure, offline-testable parser: given a Graph API JSON response body
    for GET /users/{upn}/manager?$select=userPrincipalName, returns the
    manager's UPN, or None if the shape is missing/unexpected."""
    if not isinstance(response_json, dict):
        return None
    upn = response_json.get("userPrincipalName")
    if isinstance(upn, str) and upn.strip():
        return upn.strip()
    return None


def resolve_manager_upn(requester_upn: str) -> Optional[str]:
    """HD-030. Attempts to resolve requester_upn's manager via Microsoft
    Graph using the Function App's Managed Identity. Returns the manager's
    UPN on success, or None on ANY failure."""
    try:
        from azure.identity import DefaultAzureCredential
        import requests

        credential = DefaultAzureCredential()
        token = credential.get_token("https://graph.microsoft.com/.default")
        response = requests.get(
            f"{GRAPH_BASE_URL}/users/{requester_upn}/manager",
            headers={"Authorization": f"Bearer {token.token}"},
            params={"$select": "userPrincipalName"},
            timeout=10,
        )
        if response.status_code != 200:
            logging.warning(
                f"resolve_manager_upn: Graph returned {response.status_code} for "
                f"'{requester_upn}' — this is expected until HD-012's Entra App "
                f"Registration/permissions are provisioned. Falling back to None."
            )
            return None
        return _manager_upn_from_graph_response(response.json())
    except Exception as e:
        logging.warning(
            f"resolve_manager_upn: could not resolve manager for '{requester_upn}' "
            f"({e}). This is expected until HD-012 ships. Falling back to None."
        )
        return None


# ---------------------------------------------------------------------------
# HD-040: GET /api/identity/authMethods — registered SSPR/MFA methods
# ---------------------------------------------------------------------------
# Maps a Graph authenticationMethod's '@odata.type' to a short, human-
# readable label for display in HD-041's wizard. This mapping is pure and
# offline-testable — no Graph call required to exercise it. New method
# types Microsoft adds to Graph in future simply fall back to a readable
# derived label (see _method_type_label's fallback branch) rather than
# breaking or requiring a code change here.
_METHOD_TYPE_LABELS = {
    "#microsoft.graph.passwordAuthenticationMethod": "Password",
    "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod": "Microsoft Authenticator",
    "#microsoft.graph.phoneAuthenticationMethod": "Phone",
    "#microsoft.graph.fido2AuthenticationMethod": "Security Key (FIDO2)",
    "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod": "Windows Hello for Business",
    "#microsoft.graph.softwareOathAuthenticationMethod": "Authenticator App (OATH)",
    "#microsoft.graph.emailAuthenticationMethod": "Email",
}

# Password always exists trivially for every account and is not itself a
# second/MFA factor — HD-041's "zero registered methods" flag must be
# computed excluding it, otherwise every user would always show as
# "registered" regardless of real MFA/SSPR method registration.
NON_MFA_METHOD_TYPES = {"Password"}


def _method_type_label(method: Dict[str, Any]) -> str:
    """Pure, offline-testable: maps one raw Graph authenticationMethod
    entry to a short display label. Falls back to a readable derived name
    for any '@odata.type' not in the explicit mapping above, rather than
    raising or returning a raw, ugly odata type string."""
    odata_type = method.get("@odata.type", "") or ""
    if odata_type in _METHOD_TYPE_LABELS:
        return _METHOD_TYPE_LABELS[odata_type]
    derived = odata_type.replace("#microsoft.graph.", "").replace("AuthenticationMethod", "")
    return derived if derived else "Unknown method"


def parse_auth_methods_response(response_json: Any) -> Optional[List[Dict[str, Any]]]:
    """Pure, offline-testable parser: given a Graph API JSON response body
    for GET /users/{upn}/authentication/methods, returns a list of
    {"type": <label>, "id": <method id>} dicts, or None if the response
    shape is missing/unexpected (e.g. not a dict, or missing the 'value'
    array Graph always returns for a collection endpoint)."""
    if not isinstance(response_json, dict):
        return None
    raw_methods = response_json.get("value")
    if not isinstance(raw_methods, list):
        return None
    parsed: List[Dict[str, Any]] = []
    for method in raw_methods:
        if not isinstance(method, dict):
            continue
        parsed.append({
            "type": _method_type_label(method),
            "id": method.get("id"),
        })
    return parsed


def get_auth_methods(upn: str) -> Optional[List[Dict[str, Any]]]:
    """HD-040. Attempts to read upn's registered authentication methods via
    Microsoft Graph using the Function App's Managed Identity. Returns a
    parsed list on success, or None on ANY failure (missing permissions,
    network failure, malformed response) — fail-soft, matching
    resolve_manager_upn's precedent exactly. Connection-dependent —
    validated manually against a live tenant once HD-012's Graph
    permissions are provisioned, per runbook.md Section 6."""
    try:
        from azure.identity import DefaultAzureCredential
        import requests

        credential = DefaultAzureCredential()
        token = credential.get_token("https://graph.microsoft.com/.default")
        response = requests.get(
            f"{GRAPH_BASE_URL}/users/{upn}/authentication/methods",
            headers={"Authorization": f"Bearer {token.token}"},
            timeout=10,
        )
        if response.status_code != 200:
            logging.warning(
                f"get_auth_methods: Graph returned {response.status_code} for "
                f"'{upn}' — this is expected until HD-012's Entra App "
                f"Registration/permissions are provisioned. Falling back to None."
            )
            return None
        return parse_auth_methods_response(response.json())
    except Exception as e:
        logging.warning(
            f"get_auth_methods: could not read authentication methods for "
            f"'{upn}' ({e}). This is expected until HD-012 ships. Falling back to None."
        )
        return None
