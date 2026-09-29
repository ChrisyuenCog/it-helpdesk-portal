
"""
IT Helpdesk Portal — CMDB API request/response logic (HD-019/020/021)
=========================================================================
Pure request-validation and response-building logic for:
  GET /api/cmdb/ci/{ciId}                    (HD-019)
  GET /api/cmdb/ci?class=&owner=             (HD-020)
  GET /api/cmdb/relationships?ciId=          (HD-021)
Separated from the Azure Functions HTTP triggers in function_app.py,
following the exact same pattern as workflow_instance_api.py (HD-027) and
workflow_list_api.py (HD-028/029), so this ticket is also offline-testable
without a live Durable Functions host or a live database.

Scope note (same MVP-stage caveat already documented in workflow_action_api.py
and workflow_list_api.py): these endpoints are unauthenticated reads for
MVP demonstration purposes — real Entra ID token validation and Row-Level
Security are Sprint 4's Security Hardening epic (HD-066), not yet built.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List

from cmdb_store import CmdbStore, CIBase, CIRelationship, CmdbStoreError
from workflow_api import build_error_response  # reused for a single, consistent error shape


class CiNotFoundError(Exception):
    """Raised when ciId does not refer to a known ci_base row — maps to
    HTTP 404 in function_app.py. Kept as its own exception (rather than
    reusing CmdbStoreError directly) so the HTTP trigger's except clause
    reads the same way as workflow_instance_api.py's InstanceNotFoundError."""
    pass


class RelationshipsValidationError(Exception):
    """Raised when the required ?ciId= query parameter is missing from
    GET /api/cmdb/relationships — maps to HTTP 400 in function_app.py."""
    pass


def parse_ci_id(route_param: Optional[str]) -> str:
    """Validates the {ciId} route parameter itself is present. Does not
    check whether it refers to a real CI — that is a separate, subsequent
    step (see load_ci_view below), matching workflow_instance_api.py's
    parse_instance_id precedent."""
    if not route_param or not isinstance(route_param, str):
        raise CiNotFoundError("ciId path parameter is required.")
    return route_param


def load_ci_view(store: CmdbStore, ci_id: str) -> Dict[str, Any]:
    """HD-019. The single entry point this ticket's HTTP trigger calls.
    Raises CiNotFoundError (-> 404) if ciId is unknown; any other
    CmdbStoreError is left to propagate as-is, matching HD-027's precedent
    of surfacing unexpected store errors rather than masking them behind a
    misleading 404."""
    try:
        ci: CIBase = store.get_ci(ci_id)
    except CmdbStoreError as e:
        raise CiNotFoundError(str(e))
    return build_ci_summary(ci)


def build_ci_summary(ci: CIBase) -> Dict[str, Any]:
    """Same shape used for both the single-CI view (HD-019) and each row of
    the list view (HD-020) — there is exactly one place a CIBase becomes
    JSON, so the two endpoints can never silently drift out of sync on
    field names."""
    return {
        "ciId": ci.ci_id,
        "ciClass": ci.ci_class,
        "name": ci.name,
        "status": ci.status,
        "owner": ci.owner,
        "entity": ci.entity,
        "createdAt": ci.created_at,
    }


def parse_list_ci_query(query_params: Dict[str, str]) -> Dict[str, Optional[str]]:
    """HD-020. Both 'class' and 'owner' are optional filters — supplying
    neither returns every CI, matching the MVP spec's
    'GET /api/cmdb/ci?class=Hardware&owner={user}' example, where either
    query parameter may be omitted. There is no validation error case here
    (unlike myRequests/myApprovals, which require their filter), since an
    unfiltered CI listing is itself a valid, meaningful request."""
    return {
        "ci_class": query_params.get("class") or None,
        "owner": query_params.get("owner") or None,
    }


def build_ci_list_response(cis: List[CIBase], ci_class: Optional[str], owner: Optional[str]) -> Dict[str, Any]:
    return {
        "class": ci_class,
        "owner": owner,
        "count": len(cis),
        "items": [build_ci_summary(ci) for ci in cis],
    }


def parse_relationships_query(query_params: Dict[str, str]) -> str:
    """HD-021. Returns the validated ciId string, or raises
    RelationshipsValidationError. Kept as its own function (rather than
    inlined in the HTTP trigger) so the exact validation rule is
    independently offline-testable, matching workflow_list_api.py's
    parse_my_requests_query precedent."""
    ci_id = query_params.get("ciId")
    if not ci_id or not ci_id.strip():
        raise RelationshipsValidationError(
            "'ciId' query parameter is required, e.g. ?ciId=<a known ciId>"
        )
    return ci_id.strip()


def build_relationship_summary(relationship: CIRelationship) -> Dict[str, Any]:
    return {
        "relationshipId": relationship.relationship_id,
        "fromCiId": relationship.from_ci_id,
        "toCiId": relationship.to_ci_id,
        "relationshipType": relationship.relationship_type,
        "createdAt": relationship.created_at,
    }


def build_relationships_response(relationships: List[CIRelationship], ci_id: str) -> Dict[str, Any]:
    return {
        "ciId": ci_id,
        "count": len(relationships),
        "relationships": [build_relationship_summary(r) for r in relationships],
    }
