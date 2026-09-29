
"""
IT Helpdesk Portal — Workflow "On Enter" Effects (HD-034)
============================================================
HD-034: when a workflow_instance enters a state whose incoming transition
declares 'onEnterEffects', this module executes those effects generically
— driven entirely by DATA on the transition, never by a hardcoded category
name. This file contains zero references to "Hardware" as a Python
conditional; HARDWARE_REQUEST's Fulfilled transition simply happens to be
the first transition to configure an effect of type "createCi" (see
workflow_store.py's _seed_hardware_request_definition), exactly matching
this project's "generic engine, configured via data" design principle
already stated in every prior ticket's module docstring.

Currently supported effect types:
  - "createCi": creates a new CI in the CMDB (via cmdb_store.CmdbStore,
    the same abstraction Batch A shipped) using values pulled from the
    instance's accumulated fields (WorkflowInstance.get_fields() — see
    workflow_store.py), then optionally creates a relationship from the
    instance's requester to that new CI. Config keys read from the effect
    dict: 'ciClass' (required), 'relationshipType' (optional — if absent,
    no relationship is created), 'nameField' (which key in
    instance.get_fields() supplies the CI's name — falls back to a
    generic placeholder if the field was never actually captured, since a
    cosmetic missing name should never block a state transition that has
    already passed its hard requiredFields gate), 'statusValue' (the CI's
    initial status, e.g. "InService").

Adding a second effect type in a future ticket (e.g. "closeExternalTicket"
for INCIDENT_ESCALATION) means adding one more `elif effect_type == ...`
branch here — never touching function_app.py, workflow_action_api.py, or
any workflow_definition OTHER than the one that configures it.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List

from cmdb_store import CmdbStore
from workflow_store import WorkflowInstance


def _apply_create_ci_effect(
    cmdb_store: CmdbStore, instance: WorkflowInstance, effect: Dict[str, Any]
) -> Dict[str, Any]:
    """Executes a single 'createCi' effect. Never raises — an effect
    failure (e.g. a CMDB write error) is logged and reported in the
    returned dict's 'error' key, rather than crashing the state transition
    that has already legitimately completed. The state transition itself
    is the source of truth; this is a best-effort side effect."""
    ci_class = effect.get("ciClass")
    name_field = effect.get("nameField")
    fields = instance.get_fields()
    name = fields.get(name_field) if name_field else None
    if not name:
        name = f"{ci_class} — from workflow instance {instance.instance_id}"
    status_value = effect.get("statusValue", "InService")
    try:
        new_ci = cmdb_store.create_ci(
            ci_class=ci_class,
            name=name,
            status=status_value,
            owner=instance.requester_upn,
            entity=None,
        )
    except Exception as e:
        logging.exception(f"workflow_effects_api: failed to create CI for instance {instance.instance_id}")
        return {"effectType": "createCi", "error": str(e)}
    result: Dict[str, Any] = {"effectType": "createCi", "ciId": new_ci.ci_id, "ciClass": new_ci.ci_class}
    relationship_type = effect.get("relationshipType")
    if relationship_type and instance.requester_upn:
        try:
            relationship = cmdb_store.create_relationship(
                from_ci_id=instance.requester_upn,
                to_ci_id=new_ci.ci_id,
                relationship_type=relationship_type,
            )
            result["relationshipId"] = relationship.relationship_id
            result["relationshipType"] = relationship.relationship_type
        except Exception as e:
            logging.exception(f"workflow_effects_api: failed to create relationship for CI {new_ci.ci_id}")
            result["relationshipError"] = str(e)
    return result


def apply_enter_effects(
    cmdb_store: CmdbStore, instance: WorkflowInstance, transition: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """The single entry point function_app.py calls after a transition
    completes. Reads transition.get('onEnterEffects', []) — an empty or
    absent list (i.e. every existing TEST/TEST_APPROVAL transition, and
    every HARDWARE_REQUEST transition except AwaitingSerialCapture->
    Fulfilled) is a complete no-op, returning an empty list with zero
    side effects and zero CMDB calls, preserving every prior ticket's
    behaviour exactly."""
    effects_config = transition.get("onEnterEffects", [])
    results: List[Dict[str, Any]] = []
    for effect in effects_config:
        effect_type = effect.get("type")
        if effect_type == "createCi":
            results.append(_apply_create_ci_effect(cmdb_store, instance, effect))
        else:
            logging.warning(f"workflow_effects_api: unknown effect type '{effect_type}' — skipped.")
    return results
