from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from federation.aarek_v1 import MissionSnapshot
from federation.oh50_producer_adapter_v1 import OH50ProducerAdapter
from federation.of50_ace_v1 import (
    Authority,
    ExecutionProof,
    FormationDecision,
    OF50CycleRequest,
    ProofTier,
    ReuseBuildDecision,
    RouteCandidate,
)
from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector
from federation.runtime_convergence_binding_v2 import (
    RuntimeConvergenceBinderV2,
    StageState,
)


ROOT = Path(__file__).resolve().parents[1]
PROOFOS_POLICY = ROOT / "governance/proofos_omega_policy_v1.json"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40


def selected_for(path: str) -> tuple[set[str], set[str]]:
    policy = ProofPolicy.from_path(PROOFOS_POLICY)
    impact = ImpactCompiler(policy).assess([path])
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        impact=impact,
    )
    return set(impact.impacted_subsystems), {item.test_id for item in manifest.selected_tests}


MISSION = "M-FRCB-V2-001"
OBJECTIVE = "bind actual OH50 producer invocation into convergence truth"


def formation() -> FormationDecision:
    return FormationDecision(
        mission_id=MISSION,
        foundry_cycle_ref="foundry:structural:v2",
        route_candidates=(
            RouteCandidate("R1", "REUSE", 0.9, "falsify-r1", "reuse existing"),
            RouteCandidate("R2", "REPAIR", 0.7, "falsify-r2", "repair existing"),
        ),
        selected_route_id="R1",
        reuse_vs_build=ReuseBuildDecision.REUSE,
        selected_capability_hypothesis="reuse existing",
        implementation_required=False,
    )


def snapshot() -> MissionSnapshot:
    return MissionSnapshot(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
    )


def request(manifest, **overrides) -> OF50CycleRequest:
    base = dict(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY",
        owner_protection_violations=(),
        aarek_receipt_ref="",
        swarm_manifest=manifest,
        formation_decision=formation(),
        alpha_omega_packet=None,
        execution_proof=ExecutionProof(executed=False, proof_tier=ProofTier.SOURCE),
        required_outcomes=("O1",),
        proven_outcomes=(),
        completion_requested=False,
    )
    base.update(overrides)
    return OF50CycleRequest(**base)


class OH50ProducerAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.producer = OH50ProducerAdapter()

    def test_producer_emits_exact_50_cell_manifest_and_verifiable_receipt(self):
        result = self.producer.produce(mission_id=MISSION, objective=OBJECTIVE)
        self.assertEqual(50, len(result.manifest.horizons))
        self.assertEqual(50, result.receipt.horizon_count)
        self.assertEqual((), result.manifest.validate())
        self.assertTrue(result.receipt.verify())
        self.assertTrue(result.receipt.truth_boundary["producer_invocation_verified"])
        self.assertFalse(result.receipt.truth_boundary["producer_independent_attestation_verified"])
        self.assertFalse(result.receipt.truth_boundary["provider_execution_verified"])

    def test_producer_is_deterministic_for_same_inputs(self):
        left = self.producer.produce(mission_id=MISSION, objective=OBJECTIVE)
        right = self.producer.produce(mission_id=MISSION, objective=OBJECTIVE)
        self.assertEqual(left.receipt.receipt_digest, right.receipt.receipt_digest)
        self.assertEqual(left.receipt.manifest_digest, right.receipt.manifest_digest)

    def test_producer_rejects_authority_widening(self):
        with self.assertRaisesRegex(ValueError, "OH50_PRODUCER_REQUIRES_A1_INTERNAL"):
            self.producer.produce(
                mission_id=MISSION,
                objective=OBJECTIVE,
                authority_ceiling=Authority.A2_OWNER_RESERVED.value,
            )

    def test_receipt_tamper_is_detected(self):
        result = self.producer.produce(mission_id=MISSION, objective=OBJECTIVE)
        tampered = replace(
            result.receipt,
            manifest_digest="sha256:" + ("0" * 64),
        )
        self.assertFalse(tampered.verify())


class RuntimeConvergenceBindingV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.produced = OH50ProducerAdapter().produce(
            mission_id=MISSION,
            objective=OBJECTIVE,
            required_capabilities=("proof", "route"),
        )
        self.binder = RuntimeConvergenceBinderV2()

    def test_v2_promotes_only_oh50_to_producer_invocation_verified(self):
        result = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.produced.manifest),
            oh50_producer_receipt=self.produced.receipt,
        )
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(StageState.PRODUCER_INVOCATION_VERIFIED, stages["AAREK"].state)
        self.assertEqual(StageState.PRODUCER_INVOCATION_VERIFIED, stages["OH50"].state)
        self.assertEqual(StageState.STRUCTURALLY_BOUND, stages["FORMATION_INNOVATION"].state)
        self.assertEqual(StageState.NOT_REQUIRED, stages["ALPHA_OMEGA_IF_REQUIRED"].state)
        self.assertTrue(result.convergence_receipt.truth_boundary["oh50_producer_invocation_verified"])
        self.assertFalse(result.convergence_receipt.truth_boundary["oh50_independent_attestation_verified"])
        self.assertFalse(result.convergence_receipt.provider_execution_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)
        self.assertTrue(result.convergence_receipt.verify())

    def test_manifest_substitution_is_rejected(self):
        first = self.produced.manifest.horizons[0]
        substituted = replace(
            self.produced.manifest,
            horizons=(
                replace(first, evidence_ref="sha256:" + ("0" * 64)),
                *self.produced.manifest.horizons[1:],
            ),
        )
        with self.assertRaisesRegex(ValueError, "OH50_RECEIPT_MANIFEST_MISMATCH"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(substituted),
                oh50_producer_receipt=self.produced.receipt,
            )

    def test_receipt_mission_substitution_is_rejected(self):
        forged = replace(self.produced.receipt, mission_id="OTHER")
        with self.assertRaisesRegex(ValueError, "OH50_PRODUCER_RECEIPT_INVALID"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(self.produced.manifest),
                oh50_producer_receipt=forged,
            )

    def test_host_algorithm_must_match_receipt(self):
        bad_manifest = replace(
            self.produced.manifest,
            host_algorithm_id="OTHER-PRODUCER",
        )
        with self.assertRaisesRegex(ValueError, "OH50_RECEIPT_HOST_ALGORITHM_MISMATCH"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(bad_manifest),
                oh50_producer_receipt=self.produced.receipt,
            )

    def test_v2_receipt_is_deterministic(self):
        left = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.produced.manifest),
            oh50_producer_receipt=self.produced.receipt,
        )
        right = self.binder.evaluate(
            aarek_snapshot=snapshot(),
            of50_request=request(self.produced.manifest),
            oh50_producer_receipt=self.produced.receipt,
        )
        self.assertEqual(
            left.convergence_receipt.receipt_digest,
            right.convergence_receipt.receipt_digest,
        )


class RuntimeConvergenceBindingV2ProofOSTests(unittest.TestCase):
    def test_v1_change_impacts_v2(self):
        impacted, selected = selected_for("federation/runtime_convergence_binding_v1.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V2", impacted)
        self.assertIn("runtime_convergence_binding_v2", selected)

    def test_ao_harmonic_change_impacts_v2(self):
        impacted, selected = selected_for("ao_harmonic_v3/horizon.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V2", impacted)
        self.assertIn("runtime_convergence_binding_v2", selected)

    def test_of50_change_impacts_v2(self):
        impacted, selected = selected_for("federation/of50_ace_v1.py")
        self.assertIn("FUSE_RUNTIME_CONVERGENCE_BINDING_V2", impacted)
        self.assertIn("runtime_convergence_binding_v2", selected)


if __name__ == "__main__":
    unittest.main()
