
"""
Offline tests for workflow_effects_api.py (HD-034) — exercises
apply_enter_effects against a real InMemoryCmdbStore (Batch A), no live
Azure SQL or Function host required.
"""
from cmdb_store import InMemoryCmdbStore
from workflow_store import WorkflowInstance
from workflow_effects_api import apply_enter_effects

print("=== Test 1 (HD-034): a transition with no onEnterEffects is a complete no-op ===")
cmdb_store = InMemoryCmdbStore()
instance = WorkflowInstance(instance_id="i1", workflow_def_id="TEST", current_state="Middle")
transition_no_effects = {"from": "Start", "to": "Middle", "action": "advance"}
results = apply_enter_effects(cmdb_store, instance, transition_no_effects)
assert results == []
# Confirm zero CMDB side effects — CI count unchanged from the seeded demo CI only.
assert len(cmdb_store.list_ci()) == 1
print("PASS — no effects configured, no CI created, empty list returned\n")

print("=== Test 2 (HD-034): a createCi effect creates a new CI owned by the requester ===")
instance2 = WorkflowInstance(
    instance_id="i2", workflow_def_id="HARDWARE_REQUEST", current_state="Fulfilled",
    requester_upn="carol@cognitionlearninggroup.com",
)
instance2.record_transition(
    "AwaitingSerialCapture", "Fulfilled", "captureSerial",
    fields={"itemDescription": "Dell Latitude 5450", "serialNumber": "SN-777"},
)
transition_with_effect = {
    "from": "AwaitingSerialCapture", "to": "Fulfilled", "action": "captureSerial",
    "onEnterEffects": [{
        "type": "createCi", "ciClass": "Hardware", "relationshipType": "user has",
        "nameField": "itemDescription", "statusValue": "InService",
    }],
}
results2 = apply_enter_effects(cmdb_store, instance2, transition_with_effect)
assert len(results2) == 1
assert results2[0]["effectType"] == "createCi"
assert "ciId" in results2[0]
new_ci = cmdb_store.get_ci(results2[0]["ciId"])
assert new_ci.ci_class == "Hardware"
assert new_ci.name == "Dell Latitude 5450"
assert new_ci.status == "InService"
assert new_ci.owner == "carol@cognitionlearninggroup.com"
print(f"PASS — CI created: {new_ci.ci_id}, name='{new_ci.name}', owner='{new_ci.owner}'\n")

print("=== Test 3 (HD-034): the createCi effect also creates the 'user has' relationship ===")
assert "relationshipId" in results2[0]
assert results2[0]["relationshipType"] == "user has"
relationships = cmdb_store.get_relationships_for_ci(new_ci.ci_id)
assert len(relationships) == 1
assert relationships[0].from_ci_id == "carol@cognitionlearninggroup.com"
assert relationships[0].to_ci_id == new_ci.ci_id
print(f"PASS — relationship created: {relationships[0].relationship_id} "
      f"({relationships[0].from_ci_id} -> {relationships[0].to_ci_id})\n")

print("=== Test 4 (HD-034): createCi falls back to a generic name if nameField is missing from captured fields ===")
instance3 = WorkflowInstance(
    instance_id="i3", workflow_def_id="HARDWARE_REQUEST", current_state="Fulfilled",
    requester_upn="dave@cognitionlearninggroup.com",
)
instance3.record_transition("AwaitingSerialCapture", "Fulfilled", "captureSerial", fields={"serialNumber": "SN-888"})
results3 = apply_enter_effects(cmdb_store, instance3, transition_with_effect)
new_ci3 = cmdb_store.get_ci(results3[0]["ciId"])
assert "Hardware" in new_ci3.name
assert instance3.instance_id in new_ci3.name
print(f"PASS — missing nameField falls back to a generic, still-useful name: '{new_ci3.name}' "
      f"(never crashes the state transition over cosmetic missing data)\n")

print("=== Test 5 (HD-034): no relationship is created if relationshipType is absent from the effect config ===")
instance4 = WorkflowInstance(instance_id="i4", workflow_def_id="HARDWARE_REQUEST", current_state="Fulfilled", requester_upn="eve@x.com")
instance4.record_transition("AwaitingSerialCapture", "Fulfilled", "captureSerial", fields={"itemDescription": "Monitor"})
transition_no_relationship = {
    "from": "AwaitingSerialCapture", "to": "Fulfilled", "action": "captureSerial",
    "onEnterEffects": [{"type": "createCi", "ciClass": "Hardware", "nameField": "itemDescription", "statusValue": "InService"}],
}
results4 = apply_enter_effects(cmdb_store, instance4, transition_no_relationship)
assert "relationshipId" not in results4[0]
print("PASS — relationshipType is genuinely optional; omitting it correctly skips relationship creation\n")

print("=== Test 6 (HD-034): an unknown effect type is skipped gracefully, not an error ===")
transition_unknown_effect = {
    "from": "A", "to": "B", "action": "x",
    "onEnterEffects": [{"type": "someFutureEffectType"}],
}
results5 = apply_enter_effects(cmdb_store, instance, transition_unknown_effect)
assert results5 == []
print("PASS — unknown effect types are logged and skipped, never raise\n")

print("=" * 60)
print("ALL WORKFLOW EFFECTS API OFFLINE TESTS PASSED — HD-034's createCi effect")
print("verified end-to-end against a real InMemoryCmdbStore, including the")
print("owner/name/status mapping, relationship creation, and graceful degradation.")
