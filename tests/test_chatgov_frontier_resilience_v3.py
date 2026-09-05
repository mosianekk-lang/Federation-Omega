import unittest

from bubbles.chat_governor_omega3.frontier_resilience_v3 import (
    ChaosCourtCompiler,
    DeadlineBudgetCompiler,
    DeadlineStage,
    GracefulDegradationGovernor,
    PowerOfTwoLoadSelector,
    ProviderHealthSample,
    ProviderOutlierGovernor,
    ReplicaLoad,
    ShuffleShardPlanner,
    frontier_resilience_v3_receipt,
)


class PowerOfTwoTests(unittest.TestCase):
    def test_only_qualified_healthy_non_ejected_replicas_are_sampled(self):
        selector = PowerOfTwoLoadSelector(choice_count=3)
        decision = selector.choose(
            request_key="mission-1",
            replicas=[
                ReplicaLoad("healthy-a", 9),
                ReplicaLoad("healthy-b", 1),
                ReplicaLoad("bad", 0, healthy=False),
                ReplicaLoad("unqualified", 0, qualified=False),
                ReplicaLoad("ejected", 0, ejected=True),
            ],
        )
        self.assertEqual({"healthy-a", "healthy-b"}, set(decision.sampled))
        self.assertEqual("healthy-b", decision.selected)

    def test_weight_can_legitimately_offset_active_request_count(self):
        selector = PowerOfTwoLoadSelector(choice_count=2, active_request_bias=1.0)
        decision = selector.choose(
            request_key="x",
            replicas=[ReplicaLoad("small", 1, weight=1.0), ReplicaLoad("large", 3, weight=10.0)],
        )
        self.assertEqual("large", decision.selected)


class OutlierTests(unittest.TestCase):
    def test_consecutive_failures_recommend_ejection_but_cap_blast_radius(self):
        governor = ProviderOutlierGovernor(
            min_request_volume=10,
            consecutive_gateway_failure_threshold=3,
            max_ejection_fraction=0.5,
            min_healthy_providers=1,
        )
        actions = governor.evaluate(
            [
                ProviderHealthSample("a", 100, 100, consecutive_gateway_failures=5),
                ProviderHealthSample("b", 90, 100, consecutive_gateway_failures=4),
                ProviderHealthSample("c", 99, 100),
            ]
        )
        by_id = {row.provider_id: row for row in actions}
        self.assertEqual(1, sum(row.action == "EJECT_RECOMMENDED" for row in actions))
        self.assertEqual("KEEP", by_id["c"].action)
        self.assertIn(by_id["a"].action, {"EJECT_RECOMMENDED", "KEEP_BLAST_RADIUS_CAP"})
        self.assertIn(by_id["b"].action, {"EJECT_RECOMMENDED", "KEEP_BLAST_RADIUS_CAP"})

    def test_recovery_requires_probe_not_immediate_reinstatement(self):
        governor = ProviderOutlierGovernor(min_request_volume=10)
        action = governor.evaluate([ProviderHealthSample("a", 10, 10, currently_ejected=True)])[0]
        self.assertEqual("PROBE_REINSTATE", action.action)

    def test_low_volume_success_rate_does_not_trigger_statistical_ejection(self):
        governor = ProviderOutlierGovernor(min_request_volume=100)
        actions = governor.evaluate(
            [ProviderHealthSample("a", 1, 2), ProviderHealthSample("b", 100, 100)]
        )
        self.assertTrue(all(row.action == "KEEP" for row in actions))


class ShuffleShardTests(unittest.TestCase):
    def test_same_flow_maps_to_same_small_shard(self):
        planner = ShuffleShardPlanner(queue_count=32, shard_size=4, salt="estate")
        first = planner.plan("flow-A")
        second = planner.plan("flow-A")
        self.assertEqual(first, second)
        self.assertEqual(4, len(first.queue_indices))
        self.assertEqual(4, len(set(first.queue_indices)))

    def test_distinct_flows_need_not_share_whole_shard(self):
        planner = ShuffleShardPlanner(queue_count=64, shard_size=4, salt="estate")
        a = set(planner.plan("flow-A").queue_indices)
        b = set(planner.plan("flow-B").queue_indices)
        self.assertNotEqual(a, b)


class DeadlineTests(unittest.TestCase):
    def test_proof_and_finalization_are_reserved_before_optional_work(self):
        compiler = DeadlineBudgetCompiler()
        plan = compiler.compile(
            total_budget_ms=1000,
            proof_reserve_ms=200,
            final_reserve_ms=100,
            stages=[
                DeadlineStage("required", 400, True, 1.0),
                DeadlineStage("high", 200, False, 1.0),
                DeadlineStage("low", 300, False, 0.1),
            ],
        )
        self.assertEqual("DEADLINE_TRIMMED", plan.mode)
        self.assertEqual(("low",), plan.omitted_optional)
        self.assertIn("required", {row.stage_id for row in plan.selected})
        self.assertIn("high", {row.stage_id for row in plan.selected})
        self.assertEqual(200, plan.proof_reserve_ms)

    def test_impossible_required_path_holds_instead_of_stealing_proof_budget(self):
        plan = DeadlineBudgetCompiler().compile(
            total_budget_ms=500,
            proof_reserve_ms=200,
            final_reserve_ms=100,
            stages=[DeadlineStage("must", 300, True)],
        )
        self.assertEqual("HOLD_UNSATISFIABLE", plan.mode)
        self.assertEqual((), plan.selected)


class DegradationTests(unittest.TestCase):
    def test_survival_mode_keeps_proof_and_policy(self):
        decision = GracefulDegradationGovernor().decide(
            queue_utilization=1.3,
            p95_latency_ratio=1.2,
            error_rate=0.15,
        )
        self.assertEqual("SURVIVAL", decision.mode)
        self.assertIn("policy_gate", decision.allowed_features)
        self.assertIn("proof_readback", decision.allowed_features)
        self.assertIn("secondary_research", decision.disabled_features)
        self.assertIn("verbose_progress", decision.disabled_features)

    def test_normal_pressure_keeps_full_service(self):
        decision = GracefulDegradationGovernor().decide(
            queue_utilization=0.2,
            p95_latency_ratio=0.5,
            error_rate=0.01,
        )
        self.assertEqual("FULL_SERVICE", decision.mode)
        self.assertEqual((), decision.disabled_features)


class ChaosCourtTests(unittest.TestCase):
    def test_read_only_court_compiles_dependency_and_mission_faults_without_authority(self):
        court = ChaosCourtCompiler().compile(
            mission_class="research",
            dependencies=["github", "web"],
            effectful=False,
        )
        faults = {row.fault for row in court.scenarios}
        self.assertIn("TIMEOUT", faults)
        self.assertIn("WORKER_CRASH_AFTER_CHECKPOINT", faults)
        self.assertIn("DUPLICATE_DELIVERY", faults)
        self.assertFalse(any(row.sandbox_required for row in court.scenarios))
        self.assertFalse(court.provider_effect_authorized)

    def test_effectful_court_requires_sandbox_and_effect_uncertainty_cases(self):
        court = ChaosCourtCompiler().compile(
            mission_class="provider-effect",
            dependencies=["provider"],
            effectful=True,
        )
        faults = {row.fault for row in court.scenarios}
        self.assertIn("PROVIDER_READBACK_MISMATCH", faults)
        self.assertIn("EFFECT_UNCERTAIN_AFTER_DISPATCH", faults)
        self.assertTrue(all(row.sandbox_required for row in court.scenarios))


class ReceiptTests(unittest.TestCase):
    def test_resilience_receipt_does_not_grant_effect_authority(self):
        receipt = frontier_resilience_v3_receipt()
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.fault_injection_authorized)
        self.assertFalse(receipt.route_ejection_authorized)
        self.assertIn("DETERMINISTIC_UAS_CHAOS_COURT_COMPILATION", receipt.capabilities)


if __name__ == "__main__":
    unittest.main()
