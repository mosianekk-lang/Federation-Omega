from __future__ import annotations

import unittest

from federation.capability_truth_v1 import CapabilityEligibilityCourt, CapabilityRequirement, Maturity
from federation.live_worker_attestation_v1 import (
    CapabilityEpoch, WorkerAttestation, WorkerAttestationCourt, WorkerState,
)

NOW="2026-09-06T22:25:00+02:00"


def epoch(eid="E1", *, valid=True, expires="2026-09-06T23:00:00+02:00"):
    return CapabilityEpoch(eid,"AGENT_RUNTIME","2026-09-06T22:00:00+02:00",expires,"provider:epoch",valid)


def att(state, *, aid="A1", worker="W1", eid="E1", expires="2026-09-06T22:50:00+02:00", heartbeat="hb:1", result="result:1", independent=False):
    kw=dict(attestation_id=aid,worker_id=worker,capability_id="AGENT_RUNTIME",epoch_id=eid,state=state,observed_at="2026-09-06T22:10:00+02:00",expires_at=expires,source_ref=f"source:{aid}",runtime_id="",mission_id="",tool_refs=(),heartbeat_ref="",result_ref="",independently_verified=independent)
    if state>=WorkerState.RUNTIME_AVAILABLE: kw["runtime_id"]="runtime-1"
    if state>=WorkerState.TOOL_BOUND: kw["tool_refs"]=("tool:github",)
    if state>=WorkerState.MISSION_ASSIGNED: kw["mission_id"]="MISSION-1"
    if state>=WorkerState.HEARTBEAT_VERIFIED: kw["heartbeat_ref"]=heartbeat
    if state>=WorkerState.RESULT_VERIFIED: kw["result_ref"]=result
    return WorkerAttestation(**kw)


class LiveWorkerAttestationTests(unittest.TestCase):
    def setUp(self): self.court=WorkerAttestationCourt()

    def test_registered_worker_is_not_live(self):
        a=att(WorkerState.REGISTERED); self.assertFalse(self.court.decide(a,epoch(),now=NOW).live)

    def test_runtime_available_without_heartbeat_is_not_live(self):
        self.assertFalse(self.court.decide(att(WorkerState.RUNTIME_AVAILABLE),epoch(),now=NOW).live)

    def test_tool_bound_worker_without_heartbeat_is_not_live(self):
        self.assertFalse(self.court.decide(att(WorkerState.TOOL_BOUND),epoch(),now=NOW).live)

    def test_mission_assigned_worker_without_heartbeat_is_not_live(self):
        self.assertFalse(self.court.decide(att(WorkerState.MISSION_ASSIGNED),epoch(),now=NOW).live)

    def test_heartbeat_verified_worker_is_live(self):
        self.assertTrue(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED),epoch(),now=NOW).live)

    def test_result_verified_worker_is_live(self):
        self.assertTrue(self.court.decide(att(WorkerState.RESULT_VERIFIED),epoch(),now=NOW).live)

    def test_epoch_mismatch_invalidates_worker(self):
        self.assertFalse(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED,eid="OLD"),epoch(),now=NOW).live)

    def test_expired_epoch_invalidates_worker(self):
        self.assertFalse(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED),epoch(expires="2026-09-06T22:20:00+02:00"),now=NOW).live)

    def test_invalid_epoch_invalidates_worker(self):
        self.assertFalse(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED),epoch(valid=False),now=NOW).live)

    def test_expired_attestation_invalidates_worker(self):
        self.assertFalse(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED,expires="2026-09-06T22:20:00+02:00"),epoch(),now=NOW).live)

    def test_epoch_subject_mismatch_invalidates_worker(self):
        e=CapabilityEpoch("E1","OTHER","2026-09-06T22:00:00+02:00","2026-09-06T23:00:00+02:00","provider:e")
        self.assertFalse(self.court.decide(att(WorkerState.HEARTBEAT_VERIFIED),e,now=NOW).live)

    def test_runtime_state_requires_runtime_id(self):
        a=WorkerAttestation("A","W","AGENT_RUNTIME","E1",WorkerState.RUNTIME_AVAILABLE,"2026-09-06T22:10:00+02:00","2026-09-06T22:40:00+02:00","s")
        with self.assertRaises(ValueError): a.validate()

    def test_tool_bound_requires_tool_ref(self):
        a=WorkerAttestation("A","W","AGENT_RUNTIME","E1",WorkerState.TOOL_BOUND,"2026-09-06T22:10:00+02:00","2026-09-06T22:40:00+02:00","s",runtime_id="r")
        with self.assertRaises(ValueError): a.validate()

    def test_mission_assigned_requires_mission(self):
        a=WorkerAttestation("A","W","AGENT_RUNTIME","E1",WorkerState.MISSION_ASSIGNED,"2026-09-06T22:10:00+02:00","2026-09-06T22:40:00+02:00","s",runtime_id="r",tool_refs=("t",))
        with self.assertRaises(ValueError): a.validate()

    def test_heartbeat_state_requires_receipt(self):
        a=WorkerAttestation("A","W","AGENT_RUNTIME","E1",WorkerState.HEARTBEAT_VERIFIED,"2026-09-06T22:10:00+02:00","2026-09-06T22:40:00+02:00","s",runtime_id="r",mission_id="m",tool_refs=("t",))
        with self.assertRaises(ValueError): a.validate()

    def test_result_state_requires_result_ref(self):
        a=WorkerAttestation("A","W","AGENT_RUNTIME","E1",WorkerState.RESULT_VERIFIED,"2026-09-06T22:10:00+02:00","2026-09-06T22:40:00+02:00","s",runtime_id="r",mission_id="m",tool_refs=("t",),heartbeat_ref="h")
        with self.assertRaises(ValueError): a.validate()

    def test_registered_evidence_ceiling_is_designed(self):
        ev=self.court.to_evidence(att(WorkerState.REGISTERED),epoch(),now=NOW); self.assertEqual(Maturity.DESIGNED,ev.admitted_maturity)

    def test_runtime_available_evidence_ceiling_is_hosted(self):
        ev=self.court.to_evidence(att(WorkerState.RUNTIME_AVAILABLE),epoch(),now=NOW); self.assertEqual(Maturity.HOSTED,ev.admitted_maturity)

    def test_heartbeat_evidence_reaches_provider_running(self):
        ev=self.court.to_evidence(att(WorkerState.HEARTBEAT_VERIFIED),epoch(),now=NOW); self.assertEqual(Maturity.PROVIDER_RUNNING,ev.admitted_maturity); self.assertEqual("hb:1",ev.source_ref)

    def test_result_evidence_reaches_behaviour_verified(self):
        ev=self.court.to_evidence(att(WorkerState.RESULT_VERIFIED),epoch(),now=NOW); self.assertEqual(Maturity.BEHAVIOUR_VERIFIED,ev.admitted_maturity); self.assertEqual("result:1",ev.source_ref)

    def test_stale_attestation_produces_stale_evidence(self):
        ev=self.court.to_evidence(att(WorkerState.HEARTBEAT_VERIFIED,expires="2026-09-06T22:20:00+02:00"),epoch(),now=NOW); self.assertFalse(ev.fresh)

    def test_old_epoch_produces_stale_evidence(self):
        ev=self.court.to_evidence(att(WorkerState.HEARTBEAT_VERIFIED,eid="OLD"),epoch(),now=NOW); self.assertFalse(ev.fresh)

    def test_live_workers_counts_only_fresh_heartbeat_workers(self):
        xs=[att(WorkerState.REGISTERED,aid="a",worker="reg"),att(WorkerState.HEARTBEAT_VERIFIED,aid="b",worker="live"),att(WorkerState.HEARTBEAT_VERIFIED,aid="c",worker="old",eid="OLD")]
        self.assertEqual(("live",),self.court.live_workers(xs,epoch(),now=NOW))

    def test_record_can_satisfy_runtime_capability_requirement(self):
        rec=self.court.record_for_capability("AGENT_RUNTIME",[att(WorkerState.HEARTBEAT_VERIFIED)],epoch(),now=NOW)
        d=CapabilityEligibilityCourt().decide(CapabilityRequirement("AGENT_RUNTIME",Maturity.PROVIDER_RUNNING),rec)
        self.assertTrue(d.eligible)

    def test_registration_only_record_cannot_satisfy_runtime_requirement(self):
        rec=self.court.record_for_capability("AGENT_RUNTIME",[att(WorkerState.REGISTERED)],epoch(),now=NOW)
        d=CapabilityEligibilityCourt().decide(CapabilityRequirement("AGENT_RUNTIME",Maturity.PROVIDER_RUNNING),rec)
        self.assertFalse(d.eligible)

    def test_independent_verification_is_preserved_only_when_declared(self):
        ev=self.court.to_evidence(att(WorkerState.HEARTBEAT_VERIFIED,independent=True),epoch(),now=NOW); self.assertTrue(ev.independently_verified)

    def test_retired_worker_cannot_produce_evidence(self):
        a=att(WorkerState.RESULT_VERIFIED)
        a=WorkerAttestation(a.attestation_id,a.worker_id,a.capability_id,a.epoch_id,WorkerState.RETIRED,a.observed_at,a.expires_at,a.source_ref,runtime_id=a.runtime_id,mission_id=a.mission_id,tool_refs=a.tool_refs,heartbeat_ref=a.heartbeat_ref,result_ref=a.result_ref)
        with self.assertRaises(ValueError): self.court.to_evidence(a,epoch(),now=NOW)

if __name__=="__main__": unittest.main()
