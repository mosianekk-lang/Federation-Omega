import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from omega_one.hyperperformance import (
    AdaptiveConcurrencyController,
    BoundedRetryController,
    CampaignPolicy,
    ConcurrencyPolicy,
    DeploymentEvent,
    ExactlyOnceFinalizer,
    FinalizationDecision,
    MissionMeasurement,
    OutcomeState,
    PairedMissionObservation,
    RetryPolicy,
    SloErrorBudget,
    SloPolicy,
    WorkPriority,
    canonical_sha256,
    compile_dora_metrics,
    evaluate_paired_campaign,
    otel_measurement_attributes,
)
from proofos_omega.policy_loader import _load_policy
from proofos_omega.core import ImpactCompiler, ProofSelector
from omega_one.maturity import CapabilityMaturityCompiler, MaturityStage
from omega_one.portfolio import maturity_records
from benchmarking.omega_one_cfbe_local import run_campaign


class ExactlyOnceFinalizerTests(unittest.TestCase):
    def test_identical_retry_returns_one_canonical_receipt(self):
        finalizer = ExactlyOnceFinalizer()
        first = finalizer.finalize(
            "op-1", {"x": 1}, {"ok": True}, {"proof": "p"}, OutcomeState.SUCCEEDED
        )
        replay = finalizer.finalize(
            "op-1", {"x": 1}, {"ok": True}, {"proof": "p"}, OutcomeState.SUCCEEDED
        )
        self.assertEqual(first.decision, FinalizationDecision.COMMITTED)
        self.assertEqual(replay.decision, FinalizationDecision.REPLAYED)
        self.assertEqual(first.receipt, replay.receipt)
        self.assertEqual(finalizer.committed_count, 1)
        self.assertEqual(replay.replay_count, 1)

    def test_conflicting_payload_and_result_fail_closed(self):
        finalizer = ExactlyOnceFinalizer()
        finalizer.finalize("op-2", {"x": 1}, "A", "P", OutcomeState.SUCCEEDED)
        payload_conflict = finalizer.finalize(
            "op-2", {"x": 2}, "A", "P", OutcomeState.SUCCEEDED
        )
        result_conflict = finalizer.finalize(
            "op-2", {"x": 1}, "B", "P", OutcomeState.SUCCEEDED
        )
        self.assertEqual(payload_conflict.decision, FinalizationDecision.CONFLICT)
        self.assertEqual(result_conflict.decision, FinalizationDecision.CONFLICT)
        self.assertEqual(finalizer.committed_count, 1)

    def test_unknown_outcome_requires_readback_then_recovers(self):
        finalizer = ExactlyOnceFinalizer()
        held = finalizer.finalize(
            "op-3", {"x": 1}, None, {"attempt": 1}, OutcomeState.UNKNOWN
        )
        self.assertEqual(held.decision, FinalizationDecision.HELD)
        recovered = ExactlyOnceFinalizer.from_snapshot(finalizer.snapshot())
        self.assertEqual(
            recovered.readback("op-3", {"x": 1}).reason,
            "TERMINAL_RECEIPT_NOT_FOUND",
        )
        committed = recovered.finalize(
            "op-3", {"x": 1}, {"ok": True}, {"attempt": 2}, OutcomeState.SUCCEEDED
        )
        self.assertEqual(committed.decision, FinalizationDecision.COMMITTED)
        self.assertTrue(committed.receipt.verify())

    def test_snapshot_integrity_tamper_is_rejected(self):
        finalizer = ExactlyOnceFinalizer()
        finalizer.finalize("op-4", {}, "A", "P", OutcomeState.SUCCEEDED)
        tampered = copy.deepcopy(finalizer.snapshot())
        tampered["receipts"]["op-4"]["result_sha256"] = "sha256:bad"
        with self.assertRaises(ValueError):
            ExactlyOnceFinalizer.from_snapshot(tampered)

    def test_concurrent_duplicate_finalization_emits_one_receipt(self):
        finalizer = ExactlyOnceFinalizer()

        def commit(_):
            return finalizer.finalize(
                "op-concurrent",
                {"x": 1},
                {"ok": True},
                {"proof": "same"},
                OutcomeState.SUCCEEDED,
            )

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(commit, range(200)))
        receipt_ids = {item.receipt.receipt_id for item in results if item.receipt}
        self.assertEqual(receipt_ids, {results[0].receipt.receipt_id})
        self.assertEqual(finalizer.committed_count, 1)
        self.assertEqual(
            sum(item.decision is FinalizationDecision.COMMITTED for item in results), 1
        )

    def test_prehashed_fast_path_preserves_conflict_detection(self):
        finalizer = ExactlyOnceFinalizer()
        inputs = {
            "payload_sha256": canonical_sha256({"x": 1}),
            "result_sha256": canonical_sha256({"ok": True}),
            "proof_sha256": canonical_sha256({"proof": "same"}),
            "outcome": OutcomeState.SUCCEEDED,
        }
        first = finalizer.finalize_hashed("op-fast", **inputs)
        replay = finalizer.finalize_hashed("op-fast", **inputs)
        conflict = finalizer.finalize_hashed(
            "op-fast",
            **{**inputs, "result_sha256": canonical_sha256({"ok": False})},
        )
        self.assertEqual(first.decision, FinalizationDecision.COMMITTED)
        self.assertEqual(replay.decision, FinalizationDecision.REPLAYED)
        self.assertEqual(first.receipt, replay.receipt)
        self.assertEqual(conflict.decision, FinalizationDecision.CONFLICT)
        self.assertEqual(finalizer.committed_count, 1)

    def test_recovered_replay_batch_uses_one_atomic_receipt(self):
        finalizer = ExactlyOnceFinalizer()
        inputs = {
            "payload_sha256": canonical_sha256({"x": 1}),
            "result_sha256": canonical_sha256({"ok": True}),
            "proof_sha256": canonical_sha256({"proof": "same"}),
            "outcome": OutcomeState.SUCCEEDED,
        }
        first = finalizer.finalize_hashed_replay_batch(
            "op-batch", **inputs, attempt_count=4
        )
        second = finalizer.finalize_hashed_replay_batch(
            "op-batch", **inputs, attempt_count=2
        )
        self.assertEqual(first.decision, FinalizationDecision.COMMITTED)
        self.assertEqual(first.replay_count, 3)
        self.assertEqual(second.decision, FinalizationDecision.REPLAYED)
        self.assertEqual(second.replay_count, 5)
        self.assertEqual(first.receipt, second.receipt)
        self.assertEqual(finalizer.committed_count, 1)


class RetryAndConcurrencyTests(unittest.TestCase):
    def test_retry_budget_is_bounded_and_decisions_are_idempotent(self):
        controller = BoundedRetryController(
            RetryPolicy(max_attempts=3, max_retry_tokens=2, jitter_ratio=0)
        )
        first = controller.decide("op", 1, OutcomeState.FAILED)
        duplicate = controller.decide("op", 1, OutcomeState.FAILED)
        second = controller.decide("op", 2, OutcomeState.FAILED)
        exhausted = controller.decide("op", 3, OutcomeState.FAILED)
        self.assertEqual(first, duplicate)
        self.assertTrue(first.retry)
        self.assertTrue(second.retry)
        self.assertFalse(exhausted.retry)
        self.assertEqual(controller.tokens_remaining, 0)

    def test_unknown_outcome_does_not_spend_retry_token(self):
        controller = BoundedRetryController(RetryPolicy(max_retry_tokens=1))
        decision = controller.decide("op", 1, OutcomeState.UNKNOWN)
        self.assertFalse(decision.retry)
        self.assertEqual(decision.reason, "UNKNOWN_OUTCOME_REQUIRES_READBACK")
        self.assertEqual(controller.tokens_remaining, 1)

    def test_hash_jitter_is_reproducible(self):
        policy = RetryPolicy(max_retry_tokens=2, jitter_ratio=0.5)
        one = BoundedRetryController(policy).decide("op-a", 1, OutcomeState.FAILED)
        two = BoundedRetryController(policy).decide("op-a", 1, OutcomeState.FAILED)
        other = BoundedRetryController(policy).decide("op-b", 1, OutcomeState.FAILED)
        self.assertEqual(one.delay_seconds, two.delay_seconds)
        self.assertNotEqual(one.delay_seconds, other.delay_seconds)

    def test_adaptive_limit_decreases_recovers_and_sheds(self):
        controller = AdaptiveConcurrencyController(
            ConcurrencyPolicy(
                minimum=1,
                initial=4,
                maximum=6,
                target_latency_ms=100,
                decrease_ratio=0.5,
                success_window=2,
                critical_reserve=1,
            )
        )
        decrease = controller.observe(200)
        self.assertEqual((decrease.previous_limit, decrease.new_limit), (4, 2))
        controller.observe(50)
        increase = controller.observe(50)
        self.assertEqual(increase.new_limit, 3)
        self.assertFalse(controller.admit(WorkPriority.BULK, 3).admitted)
        self.assertTrue(controller.admit(WorkPriority.CRITICAL, 3).admitted)
        for _ in range(10):
            controller.observe(1000, error=True)
        self.assertEqual(controller.limit, 1)


class SloAndCampaignTests(unittest.TestCase):
    def test_slo_gate_holds_until_sample_floor_and_on_budget_exhaustion(self):
        budget = SloErrorBudget(
            SloPolicy(
                availability_target=0.9,
                latency_target=0.9,
                latency_threshold_ms=100,
                minimum_events=10,
            )
        )
        for _ in range(9):
            budget.record(success=True, latency_ms=50)
        self.assertFalse(budget.snapshot().release_allowed)
        budget.record(success=False, latency_ms=150)
        boundary = budget.snapshot()
        self.assertTrue(boundary.release_allowed)
        self.assertAlmostEqual(boundary.worst_burn_rate, 1.0)
        budget.record(success=False, latency_ms=150)
        exhausted = budget.snapshot()
        self.assertFalse(exhausted.release_allowed)
        self.assertEqual(exhausted.reason, "ERROR_BUDGET_EXHAUSTED")

    @staticmethod
    def pairs(count=30, candidate_latency=5.0):
        return [
            PairedMissionObservation(
                MissionMeasurement(
                    f"mission-{index}", f"sha256:oracle-{index}", 10.0, 1.0
                ),
                MissionMeasurement(
                    f"mission-{index}",
                    f"sha256:oracle-{index}",
                    candidate_latency,
                    1.0,
                ),
            )
            for index in range(count)
        ]

    def test_campaign_requires_thirty_cold_observed_pairs(self):
        verdict = evaluate_paired_campaign(self.pairs(29))
        self.assertEqual(verdict.state, "HELD")
        self.assertIn("MINIMUM_PAIRED_OBSERVATIONS_NOT_MET", verdict.reasons)

    def test_campaign_qualifies_local_measurement_without_overclaim(self):
        pairs = self.pairs()
        first = evaluate_paired_campaign(
            pairs, CampaignPolicy(minimum_median_speedup=1.5)
        )
        second = evaluate_paired_campaign(
            pairs, CampaignPolicy(minimum_median_speedup=1.5)
        )
        self.assertEqual(first.state, "QUALIFIED_LOCAL")
        self.assertEqual(first.median_speedup, 2.0)
        self.assertEqual(first.measurement_sha256, second.measurement_sha256)
        self.assertIn("NO_PROVIDER", first.truth_boundary)

    def test_semantic_quality_and_exactly_once_regressions_block(self):
        pairs = self.pairs()
        bad = pairs[0]
        pairs[0] = PairedMissionObservation(
            bad.baseline,
            MissionMeasurement(
                bad.candidate.mission_id,
                "sha256:different",
                bad.candidate.latency_ms,
                0.9,
                canonical_receipt_count=2,
            ),
        )
        verdict = evaluate_paired_campaign(pairs)
        self.assertEqual(verdict.state, "HELD")
        self.assertIn("SEMANTIC_ORACLE_MISMATCH", verdict.reasons)
        self.assertIn("QUALITY_REGRESSION", verdict.reasons)
        self.assertIn("EXACTLY_ONCE_RECEIPT_VIOLATION", verdict.reasons)

    def test_p95_tail_regression_blocks_fast_median(self):
        pairs = self.pairs()
        for index in (28, 29):
            baseline = pairs[index].baseline
            candidate = pairs[index].candidate
            pairs[index] = PairedMissionObservation(
                baseline,
                MissionMeasurement(
                    candidate.mission_id,
                    candidate.oracle_sha256,
                    100.0,
                    candidate.quality_score,
                ),
            )
        verdict = evaluate_paired_campaign(pairs)
        self.assertEqual(verdict.median_speedup, 2.0)
        self.assertEqual(verdict.state, "HELD")
        self.assertIn("P95_LATENCY_REGRESSION", verdict.reasons)

    def test_scenario_pair_cannot_be_promoted_as_observed(self):
        pairs = self.pairs()
        candidate = pairs[0].candidate
        pairs[0] = PairedMissionObservation(
            pairs[0].baseline,
            MissionMeasurement(
                candidate.mission_id,
                candidate.oracle_sha256,
                candidate.latency_ms,
                candidate.quality_score,
                source="SCENARIO",
            ),
        )
        verdict = evaluate_paired_campaign(pairs)
        self.assertIn("COLD_OBSERVED_PAIR_REQUIRED", verdict.reasons)


class DeliveryAndProofOSBindingTests(unittest.TestCase):
    def test_benchmark_harness_preserves_local_truth_boundary(self):
        result = run_campaign(pair_count=3, operations=5, attempts=3)
        self.assertEqual(result["source"], "LOCAL_OBSERVED_NON_PROVIDER")
        self.assertEqual(result["pair_count"], 3)
        self.assertEqual(result["baseline_receipts_per_pair"], 15)
        self.assertEqual(result["candidate_receipts_per_pair"], 5)
        self.assertAlmostEqual(result["canonical_receipt_reduction_ratio"], 2 / 3)
        self.assertIn("NO_PROVIDER", result["truth_boundary"])

    def test_host_observation_requires_thirty_pairs_and_exact_runtime_identity(self):
        with self.assertRaisesRegex(ValueError, "HOST_OBSERVED_MINIMUM_30_PAIRS_REQUIRED"):
            run_campaign(
                pair_count=29,
                operations=1,
                attempts=1,
                observation_source="GITHUB_ACTIONS_HOST_OBSERVED_NO_EFFECT",
                runtime_run_id="123",
                source_sha="a" * 40,
                runtime_environment="github-hosted",
            )
        with self.assertRaisesRegex(ValueError, "HOST_OBSERVED_RUNTIME_RUN_ID_REQUIRED"):
            run_campaign(
                pair_count=30,
                operations=1,
                attempts=1,
                observation_source="GITHUB_ACTIONS_HOST_OBSERVED_NO_EFFECT",
                source_sha="a" * 40,
                runtime_environment="github-hosted",
            )
        with self.assertRaisesRegex(ValueError, "HOST_OBSERVED_40_HEX_SOURCE_SHA_REQUIRED"):
            run_campaign(
                pair_count=30,
                operations=1,
                attempts=1,
                observation_source="GITHUB_ACTIONS_HOST_OBSERVED_NO_EFFECT",
                runtime_run_id="123",
                source_sha="not-a-sha",
                runtime_environment="github-hosted",
            )

    def test_only_exact_full_capability_mappings_gain_local_maturity(self):
        verdicts = {
            verdict.capability_id: verdict
            for verdict in CapabilityMaturityCompiler.compile_portfolio(maturity_records())
        }
        for capability_id in ("CAP-036", "CAP-045", "CAP-047"):
            self.assertEqual(
                verdicts[capability_id].lowest_proven_stage,
                MaturityStage.DETERMINISTIC_TESTED,
            )
            self.assertEqual(
                verdicts[capability_id].next_required_stage,
                MaturityStage.CI_ADMITTED,
            )
        for partial_mapping in ("CAP-026", "CAP-061", "CAP-064", "CAP-076", "CAP-088"):
            self.assertEqual(
                verdicts[partial_mapping].lowest_proven_stage,
                MaturityStage.DESIGNED,
            )

    def test_dora_metrics_compile_all_five_current_signals(self):
        snapshot = compile_dora_metrics(
            [
                DeploymentEvent("d1", 0, 100),
                DeploymentEvent("d2", 100, 300, failed=True, rework=True, recovered_at=360),
            ],
            observation_days=2,
        )
        self.assertEqual(snapshot.deployment_count, 2)
        self.assertEqual(snapshot.deployments_per_day, 1)
        self.assertEqual(snapshot.median_change_lead_time_seconds, 150)
        self.assertEqual(snapshot.failed_deployment_rate, 0.5)
        self.assertEqual(snapshot.deployment_rework_rate, 0.5)
        self.assertEqual(snapshot.median_failed_deployment_recovery_seconds, 60)

    def test_otel_attributes_preserve_truth_and_authority_boundaries(self):
        attributes = otel_measurement_attributes(
            mission_id="M1",
            operation_name="execute_tool",
            state="QUALIFIED_LOCAL",
            measurement_sha256="sha256:abc",
        )
        self.assertEqual(attributes["service.name"], "omega-one")
        self.assertEqual(attributes["gen_ai.operation.name"], "execute_tool")
        self.assertEqual(attributes["omega.execution.authority"], "NONE")
        self.assertEqual(attributes["omega.truth.boundary"], "LOCAL_OBSERVED_ONLY")

    def test_proofos_selects_v085_and_v086_courts(self):
        root = Path(__file__).resolve().parents[1]
        policy = _load_policy(root / "governance" / "proofos_omega_policy_v1.json", root)
        impact = ImpactCompiler(policy).assess(
            [
                "omega_one/hyperperformance.py",
                "benchmarking/omega_one_cfbe_local.py",
                "tests/test_omega_one_v086_hyperperformance.py",
                "proofos_omega/policy_extensions_v1.json",
            ]
        )
        manifest = ProofSelector(policy).compile_manifest(
            base_sha="a" * 40,
            head_sha="b" * 40,
            impact=impact,
        )
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("omega_one_v085_maturity_interop", selected)
        self.assertIn("omega_one_v086_hyperperformance", selected)
        self.assertFalse(manifest.selector_state["fallback_full_suite_activated"])


if __name__ == "__main__":
    unittest.main()
