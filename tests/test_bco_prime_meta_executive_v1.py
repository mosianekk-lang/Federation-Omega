from __future__ import annotations

import hashlib
import unittest

from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    MetaFaculty,
    PrimeMode,
    PrimeObservation,
    StrategyCandidate,
    compile_continuity_lanes,
    compile_prime_decision,
    prime_capability_manifest,
    prime_promotion_gate,
    rank_strategies,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    AutonomyLevel,
    MetaAction,
    MetaCognitiveState,
)
from bubbles.chat_governor_omega3.continuity import EffectClass, PathRole
from formation_omega.reconciliation_fabric_v2 import TaskGraphProfile, TopologyMode


def digest(text: str = "objective") -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strategy(
    strategy_id: str,
    *,
    domain: str,
    quality: float,
    evidence: float = 0.8,
    reliability: float = 0.8,
    reversibility: float = 0.9,
    information_gain: float = 0.7,
    diversity: float = 0.8,
    latency: float = 0.2,
    cost: float = 0.0,
    burden: float = 0.1,
    risk: float = 0.1,
    external: bool = False,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_id=strategy_id,
        failure_domain=domain,
        expected_quality=quality,
        evidence_strength=evidence,
        reliability=reliability,
        reversibility=reversibility,
        information_gain=information_gain,
        failure_domain_diversity=diversity,
        latency_cost=latency,
        monetary_cost=cost,
        owner_burden=burden,
        risk=risk,
        external_effect=external,
        proof_refs=(f"proof:{strategy_id}",),
    )


def observation(
    *,
    meta: MetaCognitiveState | None = None,
    graph: TaskGraphProfile | None = None,
    effect_class: str = "READ_ONLY",
    exact_authority: bool = True,
    provider_runtime_available: bool = True,
    owner_approval_required: bool = False,
    active_streams: int = 2,
    shared_write_pressure: float = 0.0,
    owner_burden: float = 0.1,
    architecture_overlap: float = 0.1,
    frontier_gap: float = 0.1,
) -> PrimeObservation:
    return PrimeObservation(
        mission_id="mission-prime-1",
        objective_sha256=digest(),
        graph=graph
        or TaskGraphProfile(
            node_count=6,
            edge_count=4,
            ready_parallel_count=4,
            shared_state_key_count=0,
            deterministic_fraction=0.50,
            uncertainty=0.20,
            evidence_conflict=0.10,
            consequential_fraction=0.0,
        ),
        meta_state=meta
        or MetaCognitiveState(
            confidence=0.80,
            evidence_coverage=0.90,
            contradiction_pressure=0.10,
            novelty=0.20,
            progress=0.60,
            plan_stability=0.80,
            context_freshness=0.90,
            resource_pressure=0.20,
            repeated_failure_count=0,
        ),
        effect_class=effect_class,
        reversible=True,
        exact_authority=exact_authority,
        provider_runtime_available=provider_runtime_available,
        owner_approval_required=owner_approval_required,
        active_streams=active_streams,
        shared_write_pressure=shared_write_pressure,
        owner_burden=owner_burden,
        architecture_overlap=architecture_overlap,
        frontier_gap=frontier_gap,
        evidence_refs=("evidence:current",),
    )


class BCOPrimeMetaExecutiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategies = (
            strategy("route-a", domain="github", quality=0.92, evidence=0.90, reliability=0.90),
            strategy("route-b", domain="google", quality=0.82, information_gain=0.90),
            strategy("route-c", domain="github", quality=0.76, latency=0.05),
        )

    def test_strategy_tournament_preserves_champion_challenger_and_diverse_fallback(self):
        result = rank_strategies(self.strategies)
        self.assertEqual("route-a", result.champion_strategy_id)
        self.assertIn("route-b", result.challenger_strategy_ids)
        self.assertEqual("route-b", result.fallback_strategy_id)
        self.assertIn("FAILURE_DOMAIN_DIVERSITY_PRESERVED", result.reason_codes)

    def test_duplicate_strategy_ids_fail_closed(self):
        duplicate = (self.strategies[0], self.strategies[0])
        with self.assertRaisesRegex(ValueError, "PRIME_DUPLICATE_STRATEGY_ID"):
            rank_strategies(duplicate)

    def test_parallel_safe_mission_compiles_shadow_prime_decision(self):
        decision = compile_prime_decision(observation(), self.strategies)
        self.assertEqual(PrimeMode.SHADOW_ONLY, decision.mode)
        self.assertEqual(MetaAction.CONTINUE, decision.meta_action)
        self.assertEqual(TopologyMode.PARALLEL_CELLS, decision.topology_mode)
        self.assertGreaterEqual(decision.max_parallel_lanes, 2)
        self.assertIn(MetaFaculty.STREAM_GOVERNOR, decision.active_faculties)
        self.assertIn("EXPAND_INDEPENDENT_SAFE_PARALLEL_LANES", decision.control_actions)
        self.assertFalse(decision.dispatch_authorized)
        self.assertFalse(decision.external_effect_authorized)

    def test_high_contradiction_activates_adversarial_scientific_challenge(self):
        meta = MetaCognitiveState(0.70, 0.90, 0.75, 0.30, 0.50, 0.70, 0.90, 0.30, 0)
        graph = TaskGraphProfile(8, 7, 4, 1, 0.40, 0.50, 0.70, 0.10)
        decision = compile_prime_decision(observation(meta=meta, graph=graph), self.strategies)
        self.assertEqual(MetaAction.CHALLENGE, decision.meta_action)
        self.assertEqual(TopologyMode.BUILDER_FALSIFIER_WITNESS, decision.topology_mode)
        self.assertIn(MetaFaculty.ADVERSARIAL_TWIN, decision.active_faculties)
        self.assertIn(MetaFaculty.OMEGA_SCIENTIST, decision.active_faculties)
        self.assertIn("RUN_ADVERSARIAL_STRATEGY_TOURNAMENT", decision.control_actions)
        self.assertGreaterEqual(decision.horizon_depth, 25)

    def test_repeated_failure_forces_rollback_and_failure_scientist(self):
        meta = MetaCognitiveState(0.70, 0.90, 0.20, 0.20, 0.20, 0.60, 0.90, 0.30, 3)
        decision = compile_prime_decision(observation(meta=meta), self.strategies)
        self.assertEqual(MetaAction.ROLLBACK, decision.meta_action)
        self.assertIn(MetaFaculty.FAILURE_SCIENTIST, decision.active_faculties)
        self.assertIn("RESTORE_LAST_VERIFIED_META_POLICY", decision.control_actions)

    def test_shared_write_and_resource_pressure_throttle_parallelism_and_context(self):
        meta = MetaCognitiveState(0.80, 0.90, 0.10, 0.20, 0.50, 0.80, 0.90, 0.90, 0)
        decision = compile_prime_decision(
            observation(meta=meta, shared_write_pressure=0.90, active_streams=7),
            self.strategies,
        )
        self.assertLessEqual(decision.max_parallel_lanes, 2)
        self.assertEqual(0.30, decision.context_budget.hot_ratio)
        self.assertIn("THROTTLE_STREAM_WIP_WITH_FAIRNESS", decision.control_actions)
        self.assertIn("SHARED_WRITE_PRESSURE_THROTTLES_PARALLELISM", decision.reason_codes)

    def test_consequential_without_authority_interrupts_owner_but_never_authorizes_dispatch(self):
        external = (
            strategy("effect-a", domain="google", quality=0.90, external=True),
            strategy("effect-b", domain="github", quality=0.80, external=True),
        )
        decision = compile_prime_decision(
            observation(effect_class="CONSEQUENTIAL", exact_authority=False),
            external,
        )
        self.assertEqual(AutonomyLevel.HOLD_OWNER_TRIGGER, decision.autonomy_level)
        self.assertTrue(decision.owner_interrupt_required)
        self.assertFalse(decision.dispatch_authorized)
        self.assertFalse(decision.external_effect_authorized)
        self.assertTrue(decision.serialize_external_effects)

    def test_provider_runtime_gap_is_exact_hold_not_global_failure(self):
        decision = compile_prime_decision(
            observation(effect_class="PRIVATE_REVERSIBLE", provider_runtime_available=False),
            self.strategies,
        )
        self.assertEqual(AutonomyLevel.HOLD_PROVIDER_RUNTIME, decision.autonomy_level)
        self.assertTrue(decision.provider_runtime_hold)
        self.assertFalse(decision.owner_interrupt_required)
        self.assertIn("PROVIDER_RUNTIME_AND_ACTION_SPECIFIC_READBACK", decision.proof_requirements)

    def test_continuity_lane_compiler_emits_primary_challenger_fallback_without_mutation(self):
        decision = compile_prime_decision(observation(), self.strategies)
        lanes = compile_continuity_lanes(
            decision=decision,
            command_id="command-1",
            strategies=self.strategies,
            checkpoint_ref="checkpoint-1",
        )
        self.assertGreaterEqual(len(lanes), 2)
        self.assertEqual(PathRole.PRIMARY, lanes[0].path_role)
        self.assertEqual("checkpoint-1", lanes[0].checkpoint_ref)
        self.assertTrue(any(lane.path_role == PathRole.FALLBACK for lane in lanes))
        self.assertTrue(all(lane.effect_class == EffectClass.NO_EFFECT for lane in lanes))

    def test_external_strategy_lane_is_high_consequence_and_serialized(self):
        strategies = (
            strategy("safe", domain="github", quality=0.95),
            strategy("effect", domain="google", quality=0.80, external=True),
        )
        decision = compile_prime_decision(observation(), strategies)
        lanes = compile_continuity_lanes(decision=decision, command_id="cmd", strategies=strategies)
        effect_lane = next(lane for lane in lanes if lane.path_id == "effect")
        self.assertEqual(EffectClass.HIGH_CONSEQUENCE, effect_lane.effect_class)
        self.assertEqual("external-effect-serialized", effect_lane.concurrency_group)

    def test_meta_receipt_is_deterministic(self):
        first = compile_prime_decision(observation(), self.strategies)
        second = compile_prime_decision(observation(), self.strategies)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(64, len(first.receipt_sha256))

    def test_promotion_requires_real_shadow_pairing_value_and_rollback(self):
        hold = prime_promotion_gate(
            baseline_quality=0.70,
            candidate_quality=0.80,
            paired_cases=29,
            hard_regressions=0,
            rollback_available=True,
            independent_verifier_pass=True,
            observed_owner_value_positive=True,
            hosted_shadow_pass=True,
        )
        self.assertEqual(PrimeMode.HOLD, hold.mode)
        promoted = prime_promotion_gate(
            baseline_quality=0.70,
            candidate_quality=0.80,
            paired_cases=30,
            hard_regressions=0,
            rollback_available=True,
            independent_verifier_pass=True,
            observed_owner_value_positive=True,
            hosted_shadow_pass=True,
        )
        self.assertEqual(PrimeMode.CANDIDATE_BOUNDED_TOPOLOGY_CONTROL, promoted.mode)
        self.assertTrue(promoted.bounded_topology_control_allowed)
        self.assertFalse(promoted.external_effect_control_allowed)
        self.assertFalse(promoted.stable_self_promotion_allowed)

    def test_provider_required_promotion_cannot_inherit_runtime_proof(self):
        decision = prime_promotion_gate(
            baseline_quality=0.70,
            candidate_quality=0.80,
            paired_cases=30,
            hard_regressions=0,
            rollback_available=True,
            independent_verifier_pass=True,
            observed_owner_value_positive=True,
            hosted_shadow_pass=True,
            provider_runtime_required=True,
            provider_runtime_proven=False,
        )
        self.assertEqual(PrimeMode.HOLD, decision.mode)
        self.assertIn("PROVIDER_RUNTIME_PROOF_REQUIRED", decision.reason_codes)

    def test_manifest_proves_composition_not_new_authority(self):
        manifest = prime_capability_manifest()
        self.assertEqual(0, manifest["new_authority_planes"])
        self.assertEqual(0, manifest["new_schedulers"])
        self.assertEqual(0, manifest["new_memory_roots"])
        self.assertEqual(0, manifest["new_provider_executors"])
        self.assertFalse(manifest["v1_live_effect_authority"])
        self.assertEqual(PrimeMode.SHADOW_ONLY.value, manifest["v1_mode"])


if __name__ == "__main__":
    unittest.main()
