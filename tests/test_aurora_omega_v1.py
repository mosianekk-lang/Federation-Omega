import unittest

from federation.aurora_omega_v1 import (
    AgentEvent,
    AppreciationFinding,
    AuroraOmegaAgent,
    Evidence,
    Lens,
    MissionPhase,
    RouteCandidate,
    SpecialistRole,
    TerminalEvent,
    ToolDescriptor,
)


class AuroraOmegaV1Test(unittest.TestCase):
    def setUp(self):
        self.agent = AuroraOmegaAgent()

    def mission(self, lens=Lens.BALANCED):
        return self.agent.new_mission(
            "M-AURORA-1",
            "Understand, build, verify, and learn without diluting the objective",
            ("built", "verified"),
            lens=lens,
        )

    def test_genius_appreciation_gate_prevents_reductive_critique(self):
        state = self.mission(Lens.GENIUS_APPRECIATION)
        self.assertFalse(self.agent.can_enter_technical_critique(state))
        self.assertEqual(MissionPhase.APPRECIATE, state.phase)

    def test_genius_appreciation_gate_passes_after_originality_synthesis_significance(self):
        state = self.mission(Lens.GENIUS_APPRECIATION)
        for kind in ("ORIGINALITY", "SYNTHESIS", "SIGNIFICANCE"):
            self.agent.add_appreciation_finding(
                state,
                AppreciationFinding(
                    finding_id=f"F-{kind}",
                    kind=kind,
                    claim=f"supported {kind.lower()} finding",
                    evidence_refs=("src-1",),
                    confidence=.9,
                ),
            )
        self.assertTrue(self.agent.can_enter_technical_critique(state))

    def test_specialist_selection_changes_for_appreciation_lens(self):
        state = self.mission(Lens.GENIUS_APPRECIATION)
        roles = self.agent.select_specialists(state, complexity=.8, stakes=.8)
        self.assertIn(SpecialistRole.INNOVATION_HISTORIAN, roles)
        self.assertIn(SpecialistRole.SYNTHESIS_SCHOLAR, roles)
        self.assertIn(SpecialistRole.CHALLENGER, roles)
        self.assertIn(SpecialistRole.VERIFIER, roles)

    def test_route_score_penalizes_duplicate_and_coordination_overhead(self):
        clean = RouteCandidate("R1", "independent clean route", impact=.9, proofability=.9)
        noisy = RouteCandidate(
            "R2",
            "duplicate expensive route",
            impact=.9,
            proofability=.9,
            duplication=.8,
            coordination_overhead=.8,
        )
        self.assertGreater(clean.score(), noisy.score())

    def test_multi_path_selection_rejects_collision_and_semantic_duplicate(self):
        state = self.mission()
        routes = [
            RouteCandidate("R1", "reuse existing proof engine", family="REUSE", information_gain=.7),
            RouteCandidate("R2", "reuse existing proof engine exactly", family="REUSE", information_gain=.6),
            RouteCandidate("R3", "build independent challenger", family="CHALLENGE", information_gain=.8),
            RouteCandidate("R4", "mutate shared target", family="BUILD", information_gain=.9, collision_key="shared"),
            RouteCandidate("R5", "another shared mutation", family="BUILD2", information_gain=.8, collision_key="shared"),
        ]
        selected = self.agent.select_parallel_routes(state, routes, max_paths=4)
        ids = {r.route_id for r in selected}
        self.assertIn("R1", ids)
        self.assertIn("R3", ids)
        self.assertFalse({"R4", "R5"} <= ids)
        self.assertFalse({"R1", "R2"} <= ids)

    def test_event_chain_detects_tamper(self):
        state = self.mission()
        self.agent.record_event(state, TerminalEvent.SUCCESS, {"x": 1})
        self.agent.record_event(state, TerminalEvent.EXPERIMENT_RESULT, {"x": 2})
        self.assertTrue(self.agent.verify_event_chain(state))
        original = state.events[0]
        state.events[0] = AgentEvent(
            sequence=original.sequence,
            event_type=original.event_type,
            payload={"x": 999},
            previous_hash=original.previous_hash,
            event_hash=original.event_hash,
        )
        self.assertFalse(self.agent.verify_event_chain(state))

    def test_repeated_failed_route_is_banned(self):
        state = self.mission()
        self.agent.record_failure(state, route_id="R1", fingerprint="F1", error="boom")
        self.agent.record_failure(state, route_id="R1", fingerprint="F1", error="boom again")
        self.assertIn("R1", state.banned_routes)

    def test_root_cause_required_to_close_failure(self):
        state = self.mission()
        self.agent.record_failure(state, route_id="R1", fingerprint="F1", error="boom")
        self.assertFalse(self.agent.failure_can_close(state, "F1"))
        state.root_causes["F1"] = "stale provider state"
        self.assertTrue(self.agent.failure_can_close(state, "F1"))

    def test_recovery_selects_material_available_route_not_banned_route(self):
        state = self.mission()
        state.banned_routes.add("R1")
        r1 = RouteCandidate("R1", "failed", information_gain=1)
        r2 = RouteCandidate("R2", "fresh provider readback", information_gain=.6)
        self.assertEqual("R2", self.agent.recovery_route(state, (r1, r2)).route_id)

    def test_completion_requires_independent_verification_not_artifact(self):
        state = self.mission()
        state.artifacts.append("artifact.json")
        self.agent.mark_predicate_satisfied(state, "built")
        self.agent.mark_predicate_satisfied(state, "verified")
        decision = self.agent.completion_gate(state)
        self.assertFalse(decision.complete)
        self.assertIn("INDEPENDENT_VERIFICATION_MISSING", decision.missing_requirements)

    def test_completion_passes_with_predicates_and_independent_proof(self):
        state = self.mission()
        self.agent.mark_predicate_satisfied(state, "built")
        self.agent.mark_predicate_satisfied(state, "verified")
        self.agent.add_evidence(
            state,
            Evidence(
                ref="proof-1",
                kind="READBACK",
                claim="independent semantic verification",
                verified=True,
                independent=True,
            ),
        )
        decision = self.agent.completion_gate(state)
        self.assertTrue(decision.complete)
        self.assertEqual("COMPLETE_VERIFIED", decision.state)

    def test_critical_unknown_blocks_completion(self):
        state = self.mission()
        state.satisfied_predicates.update({"built", "verified"})
        state.critical_unknowns.add("provider identity")
        self.agent.add_evidence(state, Evidence("proof", "READBACK", "ok", True, True))
        decision = self.agent.completion_gate(state)
        self.assertIn("CRITICAL_UNKNOWNS_OPEN", decision.missing_requirements)

    def test_context_compaction_preserves_mission_truth_and_limits_event_window(self):
        state = self.mission()
        state.open_unknowns.append("unknown-1")
        for i in range(20):
            self.agent.record_event(state, TerminalEvent.EXPERIMENT_RESULT, {"i": i})
        compact = self.agent.compact_context(state, event_window=5)
        self.assertEqual(state.contract.objective, compact["objective"])
        self.assertEqual(["unknown-1"], compact["open_unknowns"])
        self.assertEqual(5, len(compact["recent_events"]))
        self.assertEqual(state.events[-1].event_hash, compact["event_chain_tip"])

    def test_tool_search_loads_only_relevant_safe_tools(self):
        catalog = [
            ToolDescriptor("T1", "drive_search", "search documents in drive", ("docs", "search")),
            ToolDescriptor("T2", "mail_send", "send external mail", ("email",), external_effect=True),
            ToolDescriptor("T3", "github_search", "search source code", ("code", "search")),
        ]
        tools = self.agent.tool_search("search source code", catalog)
        self.assertEqual("T3", tools[0].tool_id)
        self.assertNotIn("T2", {t.tool_id for t in tools})

    def test_external_effect_is_held_by_default(self):
        state = self.mission()
        self.assertTrue(self.agent.bounded_autonomy_allowed(state, external_effect=False))
        self.assertFalse(self.agent.bounded_autonomy_allowed(state, external_effect=True))

    def test_model_request_is_versioned_and_lens_aware(self):
        state = self.mission(Lens.GENIUS_APPRECIATION)
        req = self.agent.make_model_request(state, SpecialistRole.SYNTHESIS_SCHOLAR)
        self.assertEqual(state.version, req.mission_version)
        self.assertEqual(Lens.GENIUS_APPRECIATION, req.lens)
        self.assertEqual(MissionPhase.APPRECIATE, req.phase)


if __name__ == "__main__":
    unittest.main()
