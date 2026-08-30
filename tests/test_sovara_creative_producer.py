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

    def test_plan_binds_exact_policy_state(self):
        mission, graph, taste = self.fixtures()
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        self.assertEqual(plan.content_class, ContentClass.BRAND_COMMERCIAL.value)
        self.assertEqual(plan.privacy_class, PrivacyClass.PUBLIC.value)
        self.assertEqual(plan.rights_state, RightsState.NOT_APPLICABLE.value)
        self.assertTrue(plan.owner_approval_required)
        binding = next(
            step for step in plan.steps if step.step_id == "02-bind-creative-state"
        )
        self.assertEqual(binding.action, "BIND_GRAPH_TASTE_AND_POLICY_STATE")
        self.assertEqual(
            binding.inputs[2:],
            (
                ContentClass.BRAND_COMMERCIAL.value,
                PrivacyClass.PUBLIC.value,
                RightsState.NOT_APPLICABLE.value,
                "OWNER_APPROVAL_REQUIRED",
            ),
        )

    def test_each_policy_fact_changes_plan_hash(self):
        mission, graph, taste = self.fixtures()
        baseline = ProducerCompiler().compile(
            mission=mission,
            graph=graph,
            taste=taste,
        )
        variants = {
            "content_class": CreativeMissionGenome.build(
                mission_id=mission.mission_id,
                content_class=ContentClass.SOCIAL,
                objective=mission.objective,
                privacy_class=mission.privacy_class,
                required_modalities=mission.required_modalities,
                target_channels=mission.target_channels,
                rights_state=mission.rights_state,
                owner_approval_required=mission.owner_approval_required,
            ),
            "privacy_class": CreativeMissionGenome.build(
                mission_id=mission.mission_id,
                content_class=mission.content_class,
                objective=mission.objective,
                privacy_class=PrivacyClass.INTERNAL,
                required_modalities=mission.required_modalities,
                target_channels=mission.target_channels,
                rights_state=mission.rights_state,
                owner_approval_required=mission.owner_approval_required,
            ),
            "rights_state": CreativeMissionGenome.build(
                mission_id=mission.mission_id,
                content_class=mission.content_class,
                objective=mission.objective,
                privacy_class=mission.privacy_class,
                required_modalities=mission.required_modalities,
                target_channels=mission.target_channels,
                rights_state=RightsState.VERIFIED,
                owner_approval_required=mission.owner_approval_required,
            ),
            "owner_approval_required": CreativeMissionGenome.build(
                mission_id=mission.mission_id,
                content_class=mission.content_class,
                objective=mission.objective,
                privacy_class=mission.privacy_class,
                required_modalities=mission.required_modalities,
                target_channels=mission.target_channels,
                rights_state=mission.rights_state,
                owner_approval_required=False,
            ),
        }
        for fact, variant in variants.items():
            with self.subTest(fact=fact):
                candidate = ProducerCompiler().compile(
                    mission=variant,
                    graph=graph,
                    taste=taste,
                )
                self.assertNotEqual(candidate.plan_sha256, baseline.plan_sha256)

    def test_mature_verified_policy_state_is_explicit_in_plan(self):
        _, graph, taste = self.fixtures()
        mission = CreativeMissionGenome.build(
            mission_id=graph.graph_id,
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            objective="Compile a rights-verified mature production plan",
            privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
            required_modalities=("image", "video"),
            target_channels=("review",),
            rights_state=RightsState.VERIFIED,
            owner_approval_required=True,
        )
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        self.assertEqual(plan.content_class, ContentClass.MATURE_ADULT_ORIENTED.value)
        self.assertEqual(plan.privacy_class, PrivacyClass.SENSITIVE_PERFORMER.value)
        self.assertEqual(plan.rights_state, RightsState.VERIFIED.value)
        self.assertTrue(plan.owner_approval_required)

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
