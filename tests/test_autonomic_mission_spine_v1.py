from __future__ import annotations

from dataclasses import replace
import unittest

from federation.action_admission_gate_v1 import ActionRequest, AuthorityGrant
from federation.autonomic_mission_spine_v1 import (
    ActionExecutionBundle,
    AutonomicMissionSpine,
    SpineStage,
)
from federation.capability_truth_v1 import CapabilityTruthRecord, ClaimKind, EvidenceRef, Maturity
from federation.cfbe_chat_hyperperformance_v1 import EffectClass, RouteProfile, WorkUnit
from federation.execution_readback_closure_v1 import ExecutionAttempt, SemanticReadback
from federation.execution_topology_compiler_v1 import TopologyTask
from federation.live_worker_attestation_v1 import CapabilityEpoch, WorkerAttestation, WorkerState
from federation.mission_capability_admission_v1 import MissionCapabilityRequirement
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import OutcomeEvidence, RequiredAction, ValueObservation

NOW = "2026-09-06T22:55:00+02:00"


def mission(*, mutation: bool = False, values=("owner_interrupts",)) -> MissionIR:
    return MissionIR(
        mission_id="m-spine-1",
        objective="finish only through the FUSE proof spine",
        domain="FEDERATION",
        outcome_contract="all required work complete and verified",
        source_frontier="signed-main",
        privacy_class="P1_INTERNAL",
        rights_state="OWNER_AUTHORIZED",
        effect_class="BOUNDED_EFFECT" if mutation else "READ_ONLY",
        rollback_required=mutation,
        authority_requirements=("AUTH_WRITE",) if mutation else (),
        proof_requirements=("effect_receipts", "outcome_readback"),
        value_metrics=values,
    )


def truth(*, kind=ClaimKind.RUNTIME_RECEIPT, maturity=Maturity.PROVIDER_RUNNING, fresh=True):
    e = EvidenceRef(
        "e-cap", "CAP_A", kind, "provider:capability",
        maturity, fresh=fresh, independently_verified=True,
    )
    return {"CAP_A": CapabilityTruthRecord("CAP_A").add(e)}


def epoch() -> CapabilityEpoch:
    return CapabilityEpoch(
        epoch_id="epoch-CAP_A",
        subject="CAP_A",
        observed_at="2026-09-06T22:30:00+02:00",
        expires_at="2026-09-06T23:30:00+02:00",
        source_ref="provider:epoch",
    )


def worker(*, state=WorkerState.HEARTBEAT_VERIFIED, runtime="runtime-1") -> WorkerAttestation:
    return WorkerAttestation(
        attestation_id="att-w1",
        worker_id="w1",
        capability_id="CAP_A",
        epoch_id="epoch-CAP_A",
        state=state,
        observed_at="2026-09-06T22:45:00+02:00",
        expires_at="2026-09-06T23:10:00+02:00",
        source_ref="provider:worker",
        runtime_id=runtime if state >= WorkerState.RUNTIME_AVAILABLE else "",
        mission_id="m-spine-1" if state >= WorkerState.MISSION_ASSIGNED else "",
        tool_refs=("tool:github",) if state >= WorkerState.TOOL_BOUND else (),
        heartbeat_ref="provider:heartbeat" if state >= WorkerState.HEARTBEAT_VERIFIED else "",
        result_ref="provider:result" if state >= WorkerState.RESULT_VERIFIED else "",
        independently_verified=True,
    )


def route() -> tuple[RouteProfile, ...]:
    return (
        RouteProfile(
            route_id="github-direct", surface="github",
            available=True, fresh=True, direct=True,
            proof_refs=("provider:route",),
        ),
    )


def task(*, mutation=False) -> TopologyTask:
    effect = EffectClass.INTERNAL_WRITE if mutation else EffectClass.READ_ONLY
    return TopologyTask(
        WorkUnit(
            unit_id="u1", surface="github", operation="act",
            input_fingerprint="input-u1", effect_class=effect,
            cacheable=True,
        ),
        capability_id="CAP_A",
        mutation_domain="repo:main" if mutation else "",
    )


def request(*, mutation=False) -> ActionRequest:
    effect = EffectClass.INTERNAL_WRITE if mutation else EffectClass.READ_ONLY
    return ActionRequest(
        action_id="a1", unit_id="u1", effect_class=effect,
        target_scope="repo:main",
        mutation_domain="repo:main" if mutation else "",
    )


def grant() -> AuthorityGrant:
    return AuthorityGrant(
        grant_id="g1", mission_id="m-spine-1", action_id="a1",
        effect_class=EffectClass.INTERNAL_WRITE, target_scope="repo:main",
        source_ref="authority:grant", observed_at="2026-09-06T22:45:00+02:00",
        expires_at="2026-09-06T23:20:00+02:00",
        authority_refs=("AUTH_WRITE",), current_state_ref="provider:prestate",
        readback_contract_ref="provider:readback-contract",
        rollback_plan_ref="provider:rollback-plan", idempotency_key="idem-1",
    )


def attempt(*, mutation=False, write_ack=False) -> ExecutionAttempt:
    effect = EffectClass.INTERNAL_WRITE if mutation else EffectClass.READ_ONLY
    # action-admission digest is filled by helper after admission when needed
    return ExecutionAttempt(
        attempt_id="attempt-1", action_admission_digest="PLACEHOLDER",
        mission_id="m-spine-1", action_id="a1", unit_id="u1",
        effect_class=effect, target_scope="repo:main", idempotency_key="idem-1",
        request_fingerprint="request-v1", pre_state_fingerprint="pre-v1",
        transport_ref="provider:transport" if mutation else "",
        write_ack_ref="provider:ack" if write_ack else "",
    )


def readback(*, behaviour=True) -> SemanticReadback:
    return SemanticReadback(
        readback_id="rb1", attempt_id="attempt-1", provider_ref="provider:readback",
        target_scope="repo:main", observed_state_fingerprint="post-v1",
        expected_state_fingerprint="post-v1", semantic_match=True, fresh=True,
        provider_native=True, behaviour_ref="provider:behaviour" if behaviour else "",
    )


def outcome(m: MissionIR) -> OutcomeEvidence:
    return OutcomeEvidence(
        "out1", m.mission_id, m.outcome_contract,
        "provider:outcome", True, True,
    )


def values() -> tuple[ValueObservation, ...]:
    return (ValueObservation("owner_interrupts", "metrics:owner", "0", True, True),)


class AutonomicMissionSpineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spine = AutonomicMissionSpine()
        self.req = (MissionCapabilityRequirement("CAP_A", Maturity.PROVIDER_RUNNING),)

    def base_kwargs(self, m: MissionIR, *, workers=None, records=None, mutation=False, bundles=()):
        return dict(
            mission=m,
            capability_requirements=self.req,
            truth_records=truth() if records is None else records,
            topology_tasks=(task(mutation=mutation),),
            routes=route(),
            worker_attestations=(worker(),) if workers is None else workers,
            capability_epochs={"CAP_A": epoch()},
            action_bundles=bundles,
            required_actions=(RequiredAction("a1", require_behaviour=True),),
            now=NOW,
            outcome_evidence=outcome(m),
            proof_evidence={"effect_receipts": "proof:effects", "outcome_readback": "proof:outcome"},
            value_observations=values(),
        )

    def test_specification_only_capability_holds_before_topology(self) -> None:
        m = mission()
        rec = truth(kind=ClaimKind.REQUIREMENT, maturity=Maturity.PROVIDER_RUNNING)
        r = self.spine.run(**self.base_kwargs(m, records=rec))
        self.assertEqual(SpineStage.HELD, r.final_snapshot.stage)
        self.assertEqual("MISSION_HELD_CAPABILITY_GAP", r.final_snapshot.state)
        self.assertIsNone(r.topology)

    def test_registered_worker_does_not_advance_past_topology(self) -> None:
        m = mission()
        r = self.spine.run(**self.base_kwargs(m, workers=(worker(state=WorkerState.MISSION_ASSIGNED),)))
        self.assertEqual(SpineStage.HELD, r.final_snapshot.stage)
        self.assertEqual("TOPOLOGY_HELD_NO_LIVE_CAPACITY", r.final_snapshot.state)
        self.assertEqual((), r.action_admissions)

    def test_ready_topology_cannot_bypass_missing_mutation_authority(self) -> None:
        m = mission(mutation=True)
        bundle = ActionExecutionBundle(request=request(mutation=True), grant=None)
        r = self.spine.run(**self.base_kwargs(m, mutation=True, bundles=(bundle,)))
        self.assertEqual(SpineStage.HELD, r.final_snapshot.stage)
        self.assertEqual("ACTIONS_HELD_NOT_ADMITTED", r.final_snapshot.state)
        self.assertTrue(r.topology and r.topology.executable)
        self.assertFalse(r.action_admissions[0].admitted)

    def test_write_ack_only_cannot_advance_to_execution_closed(self) -> None:
        m = mission(mutation=True)
        # obtain exact action-admission digest using the spine's own lower courts
        adm = self.spine.capability_compiler.admit(m, self.req, truth())
        topo = self.spine.topology_compiler.compile(
            mission=m, admission=adm, tasks=(task(mutation=True),), routes=route(),
            attestations=(worker(),), epochs={"CAP_A": epoch()}, now=NOW,
        )
        aa = self.spine.action_gate.admit(
            mission=m, topology=topo, request=request(mutation=True), grant=grant(), now=NOW,
        )
        att = replace(attempt(mutation=True, write_ack=True), action_admission_digest=aa.receipt_digest)
        bundle = ActionExecutionBundle(request=request(mutation=True), grant=grant(), attempt=att)
        r = self.spine.run(**self.base_kwargs(m, mutation=True, bundles=(bundle,)))
        self.assertEqual(SpineStage.HELD, r.final_snapshot.stage)
        self.assertEqual("EXECUTION_HELD_NOT_SEMANTICALLY_CLOSED", r.final_snapshot.state)
        self.assertEqual("WRITE_ACKNOWLEDGED", r.closures[0].state.value)

    def test_semantic_action_success_without_outcome_or_value_still_holds_mission(self) -> None:
        m = mission()
        adm = self.spine.capability_compiler.admit(m, self.req, truth())
        topo = self.spine.topology_compiler.compile(
            mission=m, admission=adm, tasks=(task(),), routes=route(), attestations=(worker(),),
            epochs={"CAP_A": epoch()}, now=NOW,
        )
        aa = self.spine.action_gate.admit(mission=m, topology=topo, request=request(), now=NOW)
        att = replace(attempt(), action_admission_digest=aa.receipt_digest)
        bundle = ActionExecutionBundle(request=request(), grant=None, attempt=att, readback=readback())
        kw = self.base_kwargs(m, bundles=(bundle,))
        kw["outcome_evidence"] = None
        kw["value_observations"] = ()
        r = self.spine.run(**kw)
        self.assertEqual(SpineStage.HELD, r.final_snapshot.stage)
        self.assertTrue(r.closures[0].effect_verified)
        self.assertIsNotNone(r.outcome)

    def test_full_chain_reaches_value_observed_only_with_all_proofs(self) -> None:
        m = mission()
        adm = self.spine.capability_compiler.admit(m, self.req, truth())
        topo = self.spine.topology_compiler.compile(
            mission=m, admission=adm, tasks=(task(),), routes=route(), attestations=(worker(),),
            epochs={"CAP_A": epoch()}, now=NOW,
        )
        aa = self.spine.action_gate.admit(mission=m, topology=topo, request=request(), now=NOW)
        att = replace(attempt(), action_admission_digest=aa.receipt_digest)
        bundle = ActionExecutionBundle(request=request(), grant=None, attempt=att, readback=readback())
        r = self.spine.run(**self.base_kwargs(m, bundles=(bundle,)))
        self.assertEqual(SpineStage.VALUE_OBSERVED, r.final_snapshot.stage)
        self.assertTrue(r.final_snapshot.terminal_value)
        self.assertTrue(self.spine.verify_chain(r.snapshots))
        self.assertEqual(
            [SpineStage.INIT, SpineStage.CAPABILITY_ADMITTED, SpineStage.TOPOLOGY_READY,
             SpineStage.ACTIONS_ADMITTED, SpineStage.EXECUTION_CLOSED, SpineStage.VALUE_OBSERVED],
            [x.stage for x in r.snapshots],
        )

    def test_tampered_snapshot_chain_is_rejected(self) -> None:
        m = mission()
        adm = self.spine.capability_compiler.admit(m, self.req, truth())
        topo = self.spine.topology_compiler.compile(
            mission=m, admission=adm, tasks=(task(),), routes=route(), attestations=(worker(),),
            epochs={"CAP_A": epoch()}, now=NOW,
        )
        aa = self.spine.action_gate.admit(mission=m, topology=topo, request=request(), now=NOW)
        att = replace(attempt(), action_admission_digest=aa.receipt_digest)
        bundle = ActionExecutionBundle(request=request(), grant=None, attempt=att, readback=readback())
        r = self.spine.run(**self.base_kwargs(m, bundles=(bundle,)))
        tampered = list(r.snapshots)
        tampered[2] = replace(tampered[2], predecessor_digest="sha256:forged")
        self.assertFalse(self.spine.verify_chain(tampered))


if __name__ == "__main__":
    unittest.main()
