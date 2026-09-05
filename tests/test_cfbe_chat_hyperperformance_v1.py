import unittest

from federation.cfbe_chat_hyperperformance_v1 import (
    AdaptiveConcurrencyController,
    CacheRecord,
    ContextBudgeter,
    ContextItem,
    EffectClass,
    FreshResultCache,
    HyperperformancePlanner,
    OwnerEscalationState,
    PerformanceBudget,
    RouteProfile,
    RouteSelector,
    SpanObservation,
    TraceToRegression,
    WorkUnit,
    owner_interrupt_required,
)


class CFBEChatHyperperformanceV1Tests(unittest.TestCase):
    def route(self, route_id="direct", surface="drive", **kwargs):
        base = dict(
            route_id=route_id,
            surface=surface,
            available=True,
            fresh=True,
            direct=True,
            success_rate=0.99,
            semantic_readback_rate=0.99,
            p95_ms=800,
            unit_cost=0.01,
            circuit_open=False,
            proof_refs=(f"proof:{route_id}",),
        )
        base.update(kwargs)
        return RouteProfile(**base)

    def unit(self, unit_id="u1", **kwargs):
        base = dict(
            unit_id=unit_id,
            surface="drive",
            operation="READ",
            input_fingerprint=f"input:{unit_id}",
        )
        base.update(kwargs)
        return WorkUnit(**base)

    def test_route_selector_prefers_fast_reliable_direct_route(self):
        selector = RouteSelector(target_p95_ms=2000)
        decision = selector.choose(
            self.unit(),
            (
                self.route("slow", p95_ms=6000, success_rate=0.98),
                self.route("fast", p95_ms=600, success_rate=0.99),
            ),
        )
        self.assertEqual(decision.route_id, "fast")

    def test_stale_route_is_rejected(self):
        decision = RouteSelector().choose(self.unit(), (self.route(fresh=False),))
        self.assertEqual(decision.state, "NO_ELIGIBLE_ROUTE")

    def test_open_circuit_route_is_rejected(self):
        decision = RouteSelector().choose(self.unit(), (self.route(circuit_open=True),))
        self.assertEqual(decision.state, "NO_ELIGIBLE_ROUTE")

    def test_effect_route_requires_high_semantic_readback(self):
        unit = self.unit(effect_class=EffectClass.INTERNAL_WRITE)
        decision = RouteSelector().choose(unit, (self.route(semantic_readback_rate=0.80),))
        self.assertEqual(decision.state, "NO_ELIGIBLE_ROUTE")

    def test_external_effect_cannot_be_cached(self):
        with self.assertRaisesRegex(ValueError, "EXTERNAL_EFFECT_CANNOT_BE_RESULT_CACHED"):
            self.unit(effect_class=EffectClass.EXTERNAL_EFFECT).validate()

    def test_cache_hit_requires_freshness_match_and_proof(self):
        unit = self.unit(freshness_key="rev1")
        cache = FreshResultCache((CacheRecord(unit.semantic_key, "result:1", "proof:1", "rev1"),))
        self.assertEqual(cache.lookup(unit).result_ref, "result:1")
        stale = self.unit(freshness_key="rev2")
        self.assertIsNone(cache.lookup(stale))

    def test_planner_deduplicates_identical_safe_work(self):
        u1 = self.unit("u1", input_fingerprint="same")
        u2 = self.unit("u2", input_fingerprint="same")
        plan = HyperperformancePlanner(PerformanceBudget(max_parallel=4)).compile((u1, u2), (self.route(),))
        self.assertEqual(plan.deduplicated_units, 1)
        states = {p.unit.unit_id: p.state for p in plan.planned_units}
        self.assertIn("DEDUPLICATED", states.values())

    def test_planner_uses_cache_without_scheduling_unit(self):
        unit = self.unit("u1", freshness_key="rev1")
        cache = FreshResultCache((CacheRecord(unit.semantic_key, "result:cached", "proof:cache", "rev1"),))
        plan = HyperperformancePlanner(PerformanceBudget()).compile((unit,), (self.route(),), cache)
        self.assertEqual(plan.cache_hits, 1)
        self.assertEqual(plan.waves, ())

    def test_planner_parallelizes_independent_safe_units(self):
        units = tuple(self.unit(f"u{i}") for i in range(4))
        plan = HyperperformancePlanner(PerformanceBudget(max_parallel=4)).compile(units, (self.route(),))
        self.assertEqual(len(plan.waves), 1)
        self.assertEqual(len(plan.waves[0].unit_ids), 4)

    def test_planner_respects_dependencies(self):
        u1 = self.unit("u1")
        u2 = self.unit("u2", deps=("u1",))
        plan = HyperperformancePlanner(PerformanceBudget(max_parallel=8)).compile((u1, u2), (self.route(),))
        self.assertEqual(len(plan.waves), 2)
        self.assertEqual(plan.waves[0].unit_ids, ("u1",))
        self.assertEqual(plan.waves[1].unit_ids, ("u2",))

    def test_external_effect_is_a_serial_barrier(self):
        read = self.unit("read")
        effect = self.unit(
            "effect",
            operation="SEND",
            effect_class=EffectClass.EXTERNAL_EFFECT,
            cacheable=False,
        )
        plan = HyperperformancePlanner(PerformanceBudget(max_parallel=8)).compile((read, effect), (self.route(),))
        self.assertTrue(plan.waves[0].barrier)
        self.assertEqual(plan.waves[0].unit_ids, ("effect",))
        self.assertEqual(plan.waves[1].unit_ids, ("read",))

    def test_blocked_dependency_propagates_without_deadlock(self):
        blocked = self.unit("blocked", surface="missing")
        child = self.unit("child", deps=("blocked",))
        plan = HyperperformancePlanner(PerformanceBudget()).compile((blocked, child), (self.route(),))
        self.assertEqual(set(plan.blocked_units), {"blocked", "child"})

    def test_missing_dependency_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "MISSING_DEPENDENCY"):
            HyperperformancePlanner(PerformanceBudget()).compile((self.unit("u", deps=("ghost",)),), (self.route(),))

    def test_dependency_cycle_is_detected(self):
        u1 = self.unit("u1", deps=("u2",))
        u2 = self.unit("u2", deps=("u1",))
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_CYCLE_DETECTED"):
            HyperperformancePlanner(PerformanceBudget()).compile((u1, u2), (self.route(),))

    def test_adaptive_controller_increases_when_healthy(self):
        controller = AdaptiveConcurrencyController(PerformanceBudget(max_parallel=8, target_p95_ms=2000), initial=2)
        state = controller.observe((SpanObservation("s", "u", 500, True, True),))
        self.assertEqual(state.action, "ADDITIVE_INCREASE")
        self.assertEqual(state.concurrency, 3)

    def test_adaptive_controller_halves_on_latency_or_semantic_failure(self):
        controller = AdaptiveConcurrencyController(PerformanceBudget(max_parallel=8, target_p95_ms=1000), initial=8)
        state = controller.observe((SpanObservation("s", "u", 3000, True, False),))
        self.assertEqual(state.action, "MULTIPLICATIVE_DECREASE")
        self.assertEqual(state.concurrency, 4)

    def test_context_budgeter_prioritizes_proof_and_decisions(self):
        items = (
            ContextItem("proof", "ref:p", 200, 0.8, 0.8, proof_bearing=True),
            ContextItem("decision", "ref:d", 200, 0.8, 0.8, decision_bearing=True),
            ContextItem("noise", "ref:n", 600, 1.0, 1.0),
        )
        pack = ContextBudgeter().compile(items, 450)
        self.assertEqual(set(pack.selected_ids), {"proof", "decision"})
        self.assertIn("noise", pack.dropped_ids)

    def test_trace_to_regression_emits_semantic_and_owner_burden_classes(self):
        span = SpanObservation(
            "s1", "u1", 1000, True, False,
            avoidable_owner_interrupt=True,
            claim_mismatch=True,
        )
        out = TraceToRegression().compile((span,))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].severity, "P0")
        self.assertIn("SEMANTIC_READBACK_FAILURE", out[0].failure_classes)
        self.assertIn("AVOIDABLE_OWNER_INTERRUPT", out[0].failure_classes)
        self.assertIn("CLAIM_PROOF_MISMATCH", out[0].failure_classes)

    def test_trace_to_regression_ignores_clean_span(self):
        span = SpanObservation("s1", "u1", 100, True, True)
        self.assertEqual(TraceToRegression().compile((span,)), ())

    def test_owner_interrupt_suppressed_while_safe_recovery_exists(self):
        state = OwnerEscalationState(True, False, False, True, "Choose route")
        self.assertFalse(owner_interrupt_required(state))

    def test_owner_only_decision_requires_precise_request(self):
        state = OwnerEscalationState(True, True, False, False, "Approve irreversible action")
        self.assertTrue(owner_interrupt_required(state))
        vague = OwnerEscalationState(True, True, False, False, "")
        self.assertFalse(owner_interrupt_required(vague))

    def test_exhausted_recovery_escalates_precisely(self):
        state = OwnerEscalationState(True, False, True, False, "Choose between A and B")
        self.assertTrue(owner_interrupt_required(state))


if __name__ == "__main__":
    unittest.main()
