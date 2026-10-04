import unittest

from federation.cfbe_chat_hyperperformance_v2 import (
    ActionKind,
    AlgorithmObservation,
    AlgorithmPerformanceLedger,
    AlgorithmStage,
    BulkheadProfile,
    CapabilitySnapshot,
    CapabilitySnapshotCache,
    CriticalPathBulkheadPlanner,
    DirectiveDuplicateGuard,
    ExecutionArbiter,
    ExecutionState,
    FailureEvolutionEngine,
    FailureObservation,
    HedgeRequest,
    MutationFenceBook,
    OwnerAttentionBudget,
    OwnerAttentionGovernor,
    OutputClass,
    ProgressSnapshot,
    RetryBudget,
    SchedulableUnit,
    SingleFlightLeaseBook,
    TailHedgePolicy,
    TraceSpanV2,
    TrajectoryEvaluator,
    monotonic_progress,
)


class CFBEChatHyperperformanceV2Tests(unittest.TestCase):
    def test_actionable_provider_work_blocks_report(self):
        state = ExecutionState("m", actionable_provider_steps=("CANVA_EDIT",))
        d = ExecutionArbiter().decide(state, ActionKind.REPORT)
        self.assertFalse(d.allowed)
        self.assertEqual(d.required_action, "CANVA_EDIT")
        self.assertIn("EXECUTABLE_PROVIDER_WORK_PRECEDES_REPORT", d.reasons)

    def test_checkpoint_loop_is_blocked_when_provider_work_exists(self):
        state = ExecutionState("m", actionable_provider_steps=("DRIVE_WRITE",), local_checkpoint_count=3)
        d = ExecutionArbiter().decide(state, ActionKind.CHECKPOINT)
        self.assertFalse(d.allowed)
        self.assertIn("CHECKPOINT_LOOP_BLOCKED", d.reasons)

    def test_owner_gate_requires_precise_request(self):
        state = ExecutionState("m", owner_gate_required=True, owner_gate_request="")
        d = ExecutionArbiter().decide(state, ActionKind.OWNER_GATE)
        self.assertFalse(d.allowed)
        self.assertEqual(d.required_action, "REPAIR_OWNER_GATE_REQUEST")

    def test_duplicate_directive_guard_blocks_same_prompt_without_new_evidence(self):
        g = DirectiveDuplicateGuard(0.75)
        prev = "Execute Canva design edit, preview all pages, ask approval, commit and read back."
        new = "Execute Canva design edit; preview all pages; ask approval; commit and read back."
        d = g.compare(prev, new, new_execution_evidence=False)
        self.assertTrue(d.duplicate)
        self.assertFalse(d.allowed)

    def test_duplicate_directive_allowed_after_new_execution_evidence(self):
        g = DirectiveDuplicateGuard(0.75)
        d = g.compare("execute provider then read back", "execute provider and read back", new_execution_evidence=True)
        self.assertTrue(d.allowed)

    def test_negative_capability_claim_requires_fresh_snapshot(self):
        c = CapabilitySnapshotCache(positive_ttl_epochs=3, negative_ttl_epochs=1)
        c.put(CapabilitySnapshot("canva", "edit", False, "proof:no-tool", 4))
        self.assertTrue(c.may_claim_unavailable("canva", "edit", current_epoch=5))
        self.assertFalse(c.may_claim_unavailable("canva", "edit", current_epoch=6))

    def test_newer_capability_snapshot_wins(self):
        c = CapabilitySnapshotCache()
        c.put(CapabilitySnapshot("canva", "edit", False, "old", 1))
        c.put(CapabilitySnapshot("canva", "edit", True, "new", 2))
        self.assertTrue(c.get("canva", "edit", current_epoch=2).available)

    def test_repeated_failure_forces_alternate_route(self):
        f = FailureObservation("TOOL_SELECTION", "canva", "EDIT", "route-a", "MISSING_TOOL", "proof:2")
        h = FailureObservation("TOOL_SELECTION", "canva", "EDIT", "route-a", "MISSING_TOOL", "proof:1")
        d = FailureEvolutionEngine().decide(f, (h,), ("route-a", "route-b"))
        self.assertEqual(d.action, "SWITCH_ROUTE")
        self.assertEqual(d.selected_route, "route-b")

    def test_third_identical_failure_triggers_architecture_remediation(self):
        base = [
            FailureObservation("REPETITION", "chat", "N", "same", "NO_PROGRESS", "p1"),
            FailureObservation("REPETITION", "chat", "N", "same", "NO_PROGRESS", "p2"),
        ]
        current = FailureObservation("REPETITION", "chat", "N", "same", "NO_PROGRESS", "p3")
        d = FailureEvolutionEngine().decide(current, base, ("same",))
        self.assertTrue(d.architecture_remediation)
        self.assertEqual(d.action, "ARCHITECTURE_REMEDIATION")

    def test_singleflight_coalesces_concurrent_duplicates(self):
        b = SingleFlightLeaseBook()
        leader = b.acquire("k", "a", now_tick=1, ttl_ticks=5)
        follower = b.acquire("k", "b", now_tick=2, ttl_ticks=5)
        self.assertEqual(leader.state, "LEADER")
        self.assertEqual(follower.state, "FOLLOWER")
        self.assertEqual(follower.lease.owner_id, "a")

    def test_singleflight_stale_lease_can_be_replaced(self):
        b = SingleFlightLeaseBook()
        first = b.acquire("k", "a", now_tick=1, ttl_ticks=2)
        second = b.acquire("k", "b", now_tick=3, ttl_ticks=2)
        self.assertEqual(second.state, "STALE_REPLACED")
        self.assertGreater(second.lease.generation, first.lease.generation)

    def test_mutation_fence_rejects_stale_worker(self):
        b = MutationFenceBook()
        old = b.acquire("design:1", "w1")
        new = b.acquire("design:1", "w2")
        self.assertFalse(b.can_commit(old))
        self.assertTrue(b.can_commit(new))
        with self.assertRaisesRegex(ValueError, "STALE_MUTATION_FENCE"):
            b.commit(old)

    def test_critical_path_ranker_prioritizes_long_downstream_chain(self):
        units = (
            SchedulableUnit("a", "drive", 100, deps=()),
            SchedulableUnit("b", "drive", 100, deps=("a",)),
            SchedulableUnit("c", "drive", 100, deps=("b",)),
            SchedulableUnit("x", "drive", 10, priority=99),
        )
        waves = CriticalPathBulkheadPlanner().plan(
            units, (BulkheadProfile("drive", 1),), global_max_parallel=1
        )
        self.assertEqual(waves[0].unit_ids, ("a",))

    def test_bulkhead_limits_per_surface_concurrency(self):
        units = (
            SchedulableUnit("d1", "drive", 100),
            SchedulableUnit("d2", "drive", 100),
            SchedulableUnit("g1", "github", 100),
        )
        waves = CriticalPathBulkheadPlanner().plan(
            units,
            (BulkheadProfile("drive", 1), BulkheadProfile("github", 2)),
            global_max_parallel=3,
        )
        self.assertEqual(dict(waves[0].surface_counts)["drive"], 1)
        self.assertEqual(dict(waves[0].surface_counts)["github"], 1)

    def test_same_mutation_key_not_in_same_wave(self):
        units = (
            SchedulableUnit("m1", "canva", 100, mutation_key="design:1"),
            SchedulableUnit("m2", "canva", 100, mutation_key="design:1"),
        )
        waves = CriticalPathBulkheadPlanner().plan(
            units, (BulkheadProfile("canva", 2),), global_max_parallel=2
        )
        self.assertEqual(len(waves[0].unit_ids), 1)
        self.assertEqual(len(waves), 2)

    def test_hedging_requires_safe_read_and_budget(self):
        p = TailHedgePolicy(delay_fraction_of_p95=0.8)
        req = HedgeRequest(True, True, 900, 1000, ("alt",))
        d = p.decide(req, RetryBudget())
        self.assertTrue(d.allowed)
        self.assertEqual(d.route_id, "alt")

    def test_hedging_denied_for_write(self):
        d = TailHedgePolicy().decide(
            HedgeRequest(False, True, 9999, 100, ("alt",)), RetryBudget()
        )
        self.assertFalse(d.allowed)

    def test_retry_budget_throttles_hedges(self):
        budget = RetryBudget(max_tokens=10, token_ratio=0.1, tokens=5)
        req = HedgeRequest(True, True, 9999, 100, ("alt",))
        self.assertFalse(TailHedgePolicy().decide(req, budget).allowed)

    def test_trajectory_detects_report_checkpoint_no_progress_loop(self):
        spans = (
            TraceSpanV2("t", "1", "", ActionKind.REPORT, 10, True),
            TraceSpanV2("t", "2", "1", ActionKind.CHECKPOINT, 10, True),
            TraceSpanV2("t", "3", "2", ActionKind.REPORT, 10, True),
        )
        score = TrajectoryEvaluator(no_progress_run=2).evaluate(spans)
        self.assertGreaterEqual(score.no_progress_cycles, 1)
        self.assertFalse(score.healthy)

    def test_trajectory_is_healthy_when_provider_progress_breaks_narrative_run(self):
        spans = (
            TraceSpanV2("t", "1", "", ActionKind.REPORT, 10, True),
            TraceSpanV2("t", "2", "1", ActionKind.PROVIDER_WRITE, 100, True, provider_progress_delta=1),
            TraceSpanV2("t", "3", "2", ActionKind.REPORT, 10, True, evidence_delta=1),
        )
        score = TrajectoryEvaluator(no_progress_run=2).evaluate(spans)
        self.assertEqual(score.no_progress_cycles, 0)
        self.assertTrue(score.healthy)

    def test_owner_attention_governor_suppresses_internal_chatter(self):
        g = OwnerAttentionGovernor()
        b = OwnerAttentionBudget(max_internal_progress_messages=0)
        self.assertFalse(g.allow(OutputClass.INTERNAL_PROGRESS, internal_progress_emitted=0, owner_gates_emitted=0, budget=b))
        self.assertTrue(g.allow(OutputClass.MILESTONE, internal_progress_emitted=99, owner_gates_emitted=0, budget=b))

    def test_algorithm_ledger_promotes_only_with_repeated_success(self):
        obs = [
            AlgorithmObservation("alg", True, 100, 0.95, 0, current_mission=(i == 0))
            for i in range(5)
        ]
        s = AlgorithmPerformanceLedger().summarize(
            "alg", obs, specified=True, implemented=True, deterministic_tests_passed=5
        )
        self.assertEqual(s.stage, AlgorithmStage.A6_DEFAULT_CANDIDATE)

    def test_algorithm_regression_blocks_default_promotion(self):
        obs = [
            AlgorithmObservation("alg", True, 100, 0.95, 0, regression=(i == 4), current_mission=(i == 0))
            for i in range(5)
        ]
        s = AlgorithmPerformanceLedger().summarize(
            "alg", obs, deterministic_tests_passed=5
        )
        self.assertEqual(s.stage, AlgorithmStage.A5_REPEATED_REUSE)

    def test_monotonic_progress_requires_measurable_advance(self):
        a = ProgressSnapshot(provider_actions=1)
        self.assertFalse(monotonic_progress(a, a))
        b = ProgressSnapshot(provider_actions=1, evidence_refs=1)
        self.assertTrue(monotonic_progress(a, b))


if __name__ == "__main__":
    unittest.main()
