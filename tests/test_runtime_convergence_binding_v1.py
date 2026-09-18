from __future__ import annotations

from dataclasses import replace
import unittest

from federation.aarek_v1 import Evidence as AarekEvidence, EvidenceKind as AarekEvidenceKind, MissionSnapshot
from federation.of50_ace_v1 import (
    Authority,
    ExecutionProof,
    FormationDecision,
    HorizonCell,
    HORIZON_IDS,
    OF50CycleRequest,
    ProofTier,
    ReuseBuildDecision,
    RouteCandidate,
    SwarmManifest,
)
from federation.runtime_convergence_binding_v1 import BindingState, RuntimeConvergenceBinder

MISSION = "M-FRCB-001"
OBJECTIVE = "prove runtime convergence binding"


def swarm(mission_id: str = MISSION, objective: str = OBJECTIVE) -> SwarmManifest:
    return SwarmManifest(
        mission_id=mission_id,
        host_algorithm_id="OH50-TEST-PRODUCER",
        objective=objective,
        authority_ceiling=Authority.A1_INTERNAL.value,
        horizons=tuple(HorizonCell(item, "ASSESSED", f"proof:{item}") for item in HORIZON_IDS),
        semantic_readback_contract="action-specific readback required",
    )


def formation(*, implementation_required: bool = False) -> FormationDecision:
    return FormationDecision(
        mission_id=MISSION,
        foundry_cycle_ref="foundry:cycle:1",
        route_candidates=(
            RouteCandidate("R1", "REUSE", 0.9, "falsify-r1", "reuse existing"),
            RouteCandidate("R2", "REPAIR", 0.7, "falsify-r2", "repair existing"),
        ),
        selected_route_id="R1",
        reuse_vs_build=ReuseBuildDecision.REUSE,
        selected_capability_hypothesis="reuse existing",
        implementation_required=implementation_required,
    )


def request(**overrides) -> OF50CycleRequest:
    base = dict(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY",
        owner_protection_violations=(),
        aarek_receipt_ref="",
        swarm_manifest=swarm(),
        formation_decision=formation(),
        alpha_omega_packet=None,
        execution_proof=ExecutionProof(executed=False, proof_tier=ProofTier.SOURCE),
        required_outcomes=("O1",),
        proven_outcomes=(),
        completion_requested=False,
    )
    base.update(overrides)
    return OF50CycleRequest(**base)


def completion_request(**overrides) -> OF50CycleRequest:
    base = dict(
        execution_proof=ExecutionProof(
            executed=True,
            proof_tier=ProofTier.LOCAL_RUNTIME,
            execution_ref="exec:1",
            semantic_readback_ref="semantic:1",
        ),
        objective_satisfied=True,
        proven_outcomes=("O1",),
        oh50_rescan_ref="rescan:1",
        mission_recompiled=True,
        completion_requested=True,
    )
    base.update(overrides)
    return request(**base)


def snapshot(**overrides) -> MissionSnapshot:
    base = dict(
        mission_id=MISSION,
        objective=OBJECTIVE,
        authority_ceiling=Authority.A1_INTERNAL.value,
    )
    base.update(overrides)
    return MissionSnapshot(**base)


def complete_aarek_snapshot(**overrides) -> MissionSnapshot:
    base = dict(
        evidence=(
            AarekEvidence(AarekEvidenceKind.BINDING, "binding:1", action_specific=True),
            AarekEvidence(AarekEvidenceKind.EXECUTION, "execution:1", action_specific=True),
            AarekEvidence(AarekEvidenceKind.SEMANTIC_READBACK, "readback:1", action_specific=True),
        ),
        mission_recompiled=True,
    )
    base.update(overrides)
    return snapshot(**base)


class RuntimeConvergenceBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binder = RuntimeConvergenceBinder()

    def test_real_aarek_execution_is_bound_into_of50(self):
        result = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        self.assertEqual(result.aarek_receipt.receipt_digest, result.bound_request.aarek_receipt_ref)
        self.assertTrue(result.aarek_receipt.receipt_digest.startswith("sha256:"))
        self.assertFalse(result.convergence_receipt.completion_verified)
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertTrue(result.convergence_receipt.truth_boundary["aarek_execution_verified"])
        self.assertTrue(result.convergence_receipt.verify())

    def test_caller_cannot_substitute_aarek_reference(self):
        with self.assertRaisesRegex(ValueError, "AAREK_RECEIPT_REF_SUBSTITUTION"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(aarek_receipt_ref="sha256:" + ("0" * 64)),
            )

    def test_mission_identity_must_match(self):
        with self.assertRaisesRegex(ValueError, "MISSION_MISMATCH"):
            self.binder.evaluate(aarek_snapshot=snapshot(mission_id="OTHER"), of50_request=request())

    def test_objective_identity_must_match(self):
        with self.assertRaisesRegex(ValueError, "OBJECTIVE_MISMATCH"):
            self.binder.evaluate(aarek_snapshot=snapshot(objective="different"), of50_request=request())

    def test_oh50_mission_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "OH50_MISSION_MISMATCH"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(swarm_manifest=swarm(mission_id="OTHER")),
            )

    def test_formation_mission_mismatch_is_rejected(self):
        bad = replace(formation(), mission_id="OTHER")
        with self.assertRaisesRegex(ValueError, "FORMATION_MISSION_MISMATCH"):
            self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request(formation_decision=bad))

    def test_build_required_without_alpha_omega_packet_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ALPHA_OMEGA_PACKET_REQUIRED"):
            self.binder.evaluate(
                aarek_snapshot=snapshot(),
                of50_request=request(formation_decision=formation(implementation_required=True)),
            )

    def test_stage_states_preserve_truth_boundary(self):
        result = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        stages = {item.stage: item for item in result.convergence_receipt.stages}
        self.assertEqual(BindingState.EXECUTION_RECEIPT_VERIFIED, stages["AAREK"].state)
        self.assertEqual(BindingState.STRUCTURALLY_BOUND, stages["OH50"].state)
        self.assertEqual(BindingState.STRUCTURALLY_BOUND, stages["FORMATION_INNOVATION"].state)
        self.assertEqual(BindingState.NOT_REQUIRED, stages["ALPHA_OMEGA_IF_REQUIRED"].state)

    def test_completion_request_requires_aarek_complete_verified(self):
        with self.assertRaisesRegex(ValueError, "AAREK_COMPLETION_NOT_VERIFIED"):
            self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=completion_request())

    def test_of50_completion_cannot_be_promoted_to_frcb_terminal_completion(self):
        result = self.binder.evaluate(
            aarek_snapshot=complete_aarek_snapshot(),
            of50_request=completion_request(),
        )
        self.assertTrue(result.of50_receipt.completion_verified)
        self.assertTrue(result.convergence_receipt.of50_completion_verified)
        self.assertTrue(result.convergence_receipt.truth_boundary["aarek_completion_verified"])
        self.assertFalse(result.convergence_receipt.f130_terminal_completion_verified)
        self.assertFalse(result.convergence_receipt.provider_execution_verified)
        self.assertFalse(result.convergence_receipt.completion_verified)

    def test_receipt_self_verification_rejects_tamper(self):
        result = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        self.assertTrue(result.convergence_receipt.verify())
        tampered = replace(
            result.convergence_receipt,
            of50_receipt_digest="sha256:" + ("0" * 64),
        )
        self.assertFalse(tampered.verify())

    def test_truth_boundary_is_immutable(self):
        result = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        with self.assertRaises(TypeError):
            result.convergence_receipt.truth_boundary["aarek_execution_verified"] = False  # type: ignore[index]

    def test_convergence_receipt_is_deterministic_for_same_inputs(self):
        left = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        right = self.binder.evaluate(aarek_snapshot=snapshot(), of50_request=request())
        self.assertEqual(left.convergence_receipt.receipt_digest, right.convergence_receipt.receipt_digest)


if __name__ == "__main__":
    unittest.main()
