from dataclasses import replace
import unittest

from sovara.creative.creative_graph import (
    CreativeGraph,
    CreativeNodeKind,
    GraphConflictError,
)
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.policy import ContentClass, PrivacyClass
from sovara.creative.producer import ProducerCompiler
from sovara.creative.ripple import RippleCompiler, RippleError
from sovara.creative.taste import TasteMemory, TasteObservation


class SovaraCreativeProducerRippleHandoffTests(unittest.TestCase):
    def fixtures(self):
        mission = CreativeMissionGenome.build(
            mission_id="mission-handoff",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a rights-aware launch package",
            privacy_class=PrivacyClass.INTERNAL,
            required_modalities=("image", "video"),
            target_channels=("owner-review",),
            rights_state=RightsState.NOT_APPLICABLE,
            owner_approval_required=True,
        )
        graph = CreativeGraph(mission.mission_id)
        head = graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
            attributes={"lighting": "low-key"},
        ).version_id
        head = graph.add_node(
            expected_version=head,
            node_id="image-asset",
            kind=CreativeNodeKind.ASSET,
            attributes={"modality": "image"},
        ).version_id
        head = graph.add_dependency(
            expected_version=head,
            source_id="concept",
            target_id="image-asset",
        ).version_id
        taste = TasteMemory("owner-handoff")
        taste.observe(TasteObservation("taste-1", "lighting", "low-key", 1.0, 1))
        plan = ProducerCompiler().compile(mission=mission, graph=graph, taste=taste)
        return mission, graph, taste, plan, head

    def apply(self, mission, graph, taste, plan, head):
        return RippleCompiler().apply(
            mission=mission,
            graph=graph,
            plan=plan,
            taste=taste,
            expected_graph_version=head,
            node_id="image-asset",
            patch={"crop": "portrait"},
        )

    def test_valid_handoff_emits_exact_v2_binding_proof(self):
        mission, graph, taste, plan, head = self.fixtures()
        receipt = self.apply(mission, graph, taste, plan, head)
        self.assertEqual(receipt.schema, "SOVARA_SC_RIPPLE_RECEIPT_V2")
        self.assertEqual(receipt.production_plan_sha256, plan.plan_sha256)
        self.assertTrue(receipt.producer_replay_verified)
        self.assertTrue(receipt.graph_state_binding_verified)
        self.assertTrue(receipt.taste_state_binding_verified)
        self.assertTrue(receipt.policy_state_binding_verified)
        self.assertTrue(receipt.owner_release_gate_preserved)
        self.assertFalse(receipt.authority_inherited)
        self.assertFalse(receipt.provider_execution_performed)
        self.assertFalse(receipt.external_effect_performed)

    def test_plan_tampering_is_rejected_before_graph_mutation(self):
        mutators = {
            "objective": lambda plan: replace(plan, objective="tampered"),
            "schema": lambda plan: replace(plan, schema="UNKNOWN"),
            "graph_hash": lambda plan: replace(plan, graph_sha256="0" * 64),
            "authority_and_effect": lambda plan: replace(
                plan,
                authority_inherited=True,
                provider_execution_performed=True,
                external_effect_performed=True,
            ),
            "provider_step": lambda plan: replace(
                plan,
                steps=(
                    replace(plan.steps[0], provider_execution_allowed=True),
                    *plan.steps[1:],
                ),
            ),
            "owner_gate_removed": lambda plan: replace(plan, steps=plan.steps[:-1]),
            "policy_binding": lambda plan: replace(
                plan,
                steps=tuple(
                    replace(step, inputs=(*step.inputs[:-1], "OWNER_APPROVAL_NOT_REQUIRED"))
                    if step.step_id == "02-bind-creative-state"
                    else step
                    for step in plan.steps
                ),
            ),
        }
        for name, mutate in mutators.items():
            with self.subTest(name=name):
                mission, graph, taste, plan, head = self.fixtures()
                with self.assertRaises((RippleError, GraphConflictError)):
                    self.apply(mission, graph, taste, mutate(plan), head)
                self.assertEqual(graph.head_version, head)

    def test_taste_drift_is_rejected_before_graph_mutation(self):
        mission, graph, taste, plan, head = self.fixtures()
        taste.observe(TasteObservation("taste-2", "tone", "warm", 1.0, 2))
        with self.assertRaises(RippleError):
            self.apply(mission, graph, taste, plan, head)
        self.assertEqual(graph.head_version, head)

    def test_policy_state_mismatch_is_rejected_before_graph_mutation(self):
        mission, graph, taste, plan, head = self.fixtures()
        changed_policy = CreativeMissionGenome.build(
            mission_id=mission.mission_id,
            content_class=ContentClass.EDITORIAL,
            objective=mission.objective,
            privacy_class=PrivacyClass.PRIVATE_ASSET,
            required_modalities=mission.required_modalities,
            target_channels=mission.target_channels,
            rights_state=mission.rights_state,
            owner_approval_required=mission.owner_approval_required,
        )
        with self.assertRaises(RippleError):
            self.apply(changed_policy, graph, taste, plan, head)
        self.assertEqual(graph.head_version, head)

    def test_mature_verified_policy_state_crosses_without_effect_authority(self):
        mission, graph, taste, _plan, head = self.fixtures()
        mature_mission = CreativeMissionGenome.build(
            mission_id=mission.mission_id,
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            objective="Prepare a rights-verified private review package",
            privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
            required_modalities=mission.required_modalities,
            target_channels=mission.target_channels,
            rights_state=RightsState.VERIFIED,
            owner_approval_required=True,
        )
        mature_plan = ProducerCompiler().compile(
            mission=mature_mission,
            graph=graph,
            taste=taste,
        )
        receipt = self.apply(mature_mission, graph, taste, mature_plan, head)
        self.assertTrue(receipt.policy_state_binding_verified)
        self.assertTrue(receipt.owner_release_gate_preserved)
        self.assertFalse(receipt.provider_execution_performed)
        self.assertFalse(receipt.external_effect_performed)


if __name__ == "__main__":
    unittest.main()
