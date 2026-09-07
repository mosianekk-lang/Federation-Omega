from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALPHA_SRC = ROOT / "systems" / "alpha-omega-turnkey" / "src"
if str(ALPHA_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHA_SRC))

from federation.of50_ace_v1 import (
    ActionCandidate, ActionFamilyRecord, Authority, CycleDecision, EvidenceKind,
    ExecutionProof, ExecutorProof, ExecutorState, FailureTransition, FormationDecision,
    HORIZON_IDS, HorizonCell, MissionGenome, OF50ACEKernel, OF50CycleRequest,
    PredicateEvidence, ProgressObservation, ProofTier, RegressionCode,
    ReuseBuildDecision, RouteCandidate, SwarmManifest, advance_terminal_predicates,
    held_zero_delta_families, strategic_gemini_terminal_ledger,
)
from evidenceops.innovation_engine.of50_adapter import compile_of50_formation_decision
from alpha_omega import AlphaOmegaEngine
from alpha_omega.of50_adapter import compile_of50_alpha_omega_packet


def manifest() -> SwarmManifest:
    return SwarmManifest(
        mission_id="M1", host_algorithm_id="ALG-1", objective="complete mission",
        authority_ceiling=Authority.A1_INTERNAL.value,
        horizons=tuple(HorizonCell(item, "ASSESSED", f"proof:{item}") for item in HORIZON_IDS),
        specialist_roles=("Mission Compiler", "Proof Auditor", "Toolsmith"),
        semantic_readback_contract="action-specific readback required",
    )


def formation(*, implementation_required: bool = False) -> FormationDecision:
    return FormationDecision(
        mission_id="M1", foundry_cycle_ref="FC-1",
        route_candidates=(
            RouteCandidate("R1", "APPS_SCRIPT", 0.8, "no callable identity", "reuse owner OAuth"),
            RouteCandidate("R2", "CLOUD_RUN", 0.7, "no semantic readback", "reuse private runtime"),
        ),
        selected_route_id="R1",
        reuse_vs_build=ReuseBuildDecision.REPAIR if implementation_required else ReuseBuildDecision.REUSE,
        selected_capability_hypothesis="repaired route can complete",
        implementation_required=implementation_required,
    )


def request(**overrides):
    base = dict(
        mission_id="M1", objective="complete mission", authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY", owner_protection_violations=(),
        aarek_receipt_ref="AAREK-1", swarm_manifest=manifest(), formation_decision=formation(),
        alpha_omega_packet=None,
        execution_proof=ExecutionProof(True, ProofTier.LOCAL_RUNTIME, "exec:1", "readback:1"),
        failure_transition=FailureTransition(), machine_resolvable_owner_tasks=(), genuine_owner_decisions=(),
        provider_runtime_required=False, objective_satisfied=False, required_outcomes=("O1",), proven_outcomes=(),
        reusable_verified_win=False, mission_genome=None, oh50_rescan_ref="rescan:1",
        mission_recompiled=True, completion_requested=False,
    )
    base.update(overrides)
    return OF50CycleRequest(**base)


class OF50RegressionTests(unittest.TestCase):
    def setUp(self):
        self.kernel = OF50ACEKernel()

    def test_silent_oh50_bypass_fails(self):
        self.assertIn("OH50_BYPASS", self.kernel.evaluate(request(swarm_manifest=None)).violations)

    def test_silent_formation_bypass_fails(self):
        self.assertIn("FORMATION_BYPASS", self.kernel.evaluate(request(formation_decision=None)).violations)

    def test_alpha_omega_bypass_fails_when_build_required(self):
        receipt = self.kernel.evaluate(request(formation_decision=formation(implementation_required=True)))
        self.assertIn("ALPHA_OMEGA_BYPASS_WHEN_IMPLEMENTATION_REQUIRED", receipt.violations)
        self.assertEqual(CycleDecision.BUILD_REQUIRED, receipt.decision)

    def test_oh50_cannot_become_parallel_foundry(self):
        receipt = self.kernel.evaluate(request(swarm_manifest=replace(manifest(), foundry_authority=True)))
        self.assertIn("OH50_PARALLEL_FOUNDRY_OR_BUILD_AUTHORITY_FORBIDDEN", receipt.violations)

    def test_source_or_ci_cannot_be_provider_runtime_proof(self):
        proof = ExecutionProof(True, ProofTier.CI, "ci:1", "", "", "")
        receipt = self.kernel.evaluate(request(provider_runtime_required=True, execution_proof=proof))
        self.assertIn("SOURCE_OR_CI_PROMOTED_AS_PROVIDER_RUNTIME_PROOF", receipt.violations)
        self.assertIn("PROVIDER_ACK_OR_RECEIPT_MISSING", receipt.violations)

    def test_unchanged_failed_route_replay_fails(self):
        receipt = self.kernel.evaluate(request(
            failure_transition=FailureTransition("FP-1", "FP-1", False, False, "FW-1")
        ))
        self.assertIn("UNCHANGED_FAILED_ROUTE_REPLAY", receipt.violations)
        self.assertEqual(CycleDecision.CHANGED_ROUTE_REQUIRED, receipt.decision)

    def test_machine_resolvable_owner_offload_fails(self):
        self.assertIn(
            "MACHINE_RESOLVABLE_OWNER_OFFLOAD",
            self.kernel.evaluate(request(machine_resolvable_owner_tasks=("repair queue",))).violations,
        )

    def test_premature_completion_fails(self):
        receipt = self.kernel.evaluate(request(completion_requested=True, objective_satisfied=False))
        self.assertIn("PREMATURE_COMPLETION", receipt.violations)
        self.assertFalse(receipt.completion_verified)

    def test_reusable_win_requires_mission_genome(self):
        self.assertIn(
            "MISSION_GENOME_MISSING_AFTER_REUSABLE_WIN",
            self.kernel.evaluate(request(reusable_verified_win=True)).violations,
        )

    def test_authority_widening_fails(self):
        receipt = self.kernel.evaluate(request(
            formation_decision=replace(formation(), authority_ceiling=Authority.A2_OWNER_RESERVED.value)
        ))
        self.assertIn("FORMATION_AUTHORITY_WIDENING", receipt.violations)

    def test_complete_verified_requires_full_chain_and_genome(self):
        genome = MissionGenome(
            genome_id="G1", objective_pattern="complete mission", dependency_graph_ref="D1",
            winning_route="R1", required_capabilities=("C1",), authority_ceiling=Authority.A1_INTERNAL.value,
            proof_gates=("semantic",), rollback_ref="RB1", runtime_identity="runtime:1",
            failure_fingerprints=("FP0",), value_delta={"owner_minutes": -10},
            reusable_conditions=("same objective",),
        )
        proof = ExecutionProof(
            True, ProofTier.SEMANTIC_READBACK, "exec:1", "semantic:1", "ack:1", "receipt:1"
        )
        receipt = self.kernel.evaluate(request(
            provider_runtime_required=True, execution_proof=proof, objective_satisfied=True,
            proven_outcomes=("O1",), reusable_verified_win=True, mission_genome=genome,
            completion_requested=True,
        ))
        self.assertEqual((), receipt.violations)
        self.assertEqual(CycleDecision.COMPLETE_VERIFIED, receipt.decision)
        self.assertTrue(receipt.completion_verified)

    def test_formation_adapter_preserves_no_effect_boundary(self):
        decision = compile_of50_formation_decision(
            mission_id="M1",
            foundry_result={"cycle_id": "FC-9", "authority_ceiling": "A1_INTERNAL", "external_effect": False},
            route_candidates=[
                {"route_id": "R1", "route_family": "A", "score": 0.9, "falsifier": "F1", "capability_hypothesis": "H1"},
                {"route_id": "R2", "route_family": "B", "score": 0.8, "falsifier": "F2", "capability_hypothesis": "H2"},
            ],
            selected_route_id="R1", reuse_vs_build="REUSE",
            selected_capability_hypothesis="H1", implementation_required=False,
        )
        self.assertFalse(decision.external_effect)
        self.assertEqual("FC-9", decision.foundry_cycle_ref)

    def test_alpha_omega_adapter_emits_full_lifecycle_without_provider_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = compile_of50_alpha_omega_packet(
                AlphaOmegaEngine(tmp), mission_id="M1", objective="repair provider bridge",
                formation_decision=formation(implementation_required=True), rollback_ref="RB-1",
                runtime_target="private-google-runtime",
                terminal_criteria=("semantic response", "provider receipt"),
            )
        self.assertIsNotNone(result)
        self.assertEqual(10, len(result.packet.lifecycle))
        self.assertFalse(result.plan.truth_boundary["provider_deployed"])
        self.assertFalse(result.plan.truth_boundary["provider_readback"])


class OF50TerminalPredicateV11Tests(unittest.TestCase):
    def setUp(self):
        self.kernel = OF50ACEKernel()
        self.ledger = strategic_gemini_terminal_ledger("M1")

    def test_control_plane_evidence_does_not_advance_provider_predicates(self):
        evidence = tuple(
            PredicateEvidence("GEM-TP-02", kind, f"proof:{kind.value}", provider_native=False)
            for kind in (
                EvidenceKind.QUEUE, EvidenceKind.SCHEDULE, EvidenceKind.SOURCE,
                EvidenceKind.CI, EvidenceKind.HEARTBEAT, EvidenceKind.CONTROL_METADATA,
            )
        )
        updated = advance_terminal_predicates(self.ledger, evidence=evidence)
        self.assertFalse(updated.state()["GEM-TP-02"])
        self.assertFalse(updated.state()["GEM-TP-03"])
        self.assertFalse(updated.state()["GEM-TP-04"])
        self.assertFalse(updated.state()["GEM-TP-05"])
        self.assertFalse(updated.state()["GEM-TP-06"])

    def test_executor_callable_requires_no_effect_execution_and_readback(self):
        incomplete = ExecutorProof(
            True, True, "identity:1", "exec:1", "",
            authority_ceiling=Authority.A1_INTERNAL.value,
        )
        updated = advance_terminal_predicates(self.ledger, executor_proof=incomplete)
        self.assertFalse(updated.state()["GEM-TP-01"])

        complete = replace(incomplete, action_specific_readback_ref="readback:1")
        updated = advance_terminal_predicates(self.ledger, executor_proof=complete)
        self.assertTrue(updated.state()["GEM-TP-01"])

    def test_only_provider_native_evidence_advances_provider_predicate(self):
        source = PredicateEvidence(
            "GEM-TP-02", EvidenceKind.SOURCE, "source:1", provider_native=False
        )
        invoked = PredicateEvidence(
            "GEM-TP-02", EvidenceKind.PROVIDER_INVOCATION, "provider:invoke:1",
            provider_native=True,
        )
        self.assertFalse(
            advance_terminal_predicates(self.ledger, evidence=(source,)).state()["GEM-TP-02"]
        )
        self.assertTrue(
            advance_terminal_predicates(self.ledger, evidence=(invoked,)).state()["GEM-TP-02"]
        )

    def test_substantive_response_requires_substantive_provider_evidence(self):
        shallow = PredicateEvidence(
            "GEM-TP-04", EvidenceKind.SUBSTANTIVE_RESPONSE, "provider:response:1",
            provider_native=True, substantive=False,
        )
        substantive = replace(shallow, proof_ref="provider:response:2", substantive=True)
        self.assertFalse(
            advance_terminal_predicates(self.ledger, evidence=(shallow,)).state()["GEM-TP-04"]
        )
        self.assertTrue(
            advance_terminal_predicates(self.ledger, evidence=(substantive,)).state()["GEM-TP-04"]
        )

    def test_control_metadata_cannot_unlock_progress_narration(self):
        action = ActionCandidate(
            "A1", "CONTROL_PLANE", 0.0, control_plane_only=True
        )
        receipt = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            executor_acquisition_active=True,
            selected_action=action,
            progress_observations=(ProgressObservation(control_plane_only=True),),
            narration_claimed=True,
        ))
        self.assertIn(RegressionCode.AVAILABLE_TOOL_BIAS.value, receipt.violations)
        self.assertIn(RegressionCode.CONTROL_PLANE_PROGRESS_SUBSTITUTION.value, receipt.violations)
        self.assertIn(RegressionCode.PROGRESS_PROOF_INTERLOCK_FAILURE.value, receipt.violations)
        self.assertIn(RegressionCode.NARRATION_WITHOUT_CAUSAL_PROGRESS.value, receipt.violations)
        self.assertFalse(receipt.narration_allowed)
        self.assertEqual(ExecutorState.EXECUTOR_ACQUISITION, receipt.executor_state)

    def test_zero_delta_action_family_is_circuit_broken(self):
        history = (
            ActionFamilyRecord("CONTROL_PLANE", False, True),
            ActionFamilyRecord("CONTROL_PLANE", False, True),
        )
        self.assertIn("CONTROL_PLANE", held_zero_delta_families(history))
        receipt = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            executor_acquisition_active=True,
            selected_action=ActionCandidate("A3", "CONTROL_PLANE", 0.0, control_plane_only=True),
            action_family_history=history,
        ))
        self.assertIn(RegressionCode.ZERO_DELTA_ACTION_FAMILY_REPLAY.value, receipt.violations)
        self.assertEqual(CycleDecision.CHANGED_ROUTE_REQUIRED, receipt.decision)

    def test_newly_callable_terminal_action_allows_progress(self):
        executor = ExecutorProof(
            True, True, "identity:1", "exec:no-effect:1", "readback:1"
        )
        receipt = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            executor_proof_v11=executor,
            progress_observations=(ProgressObservation(
                changed_predicate_ids=("GEM-TP-01",),
                terminal_action_became_callable=True,
                evidence_refs=("readback:1",),
            ),),
            narration_claimed=True,
        ))
        self.assertTrue(receipt.causal_progress)
        self.assertTrue(receipt.narration_allowed)
        self.assertTrue(receipt.terminal_predicate_state["GEM-TP-01"])
        self.assertNotIn(RegressionCode.PROGRESS_PROOF_INTERLOCK_FAILURE.value, receipt.violations)

    def test_material_route_changing_evidence_allows_progress(self):
        receipt = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            executor_acquisition_active=True,
            progress_observations=(ProgressObservation(
                material_route_change=True, evidence_refs=("provider:new-route:1",)
            ),),
            narration_claimed=True,
        ))
        self.assertTrue(receipt.causal_progress)
        self.assertTrue(receipt.narration_allowed)

    def test_completion_requires_all_terminal_predicates_true(self):
        proof = ExecutionProof(
            True, ProofTier.SEMANTIC_READBACK, "exec:1", "semantic:1", "ack:1", "receipt:1"
        )
        incomplete = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            provider_runtime_required=True,
            execution_proof=proof,
            objective_satisfied=True, proven_outcomes=("O1",),
            completion_requested=True,
        ))
        self.assertIn("TERMINAL_PREDICATES_INCOMPLETE", incomplete.violations)
        self.assertFalse(incomplete.completion_verified)

        states = {f"GEM-TP-0{i}": True for i in range(1, 7)}
        complete_ledger = strategic_gemini_terminal_ledger("M1", states=states)
        complete = self.kernel.evaluate(request(
            terminal_ledger=complete_ledger,
            provider_runtime_required=True,
            execution_proof=proof,
            objective_satisfied=True, proven_outcomes=("O1",),
            completion_requested=True,
        ))
        self.assertEqual(CycleDecision.COMPLETE_VERIFIED, complete.decision)
        self.assertTrue(complete.completion_verified)

    def test_executor_authority_cannot_expand(self):
        executor = ExecutorProof(
            True, True, "identity:1", "exec:1", "readback:1",
            authority_ceiling=Authority.A2_OWNER_RESERVED.value,
        )
        receipt = self.kernel.evaluate(request(
            terminal_ledger=self.ledger,
            executor_proof_v11=executor,
            executor_acquisition_active=True,
        ))
        self.assertIn("EXECUTOR_AUTHORITY_WIDENING", receipt.violations)
        self.assertFalse(receipt.terminal_predicate_state["GEM-TP-01"])


if __name__ == "__main__":
    unittest.main()
