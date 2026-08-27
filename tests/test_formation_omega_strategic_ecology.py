import unittest

from formation_omega.autonomic_fabric import AuthorityCeiling
from formation_omega.strategic_ecology import (
    CapabilityCentrality,
    GenesisSignalType,
    MissionCandidate,
    MissionDeduplicator,
    MissionGenesisEngine,
    MissionGenesisSignal,
    PortfolioAllocator,
    ResourceEnvelope,
    StrategicGenomeLibrary,
    StrategicGenomeRecord,
    StrategicObjective,
    StrategicObjectiveEcology,
)


class StrategicEcologyTests(unittest.TestCase):
    def mission(self, mission_id, **overrides):
        body = dict(
            mission_id=mission_id,
            objective_id="OBJ1",
            summary=f"Mission {mission_id} improve shared capability",
            outcome_value=0.7,
            unlock_leverage=0.5,
            success_probability=0.8,
            learning_value=0.5,
            reusability=0.5,
            cost=0.1,
            risk=0.1,
            latency=0.1,
            required_capabilities=(),
            produces_capabilities=(),
            resource_demand={"attention": 0.2},
        )
        body.update(overrides)
        return MissionCandidate(**body)

    def test_allocator_respects_resource_envelope(self):
        missions = (self.mission("A"), self.mission("B"), self.mission("C"))
        plan = PortfolioAllocator().allocate(missions, ResourceEnvelope({"attention": 0.4}))
        self.assertEqual(len(plan.selected), 2)
        self.assertLessEqual(plan.resource_usage["attention"], 0.4 + 1e-12)

    def test_allocator_respects_dependencies(self):
        foundation = self.mission("foundation", summary="Build foundation capability", unlock_leverage=0.9)
        dependent = self.mission("dependent", dependencies=("foundation",), outcome_value=0.95)
        plan = PortfolioAllocator().allocate((dependent, foundation), ResourceEnvelope({"attention": 1.0}))
        ids = [item.mission_id for item in plan.selected]
        self.assertLess(ids.index("foundation"), ids.index("dependent"))

    def test_allocator_holds_external_effect_without_owner_gate(self):
        external = self.mission(
            "external",
            external_effect=True,
            owner_reserved=True,
            authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT,
        )
        plan = PortfolioAllocator().allocate((external,), ResourceEnvelope({"attention": 1.0}))
        self.assertEqual(plan.selected, ())
        self.assertEqual(dict(plan.held)["external"], "AUTHORITY_CEILING_EXCEEDED")

    def test_capability_centrality_identifies_shared_bottleneck(self):
        missions = (
            self.mission("A", required_capabilities=("apps-script",)),
            self.mission("B", required_capabilities=("apps-script",)),
            self.mission("C", required_capabilities=("github",)),
        )
        pressure = CapabilityCentrality().measure(missions)
        self.assertEqual(pressure[0].capability, "apps-script")
        self.assertEqual(set(pressure[0].demanding_missions), {"A", "B"})

    def test_genesis_engine_creates_proposals_not_executions(self):
        signals = (
            MissionGenesisSignal("S1", GenesisSignalType.CAPABILITY, "Create shared route", 0.9, 0.8, capability="provider-route"),
            MissionGenesisSignal("S2", GenesisSignalType.RISK, "External migration risk", 0.8, 0.7, requires_external_effect=True),
        )
        proposals = MissionGenesisEngine().generate(signals, objective_id="OBJ1")
        self.assertEqual(len(proposals), 2)
        external = next(item for item in proposals if item.external_effect)
        self.assertTrue(external.owner_reserved)
        self.assertEqual(external.authority_ceiling, AuthorityCeiling.A2_BOUNDED_EFFECT)

    def test_deduplicator_flags_high_intent_overlap(self):
        left = self.mission(
            "A",
            summary="Build shared Google Apps Script provider route",
            required_capabilities=("google", "apps-script"),
            produces_capabilities=("provider-route",),
        )
        right = self.mission(
            "B",
            summary="Build shared Google Apps Script provider route",
            required_capabilities=("google", "apps-script"),
            produces_capabilities=("provider-route",),
        )
        suggestions = MissionDeduplicator().suggestions((left, right))
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].canonical_mission_id, "A")

    def test_strategic_genome_recommends_reliable_pattern(self):
        record = StrategicGenomeRecord.create(
            features=("provider", "source-admission", "stale-base"),
            mission_sequence=("reanchor", "ci", "readback"),
            realized_value=0.9,
            reliability=0.95,
            evidence_refs=("PR651",),
        )
        library = StrategicGenomeLibrary((record,))
        recommendations = library.recommend(("provider", "stale-base"))
        self.assertEqual(recommendations[0][0].pattern_id, record.pattern_id)
        self.assertGreater(recommendations[0][1], 0)

    def test_ecology_plan_combines_portfolio_pressure_and_patterns(self):
        record = StrategicGenomeRecord.create(
            features=("convergence", "shared-capability"),
            mission_sequence=("build", "verify"),
            realized_value=0.8,
            reliability=0.9,
        )
        ecology = StrategicObjectiveEcology(genome_library=StrategicGenomeLibrary((record,)))
        objective = StrategicObjective("OBJ1", "Improve mission estate", 0.9, 0.8, 0.9)
        missions = (
            self.mission("A", required_capabilities=("shared-route",)),
            self.mission("B", required_capabilities=("shared-route",)),
        )
        plan = ecology.plan(
            objective=objective,
            missions=missions,
            envelope=ResourceEnvelope({"attention": 1.0}),
            strategic_features=("convergence", "shared-capability"),
        )
        self.assertEqual(plan.objective_id, "OBJ1")
        self.assertEqual(len(plan.portfolio.selected), 2)
        self.assertEqual(plan.capability_pressure[0].capability, "shared-route")
        self.assertEqual(plan.strategic_patterns[0][0], record.pattern_id)
        self.assertTrue(plan.ecology_sha256)

    def test_plan_hash_is_deterministic(self):
        ecology = StrategicObjectiveEcology()
        objective = StrategicObjective("OBJ1", "Improve mission estate", 0.9, 0.8, 0.9)
        missions = (self.mission("A"), self.mission("B"))
        envelope = ResourceEnvelope({"attention": 1.0})
        one = ecology.plan(objective=objective, missions=missions, envelope=envelope)
        two = ecology.plan(objective=objective, missions=missions, envelope=envelope)
        self.assertEqual(one.ecology_sha256, two.ecology_sha256)


if __name__ == "__main__":
    unittest.main()
