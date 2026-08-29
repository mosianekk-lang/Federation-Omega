from __future__ import annotations

import unittest
from federation.orchestration import CapabilityRoute, CapabilitySelector, ConcurrencyGuard, FailureMemoryRecord, FailureStatus, MissionLease, MissionSnapshot, NearMissEvent, PreWriteFence, WorkstreamObservation

MAIN="a"*40; NEXT="b"*40; ISSUED="2026-08-29T18:00:00+00:00"; EXPIRES="2026-08-29T19:00:00+00:00"; NOW="2026-08-29T18:30:00+00:00"

def lease(): return MissionLease.create(mission_id="M-1",lane_id="lane",holder_id="federation",base_main_sha=MAIN,lease_epoch=1,path_scope=["federation/orchestration","sovara"],issued_at=ISSUED,expires_at=EXPIRES)

class MissionArbitrationV2Tests(unittest.TestCase):
    def test_stale_main_never_inherits_write_authority(self):
        d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=NEXT,now=NOW,main_changed_paths=["docs/unrelated.md"]); self.assertFalse(d.write_allowed); self.assertEqual("MAIN_DRIFT_FAST_RECONVERGE",d.state)
    def test_overlap_serializes(self):
        w=WorkstreamObservation.create(workstream_id="other",base_sha=MAIN,head_sha=NEXT,paths=["sovara/creative"]); d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=MAIN,now=NOW,active_workstreams=[w]); self.assertEqual("ACTIVE_WORKSTREAM_OVERLAP_HOLD",d.state)
    def test_prewrite_fence_requires_current_main_and_scope(self):
        d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=MAIN,now=NOW); r=PreWriteFence().authorise(lease=lease(),decision=d,intended_paths=["sovara/creative/router.py"]); self.assertTrue(r.allowed)
    def test_open_failure_blocks_unchanged_route(self):
        m=FailureMemoryRecord(fingerprint="PROVIDER_FAILURE_001",route_id="route-a",status=FailureStatus.OPEN,failure_proof_ref="run:1",retry_condition="new provider proof"); route=CapabilityRoute(route_id="route-a",capability_id="cap",reality_state="C4",proof_ref="source:1"); self.assertEqual("",CapabilitySelector().select(routes=[route],memories=[m]).selected_route_id)
    def test_closed_failure_requires_bound_recovery_proof(self):
        m=FailureMemoryRecord(fingerprint="PROVIDER_FAILURE_001",route_id="route-a",status=FailureStatus.CLOSED,failure_proof_ref="run:1",retry_condition="new provider proof",recovery_proof_ref="provider:recovered"); held=CapabilityRoute(route_id="route-a",capability_id="cap",reality_state="C4",proof_ref="source:1"); admitted=CapabilityRoute(route_id="route-a",capability_id="cap",reality_state="C4",proof_ref="source:1",retry_evidence_refs=("provider:recovered",)); self.assertEqual("",CapabilitySelector().select(routes=[held],memories=[m]).selected_route_id); self.assertEqual("route-a",CapabilitySelector().select(routes=[admitted],memories=[m]).selected_route_id)
    def test_cfbe_multidimensional_score_prefers_stronger_route(self):
        strong=CapabilityRoute(route_id="strong",capability_id="cap",reality_state="C4",proof_ref="proof:strong",quality=.9,reliability=.9,freshness=.9,proof_strength=.9,latency=.1,cost=.1,owner_burden=.1,risk=.1); weak=CapabilityRoute(route_id="weak",capability_id="cap",reality_state="C4",proof_ref="proof:weak",quality=.5,reliability=.5,freshness=.5,proof_strength=.5,latency=.8,cost=.8,owner_burden=.8,risk=.8); result=CapabilitySelector().select(routes=[weak,strong],memories=[]); self.assertEqual("strong",result.selected_route_id); self.assertGreater(strong.score,weak.score)
    def test_near_miss_is_deterministic_learning_evidence(self):
        a=NearMissEvent.create(mission_id="M-1",route_id="route-a",prevented_action="provider.write",prevention_reason="STALE_MAIN_FENCE",proof_refs=["main:old","main:new"]); b=NearMissEvent.create(mission_id="M-1",route_id="route-a",prevented_action="provider.write",prevention_reason="STALE_MAIN_FENCE",proof_refs=["main:new","main:old"]); self.assertEqual(a.event_digest,b.event_digest)
    def test_snapshot_binds_failure_memory_route_scores_and_near_miss(self):
        d=ConcurrencyGuard().evaluate(lease=lease(),current_main_sha=MAIN,now=NOW); route=CapabilityRoute(route_id="route-a",capability_id="cap",reality_state="C4",proof_ref="proof"); sel=CapabilitySelector().select(routes=[route],memories=[]); m=FailureMemoryRecord(fingerprint="OLD_FAILURE_001",route_id="old-route",status=FailureStatus.OPEN,failure_proof_ref="run:old",retry_condition="repair"); n=NearMissEvent.create(mission_id="M-1",route_id="old-route",prevented_action="retry",prevention_reason="KNOWN_OPEN_FAILURE",proof_refs=["run:old"]); s=MissionSnapshot.create(lease=lease(),current_main_sha=MAIN,concurrency=d,selection=sel,memories=[m],near_misses=[n]); self.assertIn("OLD_FAILURE_001",s.failure_fingerprints); self.assertTrue(s.near_miss_refs); self.assertTrue(s.route_scores)
    def test_no_static_historical_wif_failure_constant_is_exposed(self):
        import federation.orchestration as o; self.assertFalse(hasattr(o,"KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET"))

if __name__=="__main__": unittest.main()
