import unittest

from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    AutonomicMissionFabric,
    CounterfactualOption,
    CounterfactualPlanner,
    FailureForecast,
    FailureHorizon,
    GenomeLibrary,
    MissionGenome,
    MissionStateVector,
    MissionSwarmPlanner,
    MonotonicClosureGate,
    ProofDirectedScheduler,
    SwarmRole,
)


class AutonomicFabricTests(unittest.TestCase):
    def action(self, action_id="A", **overrides):
        body = dict(
            action_id=action_id,
            objective="Increase verified closure",
            closure_leverage=0.8,
            information_gain=0.7,
            success_probability=0.9,
            reversibility=0.9,
            cost=0.1,
            risk=0.1,
            latency=0.1,
        )
        body.update(overrides)
        return ActionCandidate(**body)

    def test_scheduler_prefers_closure_information_and_reversibility(self):
        scheduler = ProofDirectedScheduler()
        strong = self.action("strong")
        weak = self.action("weak", closure_leverage=0.3, information_gain=0.2, reversibility=0.4)
        ranked = scheduler.rank((weak, strong))
        self.assertEqual(ranked[0].action.action_id, "strong")

    def test_scheduler_serializes_shared_state(self):
        scheduler = ProofDirectedScheduler()
        a = self.action("a", shared_state_key="github-main", unlock_count=4)
        b = self.action("b", shared_state_key="github-main")
        c = self.action("c")
        wave = scheduler.ready_wave((a, b, c), max_parallel=3)
        ids = {item.action.action_id for item in wave}
        self.assertIn("c", ids)
        self.assertEqual(len({"a", "b"} & ids), 1)

    def test_external_effect_is_held_without_authority(self):
        scheduler = ProofDirectedScheduler()
        external = self.action("external", external_effect=True, authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT)
        ranked = scheduler.rank((external,))
        self.assertEqual(ranked[0].hold_reason, "AUTHORITY_CEILING_EXCEEDED")
        self.assertEqual(scheduler.ready_wave((external,)), ())

    def test_monotonic_gate_accepts_progress_and_rejects_regression(self):
        gate = MonotonicClosureGate()
        before = MissionStateVector(0.2, 0.2, 0.8, 0.5, 0.3)
        after = MissionStateVector(0.3, 0.4, 0.8, 0.5, 0.3)
        self.assertTrue(gate.evaluate(before, after).accepted)
        regressed = MissionStateVector(0.3, 0.4, 0.7, 0.5, 0.3)
        self.assertFalse(gate.evaluate(after, regressed).accepted)

    def test_monotonic_gate_rejects_noop(self):
        gate = MonotonicClosureGate()
        state = MissionStateVector(0.2, 0.2, 0.8, 0.5, 0.3)
        result = gate.evaluate(state, state)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "NO_MEASURABLE_PROGRESS")

    def test_counterfactual_planner_rewards_option_value_but_costs_risk(self):
        planner = CounterfactualPlanner()
        build_capability = CounterfactualOption(
            "build",
            "build shared capability",
            MissionStateVector(0.2, 0.5, 0.3, 0.6, 0.9),
            success_probability=0.9,
            option_value=0.5,
            cost=0.2,
            risk=0.1,
            latency=0.2,
            evidence_strength=0.8,
        )
        local_patch = CounterfactualOption(
            "patch",
            "local patch",
            MissionStateVector(0.4, 0.2, 0.1, 0.2, 0.1),
            success_probability=0.9,
            option_value=0.0,
            cost=0.2,
            risk=0.1,
            latency=0.2,
            evidence_strength=0.8,
        )
        self.assertEqual(planner.best((local_patch, build_capability)).option_id, "build")

    def test_failure_horizon_prioritizes_high_impact_preemptable_risk(self):
        horizon = FailureHorizon()
        high = FailureForecast("high", "drift", 0.8, 0.9, 0.9, 0.9, 0.1, "reanchor", "fallback")
        low = FailureForecast("low", "noise", 0.2, 0.2, 0.5, 0.5, 1.0, "observe", "fallback")
        ranked = horizon.rank((low, high))
        self.assertEqual(ranked[0].fingerprint, "high")
        self.assertIn(high, horizon.preempt((low, high), threshold=0.1))

    def test_genome_library_matches_similar_missions(self):
        prior = MissionGenome.create(
            objective_class="source admission convergence",
            invariants=("proof-before-claim",),
            proof_axes=("source", "rollback"),
            required_capabilities=("github", "airlock"),
            failure_fingerprints=("stale-base",),
            recovery_routes=("reanchor",),
        )
        target = MissionGenome.create(
            objective_class="source convergence admission",
            invariants=("proof-before-claim",),
            proof_axes=("source", "rollback"),
            required_capabilities=("github", "airlock"),
            failure_fingerprints=("stale-base",),
        )
        library = GenomeLibrary((prior,))
        matches = library.match(target)
        self.assertEqual(matches[0][0].pattern_id, prior.pattern_id)
        self.assertGreater(matches[0][1], 0.75)

    def test_swarm_has_independent_witness_and_no_self_certification(self):
        cells = MissionSwarmPlanner().plan(mission_id="M1", objective="Close mission", required_capabilities=("github",))
        self.assertEqual(len(cells), 7)
        witness = next(item for item in cells if item.role == SwarmRole.WITNESS)
        builder = next(item for item in cells if item.role == SwarmRole.BUILDER)
        self.assertEqual(witness.independence_domain, "INDEPENDENT_VERIFICATION")
        self.assertNotEqual(witness.independence_domain, builder.independence_domain)
        self.assertTrue(all(not item.may_self_certify for item in cells))

    def test_autonomic_plan_is_deterministic_and_effect_free(self):
        genome = MissionGenome.create(
            objective_class="mce source admission",
            invariants=("proof-before-claim",),
            proof_axes=("source",),
            required_capabilities=("github",),
        )
        library = GenomeLibrary((genome,))
        fabric = AutonomicMissionFabric(genome_library=library)
        actions = (
            self.action("A"),
            self.action("B", external_effect=True, authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT),
        )
        plan1 = fabric.plan(mission_id="M1", objective="Admit MCE", actions=actions, genome=genome)
        plan2 = fabric.plan(mission_id="M1", objective="Admit MCE", actions=actions, genome=genome)
        self.assertEqual(plan1.plan_sha256, plan2.plan_sha256)
        self.assertEqual([item.action.action_id for item in plan1.selected_wave], ["A"])


if __name__ == "__main__":
    unittest.main()
