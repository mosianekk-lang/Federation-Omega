import unittest

from sovara.creative.creative_graph import CreativeGraph, CreativeNodeKind
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.policy import ContentClass, PrivacyClass
from sovara.creative.producer import ProducerCompiler, ProducerError, ProductionStep
from sovara.creative.taste import TasteMemory, TasteObservation


class SovaraCreativeProducerTests(unittest.TestCase):
    def fixtures(self):
        mission = CreativeMissionGenome.build(
            mission_id="mission-001",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a premium launch concept",
            privacy_class=PrivacyClass.PUBLIC,
            required_modalities=("image", "video"),
            target_channels=("review",),
            rights_state=RightsState.NOT_APPLICABLE,
            owner_approval_required=True,
        )
        graph = CreativeGraph("mission-001")
        graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
            attributes={"tone": "premium"},
        )
        taste = TasteMemory("owner-creative")
        taste.observe(
            TasteObservation("obs-1", "lighting", "low-key", 1.0, 1)
        )
        return mission, graph, taste

    def test_compile_is_deterministic(self):
        mission, graph, taste = self.fixtures()
        a = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        b = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        self.assertEqual(a, b)

    def test_plan_binds_graph_and_taste_state(self):
        mission, graph, taste = self.fixtures()
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        self.assertEqual(plan.graph_version, graph.head_version)
        self.assertEqual(plan.graph_sha256, graph.state_sha256())
        self.assertEqual(plan.taste_preferences, (("lighting", "low-key"),))

    def test_modalities_compile_into_parallel_work_packets(self):
        mission, graph, taste = self.fixtures()
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        modality_steps = [step for step in plan.steps if step.step_id.startswith("10-")]
        self.assertEqual([step.action for step in modality_steps], [
            "PREPARE_IMAGE_WORK_PACKET",
            "PREPARE_VIDEO_WORK_PACKET",
        ])
        package = next(step for step in plan.steps if step.step_id == "80-package-preview")
        self.assertEqual(package.depends_on, tuple(step.step_id for step in modality_steps))

    def test_release_is_always_owner_gated(self):
        mission, graph, taste = self.fixtures()
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        release = plan.steps[-1]
        self.assertEqual(release.action, "REQUEST_OWNER_RELEASE_DECISION")
        self.assertTrue(release.approval_required)

    def test_plan_never_executes_provider_or_inherits_authority(self):
        mission, graph, taste = self.fixtures()
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        self.assertFalse(plan.authority_inherited)
        self.assertFalse(plan.provider_execution_performed)
        self.assertFalse(plan.external_effect_performed)
        self.assertTrue(all(not step.provider_execution_allowed for step in plan.steps))

    def test_graph_and_mission_identity_must_match(self):
        mission, _, taste = self.fixtures()
        with self.assertRaises(ProducerError):
            ProducerCompiler().compile(
                mission=mission,
                graph=CreativeGraph("different-mission"),
                taste=taste,
            )

    def test_mature_content_rights_gate_is_inherited_from_genome(self):
        with self.assertRaises(ValueError):
            CreativeMissionGenome.build(
                mission_id="adult-mission",
                content_class=ContentClass.MATURE_ADULT_ORIENTED,
                objective="Create an adult-oriented concept",
                privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
                rights_state=RightsState.PENDING,
            )

    def test_invalid_or_effectful_dag_fails_closed(self):
        with self.assertRaises(ProducerError):
            ProducerCompiler._validate_dag([
                ProductionStep("a", "A", (), ("missing",), False)
            ])
        with self.assertRaises(ProducerError):
            ProducerCompiler._validate_dag([
                ProductionStep("a", "A", (), (), False, True)
            ])


if __name__ == "__main__":
    unittest.main()
