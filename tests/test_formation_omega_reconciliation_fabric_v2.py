from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from formation_omega.autonomic_fabric import (
    AuthorityCeiling,
    FailureForecast,
    MissionStateVector,
)
from formation_omega.convergence_supervisor import ProviderSnapshot
from formation_omega.mission_convergence import ConvergenceLedger
from formation_omega.reconciliation_fabric_v2 import (
    AdaptiveTopologyCompiler,
    AttestationEnvelope,
    DesiredMissionState,
    DurableReplayKernel,
    EvaluationProfile,
    EvolutionCandidate,
    EvolutionaryChallengerLab,
    ObservedMissionState,
    OperationCandidate,
    PolicyEffect,
    PolicyInput,
    PolicyKernel,
    ProofDirectedWavePlanner,
    ReconciliationFabricV2,
    StateReconciler,
    TaskGraphProfile,
    TopologyMode,
    TraceContext,
)
from formation_omega.source_convergence import ChangeCapsule


class ReconciliationFabricV2Tests(unittest.TestCase):
    def desired(self):
        return DesiredMissionState.create(
            mission_id="mission-v2",
            objective="Converge source safely to signed current main",
            desired_state="ADMITTED",
            required_checks=("airlock", "bubbles", "leak_guard"),
            required_proof_axes=("source", "rollback"),
            required_capabilities=("github", "mce"),
            rollback_required=True,
        )

    def test_state_reconciler_computes_only_missing_delta(self):
        desired = self.desired()
        observed = ObservedMissionState(
            mission_id="mission-v2",
            observed_state="CANDIDATE",
            checks={"airlock": True, "bubbles": False, "leak_guard": True},
            proof_axes={"source": True, "rollback": False},
            capabilities={"github": True, "mce": False},
            rollback_available=False,
        )
        delta = StateReconciler.reconcile(desired, observed)
        self.assertFalse(delta.converged)
        dimensions = [item.dimension for item in delta.gaps]
        self.assertIn("mission_state", dimensions)
        self.assertIn("check", dimensions)
        self.assertIn("proof_axis", dimensions)
        self.assertIn("capability", dimensions)
        self.assertIn("rollback", dimensions)
        self.assertNotIn("airlock=PASS", [item.expected for item in delta.gaps])

    def test_converged_state_has_empty_delta(self):
        desired = self.desired()
        observed = ObservedMissionState(
            mission_id="mission-v2",
            observed_state="ADMITTED",
            checks={"airlock": True, "bubbles": True, "leak_guard": True},
            proof_axes={"source": True, "rollback": True},
            capabilities={"github": True, "mce": True},
            rollback_available=True,
        )
        delta = StateReconciler.reconcile(desired, observed)
        self.assertTrue(delta.converged)
        self.assertEqual((), delta.gaps)

    def test_adaptive_topology_prefers_deterministic_when_possible(self):
        profile = TaskGraphProfile(
            node_count=8,
            edge_count=5,
            ready_parallel_count=4,
            shared_state_key_count=1,
            deterministic_fraction=0.95,
            uncertainty=0.10,
            evidence_conflict=0.05,
        )
        decision = AdaptiveTopologyCompiler().compile(profile)
        self.assertEqual(TopologyMode.DETERMINISTIC, decision.mode)
        self.assertFalse(decision.require_falsifier)

    def test_adaptive_topology_adds_independent_challenge_under_uncertainty(self):
        profile = TaskGraphProfile(
            node_count=8,
            edge_count=8,
            ready_parallel_count=4,
            shared_state_key_count=2,
            deterministic_fraction=0.20,
            uncertainty=0.80,
            evidence_conflict=0.70,
            consequential_fraction=0.20,
        )
        decision = AdaptiveTopologyCompiler().compile(profile)
        self.assertEqual(TopologyMode.BUILDER_FALSIFIER_WITNESS, decision.mode)
        self.assertTrue(decision.require_falsifier)
        self.assertTrue(decision.require_witness)

    def test_wave_planner_rejects_regression_and_external_effect(self):
        before = MissionStateVector(0.2, 0.2, 0.8, 0.8, 0.2)
        good = OperationCandidate(
            action_id="good",
            objective="Increase proof without regression",
            closure_leverage=0.9,
            information_gain=0.8,
            success_probability=0.9,
            reversibility=1.0,
            cost=0.1,
            risk=0.1,
            latency=0.1,
            projected_state=MissionStateVector(0.3, 0.3, 0.8, 0.8, 0.3),
        )
        regressing = OperationCandidate(
            action_id="regress",
            objective="Gain closure while reducing safety",
            closure_leverage=1.0,
            information_gain=1.0,
            success_probability=1.0,
            reversibility=1.0,
            cost=0.0,
            risk=0.0,
            latency=0.0,
            projected_state=MissionStateVector(0.4, 0.4, 0.7, 0.8, 0.4),
        )
        effect = OperationCandidate(
            action_id="effect",
            objective="External effect should remain held",
            closure_leverage=1.0,
            information_gain=1.0,
            success_probability=1.0,
            reversibility=1.0,
            cost=0.0,
            risk=0.0,
            latency=0.0,
            projected_state=MissionStateVector(0.4, 0.4, 0.8, 0.8, 0.4),
            authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT,
            external_effect=True,
        )
        graph = TaskGraphProfile(3, 0, 3, 0, 0.8, 0.1, 0.1)
        wave = ProofDirectedWavePlanner().plan(
            mission_id="m",
            objective="test",
            graph=graph,
            before=before,
            operations=(good, regressing, effect),
        )
        self.assertIn("good", wave.selected_action_ids)
        self.assertIn("regress", wave.held_action_ids)
        self.assertIn("effect", wave.held_action_ids)

    def test_failure_horizon_preempts_high_priority_precursor(self):
        before = MissionStateVector(0.1, 0.1, 0.9, 0.9, 0.1)
        operation = OperationCandidate(
            action_id="safe",
            objective="safe",
            closure_leverage=0.8,
            information_gain=0.8,
            success_probability=0.9,
            reversibility=1.0,
            cost=0.1,
            risk=0.1,
            latency=0.1,
            projected_state=MissionStateVector(0.2, 0.2, 0.9, 0.9, 0.2),
        )
        forecast = FailureForecast(
            fingerprint="STALE_MAIN_RACE",
            precursor="main changed during checks",
            probability=0.9,
            impact=0.9,
            precursor_confidence=0.9,
            prevention_leverage=0.9,
            lead_time=0.1,
            preventive_action="refresh main",
            fallback_route="reclassify delta",
        )
        wave = ProofDirectedWavePlanner().plan(
            mission_id="m",
            objective="test",
            graph=TaskGraphProfile(2, 1, 2, 0, 0.5, 0.2, 0.2),
            before=before,
            operations=(operation,),
            forecasts=(forecast,),
        )
        self.assertIn("STALE_MAIN_RACE", wave.preempt_failure_fingerprints)

    def test_durable_replay_survives_restart_and_rejects_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mission.jsonl"
            ledger = ConvergenceLedger(path)
            kernel = DurableReplayKernel(ledger)
            first = kernel.commit(
                mission_id="m",
                step_key="build",
                input_payload={"sha": "abc"},
                result_ref="artifact:1",
                result_digest_source={"digest": "one"},
            )
            self.assertFalse(first.replayed)
            ledger2 = ConvergenceLedger(path)
            kernel2 = DurableReplayKernel(ledger2)
            replay = kernel2.resume(mission_id="m", step_key="build", input_payload={"sha": "abc"})
            self.assertIsNotNone(replay)
            self.assertTrue(replay.replayed)
            with self.assertRaisesRegex(RuntimeError, "REPLAY_STEP_INPUT_CONFLICT"):
                kernel2.resume(mission_id="m", step_key="build", input_payload={"sha": "different"})

    def test_policy_kernel_denies_effect_at_internal_authority(self):
        decision = PolicyKernel.evaluate(
            PolicyInput(
                action="TRADE",
                authority_ceiling=AuthorityCeiling.A1_INTERNAL,
                external_effect=True,
                semantic_conflict=False,
                required_checks_passed=True,
                rollback_available=True,
                exact_snapshot_bound=True,
                owner_authorized=True,
            )
        )
        self.assertEqual(PolicyEffect.DENY, decision.effect)
        self.assertIn("A1_INTERNAL_NO_EXTERNAL_EFFECT", decision.reason_codes)

    def test_policy_kernel_denies_semantic_conflict(self):
        decision = PolicyKernel.evaluate(
            PolicyInput(
                action="MERGE",
                authority_ceiling=AuthorityCeiling.A1_INTERNAL,
                external_effect=False,
                semantic_conflict=True,
                required_checks_passed=True,
                rollback_available=True,
                exact_snapshot_bound=True,
            )
        )
        self.assertEqual(PolicyEffect.DENY, decision.effect)

    def test_trace_context_round_trip_and_child_preserves_trace(self):
        root = TraceContext.create("mission:one")
        parsed = TraceContext.parse(root.traceparent)
        self.assertEqual(root, parsed)
        child = root.child("airlock")
        self.assertEqual(root.trace_id, child.trace_id)
        self.assertNotEqual(root.span_id, child.span_id)

    def test_evolutionary_lab_promotes_proven_challenger_only(self):
        profile = EvaluationProfile(
            profile_id="cfbe-v2",
            weights={"closure": 3.0, "safety": 3.0, "owner_burden": 2.0, "replay": 2.0},
            minimums={"safety": 0.80, "replay": 0.70},
        )
        incumbent = EvolutionCandidate(
            candidate_id="v1",
            parent_ids=(),
            metrics={"closure": 0.70, "safety": 0.90, "owner_burden": 0.60, "replay": 0.70},
            artifact_ref="commit:v1",
        )
        challenger = EvolutionCandidate(
            candidate_id="v2",
            parent_ids=("v1",),
            metrics={"closure": 0.90, "safety": 0.95, "owner_burden": 0.85, "replay": 0.95},
            artifact_ref="commit:v2",
            evidence_refs=("ci:green",),
        )
        unsafe = EvolutionCandidate(
            candidate_id="fast-unsafe",
            parent_ids=("v1",),
            metrics={"closure": 1.0, "safety": 0.50, "owner_burden": 1.0, "replay": 1.0},
            artifact_ref="commit:unsafe",
        )
        result = EvolutionaryChallengerLab().tournament(
            incumbent=incumbent,
            challengers=(challenger, unsafe),
            profile=profile,
        )
        self.assertTrue(result.promoted)
        self.assertEqual("v2", result.champion_id)
        unsafe_eval = next(item for item in result.evaluations if item.candidate_id == "fast-unsafe")
        self.assertIn("safety", unsafe_eval.fatal_regressions)

    def test_attestation_is_in_toto_shaped_and_requires_signing(self):
        envelope = AttestationEnvelope.create(
            subjects={"artifact.tar": "a" * 64},
            predicate_type="https://slsa.dev/provenance/v1",
            predicate={"buildType": "formation-omega-v2"},
            builder_id="federation-omega",
        )
        self.assertEqual("https://in-toto.io/Statement/v1", envelope.statement["_type"])
        self.assertTrue(envelope.signing_required)
        self.assertEqual(64, len(envelope.statement_sha256))

    def test_full_fabric_composes_supervisor_without_inheriting_effect_authority(self):
        desired = DesiredMissionState.create(
            mission_id="m-source",
            objective="Admit exact source candidate safely",
            desired_state="ADMITTED",
            required_checks=("airlock",),
            rollback_required=False,
        )
        observed = ObservedMissionState(
            mission_id="m-source",
            observed_state="CANDIDATE",
            checks={"airlock": False},
            rollback_available=False,
        )
        capsule = ChangeCapsule.create(
            change_id="change-1",
            mission_id="m-source",
            base_sha="base",
            candidate_head_sha="head",
            candidate_blobs={"a.py": "candidate"},
            base_blobs={"a.py": "baseblob"},
            semantic_domains=("source",),
            required_checks=("airlock",),
            proof_boundary="SOURCE_ONLY",
            rollback_ref="base",
        )
        snapshot = ProviderSnapshot.create(
            main_sha="base",
            candidate_head_sha="head",
            current_blobs={"a.py": "baseblob"},
            check_results={"airlock": False},
            evidence_refs=("github:readback",),
        )
        plan = ReconciliationFabricV2().plan(
            desired=desired,
            observed=observed,
            graph=TaskGraphProfile(2, 1, 1, 1, 0.8, 0.2, 0.1),
            before=MissionStateVector(0.1, 0.1, 0.9, 0.9, 0.1),
            capsule=capsule,
            provider_snapshot=snapshot,
        )
        self.assertIsNotNone(plan.source_decision)
        self.assertFalse(plan.source_decision.source_mutation_ready)
        self.assertEqual(PolicyEffect.HOLD, plan.policy.effect)
        self.assertIn("REQUIRED_CHECKS_INCOMPLETE", plan.policy.reason_codes)


if __name__ == "__main__":
    unittest.main()
