import unittest

from bubbles.chat_governor_omega3.frontier_runtime_v2 import (
    AblationObservation,
    AdmissionTask,
    CausalAblationAnalyzer,
    DependencyResultCache,
    ExistingReadHedgeAdmission,
    GenerationMetrics,
    GenerationRolloutGovernor,
    MissionGenerationRouter,
    QueuePressureGovernor,
    frontier_runtime_v2_receipt,
)


class DependencyCacheTests(unittest.TestCase):
    def test_exact_dependency_identity_reuses_and_changed_dependency_invalidates(self):
        cache = DependencyResultCache()
        item = cache.put(
            node_id="synthesis",
            input_payload={"q": "x"},
            dependency_result_sha256s={"research": "a" * 64, "repo": "b" * 64},
            code_version="v2",
            source_version="main@1",
            result_ref="artifact://1",
            result={"answer": 7},
            proof_ref="proof://1",
        )
        hit = cache.get(
            node_id="synthesis",
            input_payload={"q": "x"},
            dependency_result_sha256s={"research": "a" * 64, "repo": "b" * 64},
            code_version="v2",
            source_version="main@1",
        )
        self.assertEqual(item, hit)
        miss = cache.get(
            node_id="synthesis",
            input_payload={"q": "x"},
            dependency_result_sha256s={"research": "c" * 64, "repo": "b" * 64},
            code_version="v2",
            source_version="main@1",
        )
        self.assertIsNone(miss)
        self.assertEqual(1, cache.hits)
        self.assertEqual(1, cache.misses)

    def test_effectful_result_cannot_enter_incremental_cache(self):
        cache = DependencyResultCache()
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_CACHE_EFFECTFUL_RESULT_FORBIDDEN"):
            cache.put(
                node_id="send",
                input_payload={},
                dependency_result_sha256s={},
                code_version="1",
                source_version="1",
                result_ref="r",
                result="sent",
                proof_ref="p",
                effect_class="CONSEQUENTIAL_EFFECT",
            )


class BackpressureTests(unittest.TestCase):
    def test_required_work_queues_but_optional_low_value_sheds(self):
        governor = QueuePressureGovernor(max_ongoing=2, max_queued=3, optional_shed_score=70)
        required = governor.decide(
            AdmissionTask("critical", 50, 0, 10, True, 0.9),
            ongoing=2,
            queued=1,
            observed_service_seconds=2,
        )
        self.assertEqual("QUEUE_BOUNDED", required.action)
        optional = governor.decide(
            AdmissionTask("nice-to-have", 5, 0, None, False, 0.1),
            ongoing=2,
            queued=0,
        )
        self.assertEqual("SHED_OPTIONAL", optional.action)

    def test_queue_full_never_silently_drops_required_work(self):
        governor = QueuePressureGovernor(max_ongoing=1, max_queued=1)
        decision = governor.decide(
            AdmissionTask("must", 100, 100, 0, True, 1.0),
            ongoing=1,
            queued=1,
        )
        self.assertEqual("HOLD_REQUIRED_BACKPRESSURE", decision.action)

    def test_priority_ageing_increases_effective_priority(self):
        young = AdmissionTask("young", 10, 0, None, False, 0.5)
        old = AdmissionTask("old", 10, 3600, None, False, 0.5)
        self.assertGreater(QueuePressureGovernor.effective_priority(old), QueuePressureGovernor.effective_priority(young))


class RolloutTests(unittest.TestCase):
    @staticmethod
    def champion():
        return GenerationMetrics("gen-1", 95, 100, 0, 100, 1.0, 0.20)

    def test_good_candidate_ramps_progressively(self):
        governor = GenerationRolloutGovernor(min_trials=30, stable_trials=100)
        candidate = GenerationMetrics("gen-2", 49, 50, 0, 90, 0.90, 0.10)
        decision = governor.decide(champion=self.champion(), candidate=candidate, current_share=0.0)
        self.assertEqual("RAMP_CANDIDATE", decision.action)
        self.assertEqual(0.05, decision.next_share)

    def test_proof_violation_forces_rollback(self):
        governor = GenerationRolloutGovernor()
        candidate = GenerationMetrics("gen-2", 49, 50, 1, 50, 0.50, 0.0)
        decision = governor.decide(champion=self.champion(), candidate=candidate, current_share=0.25)
        self.assertEqual("ROLLBACK", decision.action)
        self.assertEqual(0.0, decision.next_share)

    def test_small_sample_cannot_promote(self):
        governor = GenerationRolloutGovernor(min_trials=30)
        candidate = GenerationMetrics("gen-2", 10, 10, 0, 50, 0.5, 0.0)
        decision = governor.decide(champion=self.champion(), candidate=candidate, current_share=0.0)
        self.assertEqual("HOLD_SHADOW", decision.action)

    def test_stable_requires_full_share_and_stable_sample(self):
        governor = GenerationRolloutGovernor(min_trials=30, stable_trials=100)
        champion = GenerationMetrics("gen-1", 190, 200, 0, 100, 1.0, 0.2)
        candidate = GenerationMetrics("gen-2", 198, 200, 0, 85, 0.8, 0.1)
        decision = governor.decide(champion=champion, candidate=candidate, current_share=1.0)
        self.assertEqual("STABLE_CANDIDATE", decision.action)


class GenerationPinTests(unittest.TestCase):
    def test_mid_execution_upgrade_is_forbidden(self):
        decision = MissionGenerationRouter.decide(
            current_generation="g1",
            candidate_generation="g2",
            checkpoint_boundary=False,
            candidate_qualified=True,
            state_compatible=True,
        )
        self.assertEqual("PIN_CURRENT", decision.action)
        self.assertEqual("g1", decision.generation)

    def test_qualified_candidate_upgrades_at_compatible_checkpoint(self):
        decision = MissionGenerationRouter.decide(
            current_generation="g1",
            candidate_generation="g2",
            checkpoint_boundary=True,
            candidate_qualified=True,
            state_compatible=True,
        )
        self.assertEqual("UPGRADE_AT_CHECKPOINT", decision.action)
        self.assertEqual("g2", decision.generation)


class AblationTests(unittest.TestCase):
    def test_matched_ablation_assigns_useful_and_negative_credit(self):
        analyzer = CausalAblationAnalyzer()
        rows = analyzer.analyze(
            baseline_utility=1.0,
            baseline_context_fingerprint="ctx",
            observations=[
                AblationObservation("cfbe", 0.70, True, "ctx", 10),
                AblationObservation("overhead", 1.10, True, "ctx", 10),
                AblationObservation("proofos", 1.20, True, "ctx", 10),
            ],
            safety_critical_components=["proofos"],
        )
        by_component = {row.component: row for row in rows}
        self.assertEqual("KEEP", by_component["cfbe"].action)
        self.assertEqual("REVIEW_REMOVE", by_component["overhead"].action)
        self.assertEqual("KEEP_SAFETY_CRITICAL", by_component["proofos"].action)

    def test_unmatched_context_is_inconclusive(self):
        analyzer = CausalAblationAnalyzer()
        row = analyzer.analyze(
            baseline_utility=1.0,
            baseline_context_fingerprint="a",
            observations=[AblationObservation("x", 0.0, True, "b", 100)],
        )[0]
        self.assertEqual("INCONCLUSIVE", row.action)


class HedgeAdmissionTests(unittest.TestCase):
    def test_tail_read_can_use_existing_slos_hedge_runtime(self):
        gate = ExistingReadHedgeAdmission(trigger_fraction_of_p95=0.9, max_active_hedges=2)
        decision = gate.decide(
            effect_class="READ_ONLY",
            idempotent=True,
            semantic_readback_available=True,
            elapsed_ms=950,
            historical_p95_ms=1000,
            deadline_remaining_ms=500,
            estimated_secondary_cost=0.2,
            hedge_budget_remaining=1.0,
            active_hedges=0,
        )
        self.assertTrue(decision.allow)
        self.assertIn("hedge_read_route", decision.runtime_route)

    def test_effectful_hedging_is_forbidden(self):
        gate = ExistingReadHedgeAdmission()
        decision = gate.decide(
            effect_class="CONSEQUENTIAL_EFFECT",
            idempotent=True,
            semantic_readback_available=True,
            elapsed_ms=1000,
            historical_p95_ms=1000,
            deadline_remaining_ms=1000,
            estimated_secondary_cost=0.1,
            hedge_budget_remaining=1.0,
            active_hedges=0,
        )
        self.assertFalse(decision.allow)
        self.assertEqual("EFFECTFUL_HEDGING_FORBIDDEN", decision.reason)


class ReceiptTests(unittest.TestCase):
    def test_receipt_never_claims_effect_or_promotion_authority(self):
        receipt = frontier_runtime_v2_receipt()
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.traffic_change_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertIn("GENERATION_CANARY_RAMP_ROLLBACK_POLICY", receipt.capabilities)


if __name__ == "__main__":
    unittest.main()
