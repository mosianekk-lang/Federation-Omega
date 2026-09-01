import unittest

from benchmarking.cfbe_omega.bco_prime_anticipatory_institution_v4 import (
    BuildDecision,
    CapabilityAction,
    CapabilitySignal,
    CapabilityUseObservation,
    DemandSignal,
    MutationDecision,
    V4Mode,
    anticipatory_mutation_gate,
    capability_opportunities,
    capability_utilization_court,
    compile_v4_decision,
    composition_search,
    interface_pressure,
    new_capability_build_gate,
    select_future_demand,
    v4_capability_manifest,
)
from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeObservation,
    StrategyCandidate,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import MetaCognitiveState
from formation_omega.institutional_cognition import Horizon
from formation_omega.reconciliation_fabric_v2 import TaskGraphProfile


def capability(
    capability_id="CAP-A",
    interfaces=("source.read", "proof.verify"),
    failure_domain="github",
    state="LIVE_VERIFIED",
    eligible=10,
    used=8,
    success=8,
    external=False,
    authority=True,
    maintenance=0.15,
):
    return CapabilitySignal(
        capability_id=capability_id,
        interfaces=interfaces,
        providers=(failure_domain,),
        failure_domain=failure_domain,
        state=state,
        proof_age_hours=2.0,
        eligible_missions=eligible,
        used_missions=used,
        successful_uses=success,
        reliability=0.92,
        owner_burden_reduction=0.85,
        cost_efficiency=0.90,
        failure_domain_uniqueness=0.80,
        strategic_option_value=0.85,
        maintenance_burden=maintenance,
        context_burden=0.15,
        authority_ready=authority,
        external_effect=external,
        evidence_refs=("proof:1",),
    )


def demand(
    demand_id="D1",
    horizon=Horizon.OPERATIONAL,
    interfaces=("source.read",),
    probability=0.9,
    value=0.9,
    uncertainty=0.4,
    external=False,
):
    return DemandSignal(
        demand_id=demand_id,
        horizon=horizon,
        required_interfaces=interfaces,
        probability=probability,
        value=value,
        urgency=0.8,
        option_value=0.8,
        dependency_centrality=0.7,
        evidence_strength=0.9,
        uncertainty=uncertainty,
        external_effect=external,
        evidence_refs=("demand:1",),
    )


def observation():
    return PrimeObservation(
        mission_id="MISSION-V4-001",
        objective_sha256="1" * 64,
        graph=TaskGraphProfile(
            node_count=12,
            edge_count=10,
            ready_parallel_count=5,
            shared_state_key_count=1,
            deterministic_fraction=0.75,
            uncertainty=0.45,
            evidence_conflict=0.15,
            consequential_fraction=0.0,
        ),
        meta_state=MetaCognitiveState(
            confidence=0.8,
            evidence_coverage=0.85,
            contradiction_pressure=0.1,
            novelty=0.45,
            progress=0.7,
            plan_stability=0.75,
            context_freshness=0.9,
            resource_pressure=0.3,
            repeated_failure_count=0,
        ),
        effect_class="NO_EFFECT",
        reversible=True,
        exact_authority=True,
        provider_runtime_available=True,
        active_streams=2,
        owner_burden=0.2,
        architecture_overlap=0.2,
        frontier_gap=0.3,
    )


def strategy(strategy_id="S1", failure_domain="git"):
    return StrategyCandidate(
        strategy_id=strategy_id,
        failure_domain=failure_domain,
        expected_quality=0.9,
        evidence_strength=0.9,
        reliability=0.9,
        reversibility=1.0,
        information_gain=0.8,
        failure_domain_diversity=0.8,
        latency_cost=0.2,
        monetary_cost=0.0,
        owner_burden=0.1,
        risk=0.1,
    )


class CapabilityUtilizationCourtTests(unittest.TestCase):
    def test_unjustified_relevant_skip_blocks_terminality(self):
        receipt = capability_utilization_court(
            [CapabilityUseObservation("GITHUB", relevance=0.95, used=False)]
        )
        self.assertFalse(receipt.terminality_allowed)
        self.assertEqual(receipt.unjustified_skips, ("GITHUB",))

    def test_valid_skip_reason_is_accepted(self):
        receipt = capability_utilization_court(
            [CapabilityUseObservation("CANVA", relevance=0.7, used=False, skip_reason="LOWER_FIT_THAN_SELECTED_ROUTE")]
        )
        self.assertTrue(receipt.terminality_allowed)
        self.assertEqual(receipt.justified_skips, 1)

    def test_manual_work_leak_blocks_when_system_can_execute(self):
        receipt = capability_utilization_court(
            [CapabilityUseObservation("GIT", relevance=0.9, used=True, manual_user_fallback=True, executable_by_system=True)]
        )
        self.assertFalse(receipt.terminality_allowed)
        self.assertEqual(receipt.manual_work_leaks, ("GIT",))

    def test_safe_parallelism_underuse_blocks(self):
        receipt = capability_utilization_court(
            [CapabilityUseObservation("READ-A", relevance=0.8, used=True, safe_parallelizable=True, executed_in_parallel=False)]
        )
        self.assertFalse(receipt.terminality_allowed)
        self.assertEqual(receipt.parallelism_underuse, ("READ-A",))

    def test_fresh_readback_underuse_blocks(self):
        receipt = capability_utilization_court(
            [CapabilityUseObservation("PROVIDER", relevance=0.8, used=True, current_readback_available=True, current_readback_used=False)]
        )
        self.assertFalse(receipt.terminality_allowed)
        self.assertEqual(receipt.freshness_underuse, ("PROVIDER",))


class AnticipatoryEcologyTests(unittest.TestCase):
    def test_multitimescale_selection_preserves_generational_signal(self):
        signals = (
            demand("T", Horizon.TACTICAL, ("a",)),
            demand("O", Horizon.OPERATIONAL, ("b",)),
            demand("S", Horizon.STRATEGIC, ("c",)),
            demand("G", Horizon.GENERATIONAL, ("d",)),
        )
        selected = select_future_demand(signals, slots=4)
        self.assertEqual({x.demand_id for x in selected}, {"T", "O", "S", "G"})

    def test_soe_interface_pressure_is_normalized(self):
        pressure = interface_pressure((demand("D1", interfaces=("source.read",)), demand("D2", interfaces=("source.read", "proof.verify")),))
        self.assertTrue(pressure)
        self.assertEqual(max(score for _, score in pressure), 1.0)

    def test_underused_high_fit_capability_triggers_router_challenge(self):
        cap = capability(eligible=20, used=2, success=2)
        opportunities = capability_opportunities((cap,), (demand(),), interface_pressure((demand(),)))
        self.assertEqual(opportunities[0].recommended_action, CapabilityAction.ROUTER_CHALLENGE)
        self.assertIn("UNDEREXPLOITED_HIGH_FIT_CAPABILITY", opportunities[0].reason_codes)

    def test_external_capability_without_authority_is_held(self):
        cap = capability(external=True, authority=False)
        opportunities = capability_opportunities((cap,), (demand(),), interface_pressure((demand(),)))
        self.assertEqual(opportunities[0].recommended_action, CapabilityAction.HOLD_PROVIDER)

    def test_composition_search_rewards_failure_domain_diversity(self):
        caps = (
            capability("GITHUB", ("source.read",), "github"),
            capability("DRIVE", ("memory.read",), "google"),
            capability("GIT2", ("memory.read",), "github"),
        )
        signals = (demand("D", interfaces=("source.read", "memory.read")),)
        results = composition_search(caps, signals)
        self.assertTrue(results)
        self.assertEqual(set(results[0].capability_ids), {"GITHUB", "DRIVE"})
        self.assertEqual(results[0].failure_domain_diversity, 1.0)


class InvestmentAndEvolutionTests(unittest.TestCase):
    def test_new_build_rejected_when_existing_live_coverage_is_high(self):
        result = new_capability_build_gate(
            required_interfaces=("source.read", "proof.verify"),
            existing_capabilities=(capability(),),
            future_signals=(demand(interfaces=("source.read", "proof.verify")),),
        )
        self.assertEqual(result.decision, BuildDecision.REUSE_OR_EXTEND)
        self.assertEqual(result.existing_interface_coverage, 1.0)

    def test_new_build_candidate_requires_real_uncovered_demand(self):
        result = new_capability_build_gate(
            required_interfaces=("future.interface",),
            existing_capabilities=(capability(),),
            future_signals=(demand(interfaces=("future.interface",), probability=1.0, value=1.0),),
        )
        self.assertEqual(result.decision, BuildDecision.CANDIDATE_NEW_CAPABILITY)
        self.assertIn("UNIQUE_UNCOVERED_CAPABILITY_GAP", result.reason_codes)

    def test_mutation_gate_never_self_promotes_stable_or_effectful(self):
        result = anticipatory_mutation_gate(
            improvement_id="MUT-1",
            baseline_score=0.5,
            candidate_score=0.8,
            hard_regression=False,
            independent_reproduction=True,
            rollback_verified=True,
        )
        self.assertEqual(result.decision, MutationDecision.CANDIDATE_SHADOW_EVOLUTION)
        self.assertFalse(result.stable_self_promotion_allowed)
        self.assertFalse(result.external_effect_authorized)

    def test_mutation_without_rollback_is_held(self):
        result = anticipatory_mutation_gate(
            improvement_id="MUT-2",
            baseline_score=0.5,
            candidate_score=0.8,
            hard_regression=False,
            independent_reproduction=True,
            rollback_verified=False,
        )
        self.assertEqual(result.decision, MutationDecision.HOLD)
        self.assertIn("ROLLBACK_REQUIRED", result.blockers)


class V4IntegrationTests(unittest.TestCase):
    def test_v4_decision_is_deterministic_and_no_effect(self):
        kwargs = dict(
            source_head_sha="a" * 40,
            observation=observation(),
            strategies=(strategy("S1", "git"), strategy("S2", "google")),
            capabilities=(
                capability("GITHUB", ("source.read",), "github"),
                capability("DRIVE", ("memory.read",), "google"),
            ),
            utilization=(
                CapabilityUseObservation("GITHUB", relevance=1.0, used=True, current_readback_available=True, current_readback_used=True),
                CapabilityUseObservation("DRIVE", relevance=0.8, used=True),
            ),
            future_demand=(
                demand("OP", Horizon.OPERATIONAL, ("source.read",), uncertainty=0.3),
                demand("STRAT", Horizon.STRATEGIC, ("memory.read",), uncertainty=0.8),
            ),
        )
        left = compile_v4_decision(**kwargs)
        right = compile_v4_decision(**kwargs)
        self.assertEqual(left, right)
        self.assertEqual(left.mode, V4Mode.SHADOW_ONLY)
        self.assertFalse(left.dispatch_authorized)
        self.assertFalse(left.external_effect_authorized)
        self.assertFalse(left.stable_self_promotion_allowed)
        self.assertGreaterEqual(left.horizon_depth, 10)
        self.assertEqual(len(left.receipt_sha256), 64)

    def test_underuse_forces_hold_and_repair_action(self):
        result = compile_v4_decision(
            source_head_sha="b" * 40,
            observation=observation(),
            strategies=(strategy(),),
            capabilities=(capability(),),
            utilization=(CapabilityUseObservation("CAP-A", relevance=1.0, used=False),),
            future_demand=(demand(),),
        )
        self.assertEqual(result.mode, V4Mode.HOLD_CAPABILITY_UNDERUSE)
        self.assertIn("REPAIR_CAPABILITY_UNDERUSE_BEFORE_TERMINALITY", result.preparatory_actions)

    def test_manifest_proves_reuse_and_zero_new_sovereign_planes(self):
        manifest = v4_capability_manifest()
        self.assertEqual(manifest["new_schedulers"], 0)
        self.assertEqual(manifest["new_memory_roots"], 0)
        self.assertEqual(manifest["new_provider_executors"], 0)
        self.assertEqual(manifest["new_authority_planes"], 0)
        self.assertEqual(manifest["new_proof_planes"], 0)
        self.assertFalse(manifest["v4_provider_effect_authority"])
        self.assertFalse(manifest["v4_stable_self_promotion"])
        self.assertEqual(manifest["composition"]["strategic_objective_ecology"], "formation_omega.strategic_ecology")


if __name__ == "__main__":
    unittest.main()
