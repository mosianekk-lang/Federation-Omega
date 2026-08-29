from __future__ import annotations
import importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"realityguard_v0.4.0"/"src"))
from federation.orchestration import CapabilityRoute,CapabilitySelector,ConcurrencyGuard,ExecutionEnvelope,FailureMemoryRecord,MissionLease,NearMissEvent,PreWriteFence,WorkstreamObservation
from realityguard import ExecutionGuard,GuardDecision
SPEC=importlib.util.spec_from_file_location("provider_airlock_activate_spine",ROOT/"phoenix"/"provider_airlock_activate.py"); assert SPEC and SPEC.loader; AIRLOCK=importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name]=AIRLOCK; SPEC.loader.exec_module(AIRLOCK)
MAIN="a"*40; NEXT="b"*40; ISSUED="2026-08-29T18:00:00+00:00"; EXPIRES="2026-08-29T19:00:00+00:00"; NOW="2026-08-29T18:30:00+00:00"
def lease(): return MissionLease.create(mission_id="SOVARA-DEPLOYMENT-20260829",lane_id="safety-spine",holder_id="federation",base_main_sha=MAIN,lease_epoch=1,path_scope=["sovara","federation/orchestration","governance","realityguard_v0.4.0"],issued_at=ISSUED,expires_at=EXPIRES)
def effect_request(): return {"schema_version":"realityguard.execution-guard.v1","request":{"request_id":"DEPLOY-1","tool_name":"provider.deploy","operation":"deploy","effect_class":"DEPLOYMENT","target":{"service":"synthetic"},"payload":{"artifact_ref":"sha256:"+"a"*64},"expected_fruit":{"provider_state":"CANARY_READY"},"idempotency_key":"deploy-synthetic-1"},"authority":{"formation_permit_consumed":True,"permit_single_use":True,"action_binding_matches":True,"proof_ref":"formation:synthetic"},"route":{"readback_supported":True,"semantic_canary_verified":True,"canary_proof_ref":"canary:synthetic","inline_binary_supported":False,"inline_binary_canary_verified":False},"retry":{"attempt":1,"previous_attempts":[],"exact_repair":""}}
class DeploymentSafetySpineTests(unittest.TestCase):
    def test_clean_current_main_allows_fenced_internal_write(self):
        d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=MAIN,now=NOW); r=PreWriteFence().authorise(lease=lease(),decision=d,current_main_sha=MAIN,intended_paths=["sovara/creative/router.py"]); self.assertTrue(r.allowed); self.assertEqual("PREWRITE_FENCE_VERIFIED",r.reason)
    def test_moving_main_never_inherits_old_write_authority(self):
        d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=NEXT,now=NOW,main_changed_paths=["docs/unrelated.md"]); self.assertFalse(d.write_allowed); self.assertEqual("MAIN_DRIFT_FAST_RECONVERGE",d.state)
    def test_overlapping_workstream_is_serialized(self):
        w=WorkstreamObservation.create(workstream_id="other",base_sha=MAIN,head_sha=NEXT,paths=["sovara/creative"]); d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=MAIN,now=NOW,active_workstreams=[w]); self.assertEqual("ACTIVE_WORKSTREAM_OVERLAP_HOLD",d.state); self.assertFalse(d.write_allowed)
    def test_dynamic_failure_memory_blocks_unchanged_retry_without_static_wif_floor(self):
        f=FailureMemoryRecord(fingerprint="CURRENT_PROVIDER_FAILURE",route_id="GITHUB_TO_PROVIDER",status="OPEN",failure_proof_ref="run:1",retry_condition="require newer provider receipt"); route=CapabilityRoute(route_id="GITHUB_TO_PROVIDER",capability_id="PROVIDER_CANARY",reality_state="C4",required_reality_state="C3",readiness="READY",authority_required="A1_INTERNAL",proof_ref="source:current"); sel=CapabilitySelector().select(routes=[route],memories=[f]); self.assertEqual("",sel.selected_route_id); self.assertIn("GITHUB_TO_PROVIDER",sel.blocked_routes); self.assertNotIn("KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET",(ROOT/"federation"/"orchestration"/"mission_arbitration.py").read_text())
    def test_cfbe_route_fitness_is_multidimensional(self):
        route=CapabilityRoute(route_id="A",capability_id="cap",reality_state="C4",proof_ref="proof",quality=.9,reliability=.9,freshness=.9,proof_strength=.9,latency=.1,cost=.1,owner_burden=.1,risk=.1); self.assertGreater(route.score,.7)
    def test_near_miss_learning_is_bound_to_proof(self):
        e=NearMissEvent.create(mission_id="SOVARA-DEPLOYMENT-20260829",route_id="A",prevented_action="provider.deploy",prevention_reason="STALE_MAIN_FENCE",proof_refs=["main:old","main:new"]); self.assertEqual(64,len(e.event_digest))
    def test_completion_claim_requires_authorization_execution_readback_and_receipt(self):
        p=ExecutionEnvelope(mission_id="M",operation_id="O",authorization_ref="auth",execution_ref="exec"); self.assertFalse(p.completion_claim_allowed); c=ExecutionEnvelope(mission_id="M",operation_id="O",authorization_ref="auth",execution_ref="exec",target_readback_ref="readback",expected_target_digest="x",observed_target_digest="x",receipt_ref="receipt"); self.assertTrue(c.completion_claim_allowed)
    def test_provider_airlock_requires_full_three_check_release_court(self):
        ruleset=json.loads((ROOT/"governance"/"federation_omega_main_airlock.ruleset.json").read_text()); AIRLOCK.validate_ruleset(ruleset); status=next(x for x in ruleset["rules"] if x["type"]=="required_status_checks"); self.assertEqual(["admission","contract","scan"],[x["context"] for x in status["parameters"]["required_status_checks"]])
    def test_provider_activation_state_preserves_absent_provider_enforcement(self):
        state=json.loads((ROOT/"governance"/"provider_airlock_activation_state.json").read_text()); self.assertFalse(state["provider_state"]["provider_apply_performed"]); self.assertEqual("ABSENT_PROVIDER_READBACK",state["provider_state"]["main_ruleset_active"]); self.assertEqual(0,state["provider_observation"]["ruleset_count"])
    def test_realityguard_blocks_missing_effect_authority(self):
        p=effect_request(); p["authority"]["formation_permit_consumed"]=False; self.assertEqual(GuardDecision.BLOCK_INVALID_AUTHORITY,ExecutionGuard().preflight_tool_call(p).decision)
    def test_realityguard_transport_or_receipt_alone_cannot_release_deployment_claim(self):
        g=ExecutionGuard(); pre=g.preflight_tool_call(effect_request()); r=g.observe_dispatch(pre,{"transport_succeeded":True}); self.assertFalse(g.guard_claim_release(r,"CANARY_READY")["claim_authorized"]); r=g.observe_dispatch(pre,{"transport_succeeded":True,"provider_receipt":{"provider_id":"provider-1","request_fingerprint":pre.request_fingerprint,"current":True}}); self.assertFalse(g.guard_claim_release(r,"CANARY_READY")["claim_authorized"])
    def test_realityguard_releases_only_independently_readback_state(self):
        g=ExecutionGuard(); pre=g.preflight_tool_call(effect_request()); r=g.observe_dispatch(pre,{"transport_succeeded":True,"provider_receipt":{"provider_id":"provider-1","request_fingerprint":pre.request_fingerprint,"current":True,"proof_ref":"provider:receipt"},"semantic_readback":{"current":True,"independent":True,"matches_expected":True,"verified_states":["CANARY_READY"],"proof_ref":"provider:readback"}}); self.assertTrue(g.guard_claim_release(r,"CANARY_READY")["claim_authorized"]); self.assertFalse(g.guard_claim_release(r,"PRODUCTION")["claim_authorized"])
if __name__=="__main__": unittest.main()
