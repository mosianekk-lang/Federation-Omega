from __future__ import annotations

import unittest

from ops.sovara_ao5_full_v2.adaptive_optimizer import (
    AO5_BOUND_PARTS,
    RAW_AO5_SOURCE_SHA256,
    AdaptiveCognitiveExecutionGovernor,
    AdaptiveCorrectionController,
    AdaptiveRoutePosterior,
    ChatOptimizationController,
    ChatSignals,
    CorrectionSignals,
    FailureDomainPortfolio,
    GovernorInput,
    InformationProbe,
    MethodDelta,
    PersistedCognitiveState,
    RouteEvidence,
    SafeContextCompactor,
    SessionRebaseProtocol,
    SessionSignals,
    SessionSnapshot,
    SplitBrainSentinel,
    TrajectoryCohortMiner,
    TrajectoryEvent,
    ValueOfInformationAllocator,
    run_adaptive_canary,
    synthetic_benchmark,
)
from ops.sovara_ao5_full_v2.ao5_full_engine import AO5


def route(route_id, domain, *, successes=5, failures=1, age=10, ttl=1000, **kwargs):
    values = dict(
        quality=.8,
        reliability=.8,
        evidence_strength=.8,
        information_gain=.6,
        expected_latency=.2,
        expected_cost=.1,
        owner_burden=.1,
        regression_risk=.1,
    )
    values.update(kwargs)
    return RouteEvidence(
        route_id,
        domain,
        successes,
        failures,
        proof_ref=f"proof-{route_id}",
        proof_age_seconds=age,
        proof_ttl_seconds=ttl,
        **values,
    )


class AdaptiveOptimizerTests(unittest.TestCase):
    def test_source_identity_bound_to_raw_upload(self):
        self.assertEqual(
            RAW_AO5_SOURCE_SHA256,
            "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443",
        )

    def test_optimizer_binds_required_ao5_parts(self):
        self.assertEqual(
            set(AO5_BOUND_PARTS),
            {"XIV", "XXI", "XXXIV", "XXXV", "XXXIX", "XL", "XLII", "XLIII", "XLVII", "XLVIII"},
        )

    def test_stale_proof_is_hard_block(self):
        ranked = AdaptiveRoutePosterior().rank((
            route("stale", "A", age=2000, ttl=1000),
            route("fresh", "A"),
        ))
        by_id = {item.route_id: item for item in ranked}
        self.assertFalse(by_id["stale"].eligible)
        self.assertIn("STALE_PROOF", by_id["stale"].reasons)
        self.assertEqual(ranked[0].route_id, "fresh")

    def test_privacy_authority_runtime_budget_are_hard_gates(self):
        routes = (
            route("privacy", "A", privacy_allowed=False),
            route("authority", "A", authority_allowed=False),
            route("runtime", "A", runtime_healthy=False),
            route("budget", "A", budget_available=False),
            route("good", "B"),
        )
        ranked = AdaptiveRoutePosterior().rank(routes)
        self.assertEqual(ranked[0].route_id, "good")
        self.assertEqual(sum(item.eligible for item in ranked), 1)

    def test_failure_domain_portfolio_diversifies(self):
        ranked = AdaptiveRoutePosterior().rank((
            route("a1", "A", quality=.95),
            route("a2", "A", quality=.9),
            route("b1", "B", quality=.8),
        ))
        portfolio = FailureDomainPortfolio().choose(ranked, shadow_count=1)
        self.assertEqual(portfolio.champion, "a1")
        self.assertEqual(portfolio.shadows, ("b1",))
        self.assertEqual(portfolio.distinct_failure_domains, 2)

    def test_trajectory_cohort_penalizes_repeated_failure_and_owner_correction(self):
        miner = TrajectoryCohortMiner()
        events = (
            TrajectoryEvent("bad", "A", False, True, .8, .8, .8, "p1"),
            TrajectoryEvent("bad", "A", False, False, .7, .7, .7, "p2"),
            TrajectoryEvent("good", "B", True, False, .1, .1, .1, "p3"),
        )
        penalties = miner.penalties(events)
        self.assertGreater(penalties["bad"], penalties["good"])
        ranked = AdaptiveRoutePosterior().rank(
            (route("bad", "A", quality=.95), route("good", "B", quality=.8)),
            trajectory_penalties=penalties,
        )
        self.assertEqual(ranked[0].route_id, "good")

    def test_split_brain_sentinel_holds_divergent_effectful_sessions(self):
        decision = SplitBrainSentinel().assess((
            SessionSnapshot("s1", 1, "a", True),
            SessionSnapshot("s2", 2, "b", True),
        ))
        self.assertEqual(decision.state, "HOLD_SPLIT_BRAIN_RECONCILE")
        self.assertEqual(decision.conflicting_sessions, ("s1", "s2"))

    def test_split_brain_allows_non_effectful_divergence(self):
        decision = SplitBrainSentinel().assess((
            SessionSnapshot("s1", 1, "a", False),
            SessionSnapshot("s2", 2, "b", False),
        ))
        self.assertEqual(decision.state, "CLEAR")

    def test_voi_selects_discriminator(self):
        probes = (
            InformationProbe("bulk", .3, .5, .8, .4),
            InformationProbe("disc", .95, .95, .95, .2),
        )
        ranked = ValueOfInformationAllocator().rank(probes)
        self.assertEqual(ranked[0].probe_id, "disc")

    def test_compactor_preserves_adverse_gaps_and_blockers(self):
        state = PersistedCognitiveState(
            adverse_evidence=("A", "A"),
            gaps=("G",),
            active_blockers=("B",),
            transient_notes=tuple(str(i) for i in range(30)),
        )
        receipt = SafeContextCompactor().compact(state, max_transient=5)
        self.assertTrue(receipt.protected_state_preserved)
        self.assertEqual(receipt.compacted.adverse_evidence, ("A",))
        self.assertEqual(receipt.compacted.gaps, ("G",))
        self.assertEqual(receipt.compacted.active_blockers, ("B",))
        self.assertEqual(len(receipt.compacted.transient_notes), 5)

    def test_stale_effectful_session_holds(self):
        decision = SessionRebaseProtocol().decide(SessionSignals(1, 2, "a", "b", True))
        self.assertTrue(decision.action.startswith("HOLD_STALE_EFFECTFUL"))

    def test_stale_non_effectful_session_rebases(self):
        decision = SessionRebaseProtocol().decide(SessionSignals(1, 2, "a", "b", False))
        self.assertTrue(decision.action.startswith("REBASE_NON_EFFECTFUL"))

    def test_owner_wait_signal_forces_fast_release(self):
        controller = ChatOptimizationController(AO5())
        session = SessionRebaseProtocol().decide(SessionSignals(1, 1, "a", "a", False))
        decision = controller.decide(ChatSignals(owner_wait_signal=True), session)
        self.assertTrue(decision.fast_release_required)
        self.assertIn("AO5_THROUGHPUT_FAILURE", decision.reasons)

    def test_material_verified_finding_releases_early(self):
        controller = ChatOptimizationController(AO5())
        session = SessionRebaseProtocol().decide(SessionSignals(1, 1, "a", "a", False))
        decision = controller.decide(ChatSignals(material_verified_finding=True), session)
        self.assertTrue(decision.fast_release_required)
        self.assertIn("FEDERATION_OUTPUT_CADENCE_GUARD", decision.reasons)

    def test_five_tool_ops_since_output_triggers_cadence(self):
        controller = ChatOptimizationController(AO5())
        session = SessionRebaseProtocol().decide(SessionSignals(1, 1, "a", "a", False))
        decision = controller.decide(
            ChatSignals(tool_operations_since_visible_output=5),
            session,
        )
        self.assertTrue(decision.fast_release_required)

    def test_context_85_requires_handoff(self):
        controller = ChatOptimizationController(AO5())
        session = SessionRebaseProtocol().decide(SessionSignals(1, 1, "a", "a", False))
        decision = controller.decide(ChatSignals(context_percent=85), session)
        self.assertEqual(decision.action, "CHECKPOINT_VERIFY_HANDOFF")
        self.assertTrue(decision.handoff_required)

    def test_budget_excess_causes_lane_split(self):
        controller = ChatOptimizationController(AO5())
        session = SessionRebaseProtocol().decide(SessionSignals(1, 1, "a", "a", False))
        decision = controller.decide(ChatSignals(tool_operations=30), session)
        self.assertTrue(decision.lane_split_required)

    def test_first_second_third_recurrence_escalation(self):
        controller = AdaptiveCorrectionController(AO5())
        self.assertEqual(
            controller.decide(CorrectionSignals(recurrence_count=1), MethodDelta()).recurrence_action,
            "STRENGTHEN_CONTROL",
        )
        self.assertEqual(
            controller.decide(CorrectionSignals(recurrence_count=2), MethodDelta()).recurrence_action,
            "OMEGA_SCIENTIST_ARCHITECTURE_REVIEW",
        )
        self.assertEqual(
            controller.decide(CorrectionSignals(recurrence_count=3), MethodDelta()).recurrence_action,
            "REDESIGN_OR_ROLLBACK",
        )

    def test_promotion_requires_all_proof_gates(self):
        controller = AdaptiveCorrectionController(AO5())
        signals = CorrectionSignals(
            regression_pass=True,
            forward_canary_pass=True,
            independent_readback=True,
            rollback_available=True,
        )
        decision = controller.decide(signals, MethodDelta(decision_value=.1))
        self.assertTrue(decision.promotion_allowed)
        incomplete = controller.decide(
            CorrectionSignals(
                regression_pass=True,
                forward_canary_pass=True,
                rollback_available=True,
            ),
            MethodDelta(decision_value=.1),
        )
        self.assertFalse(incomplete.promotion_allowed)

    def test_authority_expansion_blocks_promotion(self):
        signals = CorrectionSignals(
            regression_pass=True,
            forward_canary_pass=True,
            independent_readback=True,
            rollback_available=True,
            authority_expansion=True,
        )
        decision = AdaptiveCorrectionController(AO5()).decide(
            signals,
            MethodDelta(decision_value=.1),
        )
        self.assertFalse(decision.promotion_allowed)
        self.assertIn("AUTHORITY_EXPANSION_FORBIDDEN", decision.promotion_reasons)

    def test_external_effect_blocks_optimizer_promotion(self):
        signals = CorrectionSignals(
            regression_pass=True,
            forward_canary_pass=True,
            independent_readback=True,
            rollback_available=True,
            external_effect=True,
        )
        decision = AdaptiveCorrectionController(AO5()).decide(
            signals,
            MethodDelta(decision_value=.1),
        )
        self.assertFalse(decision.promotion_allowed)

    def test_near_miss_learns_before_failure(self):
        decision = AdaptiveCorrectionController(AO5()).decide(
            CorrectionSignals(near_miss_present=True),
            MethodDelta(),
        )
        self.assertEqual(decision.near_miss_learning["action"], "LEARN_BEFORE_FAILURE")

    def test_scientist_record_is_ao5_valid(self):
        record = AdaptiveCorrectionController(AO5()).scientist_record(
            baseline="b",
            candidate="c",
            metrics={
                "accuracy": .8,
                "source_fidelity": 1,
                "decision_value": .8,
                "information_gain": .7,
                "latency": .2,
                "tool_cost": .2,
                "owner_load": .1,
                "failure_rate": .1,
                "context_cost": .2,
                "regression_result": "PASS",
                "promotion_state": "SHADOW",
            },
        )
        self.assertEqual(record["regression_result"], "PASS")

    def test_end_to_end_canary(self):
        result = run_adaptive_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 21)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_governor_realityguard_internal_receipt(self):
        governor = AdaptiveCognitiveExecutionGovernor()
        payload = GovernorInput(
            routes=(route("r", "A"),),
            probes=(),
            state=PersistedCognitiveState(),
            session=SessionSignals(1, 1, "x", "x"),
            chat=ChatSignals(),
        )
        result = governor.evaluate(payload)
        self.assertTrue(result.realityguard_complete)
        self.assertEqual(result.external_effects, 0)
        self.assertEqual(len(result.receipt_sha256), 64)

    def test_synthetic_benchmark_has_no_production_or_tenx_claim(self):
        benchmark = synthetic_benchmark()
        self.assertFalse(benchmark["provider_performance_claim"])
        self.assertFalse(benchmark["ten_x_claim"])
        self.assertEqual(
            benchmark["benchmark_class"],
            "SYNTHETIC_DETERMINISTIC_MATCHED_SCENARIO",
        )


if __name__ == "__main__":
    unittest.main()
