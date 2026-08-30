import unittest

from sovara.creative.creative_graph import (
    CreativeGraph,
    CreativeNodeKind,
    GraphConflictError,
    LockedNodeError,
)
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.policy import ContentClass, PrivacyClass
from sovara.creative.producer import ProducerCompiler
from sovara.creative.ripple import RippleCompiler
from sovara.creative.taste import TasteMemory, TasteObservation


class SovaraCreativeRippleTests(unittest.TestCase):
    def fixtures(self):
        mission = CreativeMissionGenome.build(
            mission_id="mission-ripple",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a launch campaign",
            privacy_class=PrivacyClass.PUBLIC,
            required_modalities=("image", "video"),
            target_channels=("review",),
            rights_state=RightsState.NOT_APPLICABLE,
            owner_approval_required=True,
        )
        graph = CreativeGraph("mission-ripple")
        head = graph.head_version
        nodes = (
            ("concept", CreativeNodeKind.CONCEPT, {"lighting": "low-key"}),
            ("image-asset", CreativeNodeKind.ASSET, {"modality": "image"}),
            ("video-shot", CreativeNodeKind.SHOT, {"modality": "video"}),
            ("locked-package", CreativeNodeKind.PACKAGE, {}),
        )
        for node_id, kind, attributes in nodes:
            head = graph.add_node(
                expected_version=head,
                node_id=node_id,
                kind=kind,
                attributes=attributes,
            ).version_id
        for source, target in (
            ("concept", "image-asset"),
            ("concept", "video-shot"),
            ("video-shot", "locked-package"),
        ):
            head = graph.add_dependency(
                expected_version=head,
                source_id=source,
                target_id=target,
            ).version_id
        head = graph.set_lock(
            expected_version=head,
            node_id="locked-package",
            locked=True,
        ).version_id
        taste = TasteMemory("owner")
        taste.observe(TasteObservation("taste-1", "lighting", "low-key", 1.0, 1))
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        return mission, graph, taste, plan, head

    def test_concept_correction_regenerates_modalities_but_preserves_intent_steps(self):
        mission, graph, taste, plan, head = self.fixtures()
        receipt = RippleCompiler().apply(
            mission=mission,
            graph=graph,
            plan=plan,
            taste=taste,
            expected_graph_version=head,
            node_id="concept",
            patch={"tone": "warmer"},
        )
        self.assertEqual(receipt.invalidated_node_ids, ("image-asset", "video-shot"))
        self.assertEqual(receipt.blocked_locked_node_ids, ("locked-package",))
        self.assertIn("10-01-prepare-image", receipt.regeneration_step_ids)
        self.assertIn("10-02-prepare-video", receipt.regeneration_step_ids)
        self.assertIn("01-interpret-intent", receipt.preserved_step_ids)
        self.assertTrue(receipt.owner_review_required)

    def test_image_only_correction_preserves_video_work_packet(self):
        mission, graph, taste, plan, head = self.fixtures()
        receipt = RippleCompiler().apply(
            mission=mission,
            graph=graph,
            plan=plan,
            taste=taste,
            expected_graph_version=head,
            node_id="image-asset",
            patch={"crop": "portrait"},
        )
        self.assertIn("10-01-prepare-image", receipt.regeneration_step_ids)
        self.assertNotIn("10-02-prepare-video", receipt.regeneration_step_ids)
        self.assertIn("10-02-prepare-video", receipt.preserved_step_ids)

    def test_taste_conflict_requires_owner_review(self):
        mission, graph, taste, plan, head = self.fixtures()
        receipt = RippleCompiler().apply(
            mission=mission,
            graph=graph,
            plan=plan,
            taste=taste,
            expected_graph_version=head,
            node_id="concept",
            patch={"lighting": "bright"},
        )
        self.assertEqual(receipt.taste_conflict_dimensions, ("lighting",))
        self.assertTrue(receipt.owner_review_required)

    def test_stale_plan_or_graph_is_rejected_before_mutation(self):
        mission, graph, taste, plan, head = self.fixtures()
        graph.update_node(
            expected_version=head,
            node_id="image-asset",
            patch={"crop": "square"},
        )
        with self.assertRaises(GraphConflictError):
            RippleCompiler().apply(
                mission=mission,
                graph=graph,
                plan=plan,
                taste=taste,
                expected_graph_version=head,
                node_id="concept",
                patch={"tone": "warmer"},
            )

    def test_locked_target_cannot_be_corrected(self):
        mission, graph, taste, plan, head = self.fixtures()
        with self.assertRaises(LockedNodeError):
            RippleCompiler().apply(
                mission=mission,
                graph=graph,
                plan=plan,
                taste=taste,
                expected_graph_version=head,
                node_id="locked-package",
                patch={"format": "new"},
            )

    def test_replay_is_deterministic_and_effect_free(self):
        def execute():
            mission, graph, taste, plan, head = self.fixtures()
            return RippleCompiler().apply(
                mission=mission,
                graph=graph,
                plan=plan,
                taste=taste,
                expected_graph_version=head,
                node_id="image-asset",
                patch={"crop": "portrait"},
            )

        a = execute()
        b = execute()
        self.assertEqual(a, b)
        self.assertFalse(a.authority_inherited)
        self.assertFalse(a.provider_execution_performed)
        self.assertFalse(a.external_effect_performed)


if __name__ == "__main__":
    unittest.main()
