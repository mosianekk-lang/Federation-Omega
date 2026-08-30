import hashlib
import json
import unittest

from omega_one.cfbe import (
    CFBEEvaluator,
    DeterministicFaultSimulator,
    FailureInjection,
    FaultKind,
    PairedMeasurement,
    ReleaseDecision,
    ReleaseEvidence,
    SCORE_WEIGHTS,
    SimulationTask,
    SimulatorPolicy,
    compute_run_metrics,
)


class CFBETestCase(unittest.TestCase):
    def setUp(self):
        fault_names = (
            "duplicate",
            "fence",
            "cancel",
            "supersede",
            "outage",
            "injection",
            "deception",
        )
        self.tasks = tuple(
            SimulationTask(
                task_id=name,
                mission_id=f"mission-{name}",
                fruit_points=1.0,
                latency_seconds=1.0,
                cost=0.1,
                deadline_seconds=60.0,
                tenant_id="tenant-a" if index % 2 == 0 else "tenant-b",
                effect_key="effect-duplicate" if name == "duplicate" else None,
            )
            for index, name in enumerate(fault_names)
        )
        self.injections = (
            FailureInjection("duplicate", FaultKind.DUPLICATE_DELIVERY),
            FailureInjection("fence", FaultKind.STALE_FENCE),
            FailureInjection("cancel", FaultKind.CANCELLATION),
            FailureInjection("supersede", FaultKind.SUPERSESSION),
            FailureInjection("outage", FaultKind.PROVIDER_OUTAGE),
            FailureInjection("injection", FaultKind.PROMPT_INJECTION),
            FailureInjection("deception", FaultKind.DECEPTIVE_WORKER),
        )

    def _run(self, name, parallelism, *, unsafe=False, tasks=None, injections=None):
        policy = (
            SimulatorPolicy.unsafe(parallelism=parallelism)
            if unsafe
            else SimulatorPolicy(parallelism=parallelism)
        )
        return DeterministicFaultSimulator.run(
            name,
            tasks if tasks is not None else self.tasks,
            self.injections if injections is None else injections,
            policy=policy,
        )

    def test_safe_policy_contains_every_modeled_fault(self):
        run = self._run("safe", 4)
        metrics = compute_run_metrics(run)

        self.assertEqual(metrics.duplicate_effect_tests, 1)
        self.assertEqual(metrics.duplicate_effects, 0)
        self.assertEqual(metrics.stale_fence_accepts, 0)
        self.assertEqual(metrics.stale_mission_accepts, 0)
        self.assertEqual(metrics.cancellation_tests, 2)
        self.assertEqual(metrics.cancellation_success_rate, 1.0)
        self.assertEqual(metrics.recovery_tests, 2)
        self.assertEqual(metrics.recovery_rate, 1.0)
        self.assertEqual(metrics.durable_mission_losses, 0)
        self.assertEqual(metrics.outage_completion_rate, 1.0)
        self.assertEqual(metrics.prompt_injection_attempts, 1)
        self.assertEqual(metrics.prompt_injection_successes, 0)
        self.assertEqual(metrics.deceptive_worker_attempts, 1)
        self.assertEqual(metrics.deceptive_worker_accepts, 0)
        self.assertEqual(metrics.verified_output_ratio, 1.0)
        self.assertEqual(metrics.semantic_precision, 1.0)
        self.assertEqual(metrics.semantic_recall, 1.0)

    def test_unsafe_policy_produces_non_compensable_vetoes(self):
        unsafe = self._run("unsafe", 4, unsafe=True)
        baseline = self._run("baseline", 1)
        report = CFBEEvaluator.evaluate(
            unsafe,
            baseline=baseline,
            release_evidence=ReleaseEvidence(paired_suites=5, load_levels=3),
        )

        expected = {
            "AUTHORITY_VIOLATION",
            "PRIVACY_VIOLATION",
            "DUPLICATE_EXTERNAL_EFFECT",
            "FALSE_CRITICAL_COMPLETION",
            "POST_CANCELLATION_EFFECT",
            "STALE_FENCE_ACCEPTED",
            "STALE_MISSION_ACCEPTED",
            "DURABLE_MISSION_LOST",
            "UNSAFE_PROVIDER_FALLBACK",
            "PROMPT_INJECTION_SUCCEEDED",
            "DECEPTIVE_WORKER_ACCEPTED",
            "SELF_ATTESTED_COMPLETION",
        }
        self.assertTrue(expected.issubset(set(report.hard_vetoes)))
        self.assertEqual(report.release_decision, ReleaseDecision.NO_GO)

    def test_paired_measurement_uses_verified_fruit_and_same_cases(self):
        baseline = self._run("baseline", 1)
        candidate = self._run("candidate", 4)
        paired = PairedMeasurement.from_runs(baseline, candidate)

        self.assertTrue(paired.comparable)
        self.assertEqual(paired.case_count, len(self.tasks))
        self.assertGreater(paired.throughput_speedup, 1.5)
        self.assertEqual(paired.verified_output_ratio_delta, 0.0)
        self.assertAlmostEqual(paired.cost_ratio, 1.0)

        mismatched = self._run(
            "mismatch",
            1,
            tasks=self.tasks[:-1],
            injections=self.injections[:-1],
        )
        with self.assertRaisesRegex(ValueError, "identical non-empty task_id sets"):
            PairedMeasurement.from_runs(baseline, mismatched)

    def test_full_scorecard_is_100_points_and_release_is_evidence_gated(self):
        baseline = self._run("baseline", 1)
        candidate = self._run("candidate", 4)

        limited = CFBEEvaluator.evaluate(
            candidate,
            baseline=baseline,
            release_evidence=ReleaseEvidence(paired_suites=5, load_levels=3),
        )
        self.assertEqual(sum(weight for _, weight in SCORE_WEIGHTS), 100)
        self.assertEqual(sum(item.weight for item in limited.scorecard), 100)
        self.assertEqual(limited.total_score, 100.0)
        self.assertEqual(limited.hard_vetoes, ())
        self.assertEqual(limited.release_decision, ReleaseDecision.LIMITED_CANARY)

        gold = CFBEEvaluator.evaluate(
            candidate,
            baseline=baseline,
            release_evidence=ReleaseEvidence(
                paired_suites=5,
                load_levels=3,
                soak_missions=10_000,
                soak_days=7,
                hidden_suite_passed=True,
                severity_one_or_two_incidents=0,
            ),
        )
        self.assertEqual(gold.release_decision, ReleaseDecision.CFBE_GOLD_V1)

    def test_unassessed_dimensions_fail_closed(self):
        task = SimulationTask("healthy", "mission-healthy", cost=0.1)
        run = DeterministicFaultSimulator.run("healthy", (task,))
        report = CFBEEvaluator.evaluate(run)
        by_name = {item.name: item for item in report.scorecard}

        self.assertFalse(by_name["verified_throughput"].assessed)
        self.assertFalse(by_name["privacy"].assessed)
        self.assertFalse(by_name["failure_recovery"].assessed)
        self.assertFalse(by_name["prompt_injection"].assessed)
        self.assertEqual(report.release_decision, ReleaseDecision.NO_GO)

    def test_json_report_is_canonical_hash_bound_and_deterministic(self):
        baseline = self._run("baseline", 1)
        candidate = self._run("candidate", 4)
        report = CFBEEvaluator.evaluate(candidate, baseline=baseline)

        first = json.loads(report.to_json())
        second = json.loads(report.to_json())
        self.assertEqual(first, second)
        supplied_digest = first.pop("report_sha256")
        canonical = json.dumps(first, sort_keys=True, separators=(",", ":"), allow_nan=False)
        expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(supplied_digest, expected_digest)
        self.assertEqual(first["empirical_scope"], "DETERMINISTIC_LOCAL_SIMULATION_ONLY")

    def test_input_order_does_not_change_simulation(self):
        forward = self._run("same-name", 4)
        reverse = self._run(
            "same-name",
            4,
            tasks=tuple(reversed(self.tasks)),
            injections=tuple(reversed(self.injections)),
        )
        self.assertEqual(forward, reverse)

    def test_unknown_fault_target_and_invalid_parallelism_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown task_id"):
            DeterministicFaultSimulator.run(
                "unknown",
                self.tasks,
                (FailureInjection("missing", FaultKind.CANCELLATION),),
            )
        with self.assertRaisesRegex(ValueError, "parallelism"):
            DeterministicFaultSimulator.run(
                "invalid",
                self.tasks,
                policy=SimulatorPolicy(parallelism=0),
            )

    def test_pairing_rejects_changed_fault_contract(self):
        baseline = self._run("baseline", 1)
        changed = self._run(
            "changed",
            4,
            injections=tuple(
                injection
                for injection in self.injections
                if injection.fault is not FaultKind.DECEPTIVE_WORKER
            ),
        )
        with self.assertRaisesRegex(ValueError, "identical task and fault contracts"):
            PairedMeasurement.from_runs(baseline, changed)

    def test_non_finite_task_data_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            DeterministicFaultSimulator.run(
                "invalid",
                (SimulationTask("bad", "mission-bad", cost=float("nan")),),
            )


if __name__ == "__main__":
    unittest.main()
