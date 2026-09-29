
"""
IT Helpdesk Portal — Microsoft Graph integration (HD-030)
============================================================
HD-030: resolves a requester's line manager UPN via Microsoft Graph, so
HARDWARE_REQUEST's ManagerApproval state can dynamically address the
correct Approver with zero manual configuration (MVP Specification
Section 3.1: "Approver ... resolved dynamically via Graph manager lookup").

*** DEPENDENCY / SCOPE NOTE — READ BEFORE RELYING ON THIS CODE ***
Calling Microsoft Graph's /users/{upn}/manager endpoint via the Function
App's Managed Identity requires the Entra App Registration
IT-Helpdesk-Platform (HD-012) to exist, with User.Read.All / Reports.Read.All
Graph API permissions granted and admin-consented. As of this revision,
HD-012 is Batch B — "Manual Portal/Graph work, not a code PR" — and has NOT
yet been provisioned (see the IT Helpdesk Portal MVP Build Backlog, Batch B
status: Not Started). This module is therefore CODE-COMPLETE and
offline-tested, but resolve_manager_upn()'s live Graph call cannot be
validated end-to-end until HD-012 ships. Per this project's established
MVP-tolerance pattern (see workflow_instance_api.py's _get_sla_view() and
workflow_action_api.py's resolve_expected_approver()), this function is
deliberately FAIL-SOFT: any error (missing permissions, network failure,
user has no manager, malformed response) results in a clean None return
and a logged warning — it never raises, and it never blocks the underlying
workflow transition. Once HD-012 lands, no code change is needed here;
the Managed Identity will simply start succeeding where it previously
logged a graceful failure.

Deferred imports (azure-identity, requests) inside the function body match
sql_workflow_store.py's established pattern, so this module imports cleanly
in any environment, including this offline test sandbox, where those
packages may not be installed.
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


def _manager_upn_from_graph_response(response_json: Dict[str, Any]) -> Optional[str]:
    """Pure, offline-testable parser: given a Graph API JSON response body
    for GET /users/{upn}/manager?$select=userPrincipalName, returns the
    manager's UPN, or None if the shape is missing/unexpected (e.g. the
    requester has no manager assigned in Entra, which Graph represents in
    various ways depending on tenant configuration — this function treats
    any non-conforming shape as 'no manager', not an error)."""
    if not isinstance(response_json, dict):
        return None
    upn = response_json.get("userPrincipalName")
    if isinstance(upn, str) and upn.strip():
        return upn.strip()
    return None


def resolve_manager_upn(requester_upn: str) -> Optional[str]:
    """HD-030. Attempts to resolve requester_upn's manager via Microsoft
    Graph using the Function App's Managed Identity. Returns the manager's
    UPN on success, or None on ANY failure (see module docstring for why
    this is intentionally fail-soft rather than raising). Connection-
    dependent — validated manually against a live tenant once HD-012's
    Graph permissions are provisioned, per runbook.md Section 6, matching
    the precedent already established for SqlWorkflowStore/SqlCmdbStore's
    connection-dependent methods."""
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
