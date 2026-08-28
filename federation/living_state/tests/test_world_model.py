from __future__ import annotations

import unittest

from federation.living_state.world_model import (
    CausalEvidence, CausalStatus, ContextState, EdgeKind, EvolutionCandidate, EvolutionState,
    LearningClass, LivingWorldModel, MissionLease, NodeKind, PlannerCandidate, ProofMaturity,
    Provenance, RouteTelemetry, WorldEdge, WorldNode, learning_event, run_living_fabric_canary,
)

NOW = "2026-08-28T04:00:00+00:00"


def prov(source="s", proof="p", when=NOW, maturity=ProofMaturity.DETERMINISTIC_TESTED, ttl=3600, scope="GLOBAL", conf=0.8):
    return Provenance(source, proof, when, maturity, ttl, conf, matter_scope=scope)


class LivingWorldModelTests(unittest.TestCase):
    def test_event_chain_and_snapshot_are_deterministic(self):
        a = LivingWorldModel(); b = LivingWorldModel()
        node = WorldNode("system:A", NodeKind.SYSTEM, "A", "ACTIVE", {"x": 1}, prov())
        a.observe_node(node); b.observe_node(node)
        self.assertTrue(a.verify_event_chain()); self.assertTrue(b.verify_event_chain())
        self.assertEqual(a.snapshot(now=NOW)["snapshot_sha256"], b.snapshot(now=NOW)["snapshot_sha256"])

    def test_provider_proof_outranks_source_but_split_brain_visible(self):
        model = LivingWorldModel()
        model.observe_node(WorldNode("surface:X", NodeKind.SURFACE, "X", "READY", {}, prov(maturity=ProofMaturity.DETERMINISTIC_TESTED)))
        model.observe_node(WorldNode("surface:X", NodeKind.SURFACE, "X", "DOWN", {}, prov(source="provider", proof="pp", when="2026-08-28T03:59:00+00:00", maturity=ProofMaturity.PROVIDER_READBACK, conf=0.99)))
        estimate = model.state_estimate("surface:X", now=NOW)
        self.assertEqual(estimate.state, "DOWN"); self.assertTrue(estimate.split_brain)

    def test_stale_state_is_not_called_current(self):
        model = LivingWorldModel()
        model.observe_node(WorldNode("surface:X", NodeKind.SURFACE, "X", "READY", {}, prov(when="2026-08-27T00:00:00+00:00", ttl=60)))
        estimate = model.state_estimate("surface:X", now=NOW)
        self.assertFalse(estimate.fresh); self.assertTrue(estimate.state.startswith("STALE:"))

    def test_authority_expansion_fails(self):
        with self.assertRaises(ValueError):
            Provenance("s", "p", NOW, authority_ceiling="A2").validate()

    def test_cross_matter_edge_is_blocked(self):
        model = LivingWorldModel()
        model.observe_node(WorldNode("mission:A", NodeKind.MISSION, "A", "ACTIVE", {}, prov(scope="P1")))
        model.observe_node(WorldNode("mission:B", NodeKind.MISSION, "B", "ACTIVE", {}, prov(scope="P2")))
        with self.assertRaises(ValueError):
            model.observe_edge(WorldEdge("edge:A:B", "mission:A", "mission:B", EdgeKind.DEPENDS_ON, prov(scope="GLOBAL")))

    def test_correlation_cannot_be_promoted_to_cause(self):
        model = LivingWorldModel()
        model.observe_node(WorldNode("system:A", NodeKind.SYSTEM, "A", "ACTIVE", {}, prov()))
        model.observe_node(WorldNode("system:B", NodeKind.SYSTEM, "B", "ACTIVE", {}, prov()))
        with self.assertRaises(ValueError):
            model.observe_edge(WorldEdge("edge:cause", "system:A", "system:B", EdgeKind.CAUSES, prov(), causal_status=CausalStatus.CANDIDATE, causal_evidence=CausalEvidence(temporal_order=True, evidence_refs=("p",))))

    def test_causal_edge_requires_falsifier_and_intervention_or_mechanism(self):
        model = LivingWorldModel()
        model.observe_node(WorldNode("system:A", NodeKind.SYSTEM, "A", "ACTIVE", {}, prov()))
        model.observe_node(WorldNode("system:B", NodeKind.SYSTEM, "B", "ACTIVE", {}, prov()))
        edge = WorldEdge("edge:cause", "system:A", "system:B", EdgeKind.CAUSES, prov(maturity=ProofMaturity.RECEIPT_VERIFIED), 0.9, CausalStatus.VERIFIED, CausalEvidence(True, True, False, True, False, ("p",)))
        model.observe_edge(edge)
        self.assertEqual(model._edges["edge:cause"].causal_status, CausalStatus.VERIFIED)

    def test_thin_route_evidence_is_shrunk_toward_neutral(self):
        model = LivingWorldModel()
        model.observe_route_telemetry(RouteTelemetry("r", "m", NOW, True, 10, .1, .1, 1, 1, .1, ("fd",), "p"))
        estimate = model.route_estimates(min_samples=5)[0]
        self.assertFalse(estimate.measured)
        self.assertLess(estimate.reliability, 0.67)
        self.assertGreater(estimate.reliability, 0.5)

    def test_champion_shadow_prefers_failure_domain_diversity(self):
        model = LivingWorldModel()
        for route, domain, success in (("A", "FD1", True), ("B", "FD2", True), ("C", "FD1", True)):
            for idx in range(3):
                model.observe_route_telemetry(RouteTelemetry(route, "m", f"2026-08-28T03:5{idx}:00+00:00", success, 10+idx, .1, .1, .9, .9, .1, (domain,), f"p-{route}-{idx}"))
        portfolio = model.route_portfolio(max_shadows=1)
        self.assertEqual(portfolio.shadows, ("B",))

    def test_hidden_spof_detected(self):
        model = LivingWorldModel()
        for route in ("A", "B"):
            model.observe_route_telemetry(RouteTelemetry(route, "m", NOW, True, 1, 0, 0, 1, 1, 0, ("COMMON",), f"p-{route}"))
        self.assertEqual(model.hidden_spofs(("A", "B")), ("COMMON",))

    def test_context_protected_compaction_never_drops_adverse_or_blocker(self):
        c = ContextState("c", 800, 1000, .4, 20, ("fact",), ("adverse",), ("contradiction",), ("gap",), ("blocker",), ("decision",), ("source",))
        self.assertEqual(c.action(), "PROTECTED_COMPACTION")
        self.assertIn("adverse", c.protected_items); self.assertIn("blocker", c.protected_items)

    def test_context_handoff_at_high_pressure(self):
        c = ContextState("c", 950, 1000, 0, 0)
        self.assertEqual(c.action(), "CHECKPOINT_AND_HANDOFF")

    def test_stale_effectful_lease_fails_closed(self):
        model = LivingWorldModel()
        lease = MissionLease("m", "a"*40, 1, ("x",), "2026-08-28T03:00:00+00:00", "2026-08-28T05:00:00+00:00", True)
        result = model.arbitrate_mission_write(lease=lease, now=NOW, current_main_sha="b"*40, current_main_changed_paths=("other",))
        self.assertFalse(result.allowed); self.assertEqual(result.reason, "STALE_EFFECTFUL_LEASE")

    def test_stale_non_effectful_disjoint_requests_fast_reconvergence(self):
        model = LivingWorldModel()
        lease = MissionLease("m", "a"*40, 1, ("x",), "2026-08-28T03:00:00+00:00", "2026-08-28T05:00:00+00:00", False)
        result = model.arbitrate_mission_write(lease=lease, now=NOW, current_main_sha="b"*40, current_main_changed_paths=("other",))
        self.assertEqual(result.disposition, "FAST_RECONVERGE")

    def test_overlapping_workstream_blocks_even_with_fresh_main(self):
        model = LivingWorldModel()
        lease = MissionLease("m", "a"*40, 1, ("federation/living",), "2026-08-28T03:00:00+00:00", "2026-08-28T05:00:00+00:00")
        result = model.arbitrate_mission_write(lease=lease, now=NOW, current_main_sha="a"*40, concurrent_workstream_paths=("federation/living/file.py",))
        self.assertFalse(result.allowed); self.assertEqual(result.reason, "ACTIVE_WORKSTREAM_OVERLAP")

    def test_owner_correction_is_learning_not_personality(self):
        event = learning_event(learning_class=LearningClass.OWNER_CORRECTION, fingerprint="STALE_INFO", observed_at=NOW, matter_scope="GLOBAL", route_id="r", signal="correction", diagnosis="freshness gate failed", hypothesis="hard gate fixes", test_ref="t", result_ref="r", proof_refs=("p",), recurrence=1, independent_evidence=True)
        self.assertEqual(event.escalation, "STRENGTHEN_CONTROL")

    def test_recurrence_escalates_to_scientist_then_redesign(self):
        kwargs = dict(learning_class=LearningClass.FAILURE, fingerprint="SAMEFAIL", observed_at=NOW, matter_scope="GLOBAL", route_id="r", signal="s", diagnosis="d", hypothesis="h", test_ref="t", result_ref="r", proof_refs=("p",), independent_evidence=True)
        self.assertEqual(learning_event(recurrence=2, **kwargs).escalation, "OMEGA_SCIENTIST_REVIEW")
        self.assertEqual(learning_event(recurrence=3, **kwargs).escalation, "REDESIGN_OR_ROLLBACK")

    def test_matter_bound_learning_cannot_go_global(self):
        event = learning_event(learning_class=LearningClass.FAILURE, fingerprint="FAILXX", observed_at=NOW, matter_scope="CASE1", route_id="r", signal="s", diagnosis="d", hypothesis="h", test_ref="t", result_ref="r", proof_refs=("p",), recurrence=2, independent_evidence=True)
        self.assertFalse(event.global_promotion_allowed)

    def test_planner_prefers_information_and_mission_delta(self):
        model = LivingWorldModel()
        d = model.plan((PlannerCandidate("probe", .5, .9, .8, 1, .1, .1, 0, proof_ref="p"), PlannerCandidate("low", .2, .1, .1, 1, .1, .1, 0, proof_ref="q")))
        self.assertEqual(d.selected_action_id, "probe")

    def test_living_fabric_never_executes_effect_candidate(self):
        model = LivingWorldModel()
        d = model.plan((PlannerCandidate("deploy", 1, .1, .1, .1, .2, .2, .1, external_effect=True, proof_ref="p"),))
        self.assertEqual(d.disposition, "HOLD_FOR_EFFECT_ADMISSION"); self.assertEqual(model.external_effects, 0)

    def test_evolution_requires_all_proof_gates(self):
        weak = EvolutionCandidate("c", "role", True, True, False, True, .5, .9, 5, ("p",))
        self.assertEqual(weak.state, EvolutionState.SHADOW)

    def test_evolution_candidate_with_full_proof_is_only_eligible(self):
        strong = EvolutionCandidate("c", "role", True, True, True, True, .5, .9, 5, ("p",))
        self.assertEqual(strong.state, EvolutionState.PROMOTION_ELIGIBLE)

    def test_homeostasis_unmeasured_when_empty(self):
        self.assertEqual(LivingWorldModel().homeostasis(now=NOW)["state"], "UNMEASURED")

    def test_benchmark_debt_is_freshness_based(self):
        model = LivingWorldModel(); model.observe_benchmark("c", "2026-08-01T00:00:00+00:00", "p")
        self.assertEqual(model.debt_report(now=NOW)["benchmark_debt"], 1)

    def test_reflexes_do_not_have_external_effects(self):
        model = LivingWorldModel(); model.observe_context(ContextState("c", 950, 1000, 0, 0))
        self.assertTrue(model.reflexes(now=NOW)); self.assertTrue(all(not x["external_effect"] for x in model.reflexes(now=NOW)))

    def test_capability_twin_adapter(self):
        model = LivingWorldModel()
        model.ingest_capability_twin({"system_id":"X","runtime_state":"RUNTIME_VERIFIED","semantic_state":"RUNTIME_SEMANTIC_VERIFIED","readback_state":"RUNTIME_READBACK","proof_ref":"p","source_ref":"s","observed_at":NOW,"ttl_seconds":3600,"confidence":.88,"authority_ceiling":"A1_INTERNAL"})
        self.assertIn("capability:X", model.current_nodes())

    def test_awareness_adapter(self):
        model = LivingWorldModel(); ids = model.ingest_awareness_result({"receipt_sha256":"r","routes":({"alias":"G","provider":"Google","state":"READY"},),"opportunities":()}, observed_at=NOW)
        self.assertEqual(ids, ("route:G",))

    def test_omega4_adapter_preserves_project_matter_scope(self):
        model = LivingWorldModel(); model.ingest_omega4_snapshot(missions=({"mission_id":"M","project_id":"P","objective":"O","current_stage":"ACTIVE"},), observed_at=NOW)
        self.assertEqual(model.current_nodes()["mission:M"].provenance.matter_scope, "P")

    def test_canary(self):
        result = run_living_fabric_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 26)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)
        self.assertFalse(result["truth_boundary"]["continuous_unattended_runtime_claimed"])


if __name__ == "__main__":
    unittest.main()
