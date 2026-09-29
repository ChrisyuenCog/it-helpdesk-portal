
"""
IT Helpdesk Portal — Identity/SSPR API request/response logic (HD-039/040/041)
=================================================================================
Pure request-validation and response-building logic for:
  GET /api/identity/authMethods?upn=       (HD-040)
Separated from the Azure Functions HTTP trigger in function_app.py, same
pattern as every other *_api.py module in this repo, so this ticket is
offline-testable without a live Function host or a live Graph tenant.

HD-039 (SSPR tile linking directly to aka.ms/sspr) and HD-041 (the guided
wizard UI built on top of this endpoint's response) are frontend-only
tickets — see web/index.html — and have no backend logic of their own
beyond this single endpoint.

Scope note (same MVP-stage caveat as every other identity-adjacent module
in this repo): 'upn' is accepted as a caller-supplied query parameter, not
a validated Entra ID token claim — real identity binding is Sprint 4's
Security Hardening epic (HD-066).
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List

from graph_api import NON_MFA_METHOD_TYPES


class AuthMethodsValidationError(Exception):
    """Raised when the required ?upn= query parameter is missing from
    GET /api/identity/authMethods — maps to HTTP 400 in function_app.py."""
    pass


def parse_auth_methods_query(query_params: Dict[str, str]) -> str:
    """Returns the validated upn string, or raises
    AuthMethodsValidationError. Kept as its own function (rather than
    inlined in the HTTP trigger) so the exact validation rule is
    independently offline-testable, matching this repo's established
    query-parsing precedent (parse_my_requests_query, parse_ci_id, etc.)."""
    upn = query_params.get("upn")
    if not upn or not upn.strip():
        raise AuthMethodsValidationError(
            "'upn' query parameter is required, e.g. "
            "?upn=chris.yuen@cognitionlearninggroup.com"
        )
    return upn.strip()


def build_auth_methods_response(upn: str, methods: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """HD-040/041. Builds the response shape the wizard consumes.

    When `methods` is None (Graph call failed or HD-012 isn't provisioned
    yet — see graph_api.py's module docstring), returns 'available: False'
    with a human-readable reason, rather than an HTTP error — this endpoint
    ALWAYS returns 200 on a syntactically valid request; unavailability of
    the underlying Graph data is a normal, expected MVP-stage condition,
    not a caller error. HD-041's frontend wizard is designed to gracefully
    fall back to 'go register at aka.ms/sspr' in this case rather than
    blocking the user (see index.html's module docstring).

    'hasAnyMethod' deliberately excludes Password (see
    graph_api.NON_MFA_METHOD_TYPES) — every account trivially has a
    password, so counting it would make every user appear registered
    regardless of real MFA/SSPR method registration, defeating HD-041's
    'flags users with zero registered methods' acceptance criterion."""
    if methods is None:
        return {
            "upn": upn,
            "available": False,
            "reason": (
                "Unable to read authentication methods from Microsoft Graph. "
                "This is expected until HD-012's Entra App Registration and "
                "Graph permissions are provisioned."
            ),
            "hasAnyMethod": False,
            "methodCount": 0,
            "methods": [],
        }
    real_methods = [m for m in methods if m.get("type") not in NON_MFA_METHOD_TYPES]
    return {
        "upn": upn,
        "available": True,
        "hasAnyMethod": len(real_methods) > 0,
        "methodCount": len(real_methods),
        "methods": methods,
    }
