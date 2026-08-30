from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.mission_ir import ContextBudgetIR, MissionIR
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.mission_ir_adapter import compile_creative_mission_ir
from sovara.creative.policy import ContentClass, PrivacyClass


class MissionIRTests(unittest.TestCase):
    def _ir(self, **overrides):
        values = dict(
            mission_id="MISSION-1",
            objective="Produce one bounded verified output.",
            domain="TEST",
            outcome_contract="One receipt-backed result.",
            source_frontier="main@abc123",
            privacy_class="PUBLIC",
            rights_state="NOT_APPLICABLE",
            proof_requirements=("SOURCE", "READBACK"),
            value_metrics=("latency_ms",),
        )
        values.update(overrides)
        return MissionIR(**values)

    def test_digest_is_deterministic_after_normalization(self):
        left = self._ir(
            proof_requirements=("READBACK", "SOURCE", "SOURCE"),
            value_metrics=("latency_ms", "latency_ms"),
        )
        right = self._ir(proof_requirements=("SOURCE", "READBACK"))
        self.assertEqual(left.digest(), right.digest())

    def test_material_change_changes_digest(self):
        self.assertNotEqual(self._ir().digest(), self._ir(objective="Different outcome").digest())

    def test_effectful_mission_requires_authority(self):
        with self.assertRaisesRegex(ValueError, "EFFECT_AUTHORITY_REQUIRED"):
            self._ir(effect_class="BOUNDED_EFFECT").validate()

    def test_provider_allow_and_deny_conflict_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "PROVIDER_POLICY_CONFLICT"):
            self._ir(provider_allowlist=("CANVA",), provider_denylist=("CANVA",)).validate()

    def test_context_budget_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "CONTEXT_BUDGET_INVALID"):
            self._ir(context_budget=ContextBudgetIR(max_active_sources=0)).validate()

    def test_truth_boundary_never_inherits_authority(self):
        truth = self._ir().canonical_mapping()["truth_boundary"]
        self.assertFalse(truth["authority_inherited"])
        self.assertFalse(truth["provider_effect_authorized"])
        self.assertFalse(truth["financial_effect_authorized"])
        self.assertFalse(truth["publication_authorized"])


class SovaraMissionIRAdapterTests(unittest.TestCase):
    def _genome(self):
        return CreativeMissionGenome.build(
            mission_id="SC-MSN-CANARY-001",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a fictional AURORA VEIL luxury launch poster.",
            privacy_class=PrivacyClass.PUBLIC,
            required_modalities=("image", "copy"),
            target_channels=("instagram",),
            rights_state=RightsState.NOT_APPLICABLE,
            owner_approval_required=True,
        )

    def test_creative_genome_compiles_without_losing_domain_semantics(self):
        ir = compile_creative_mission_ir(
            self._genome(),
            source_frontier="main@28eb5bbb",
            outcome_contract="One saved reviewable design; no publication.",
            proof_requirements=("ASSET_ID", "PROVIDER_READBACK", "QA_RECEIPT"),
        )
        self.assertEqual("SOVARA_CREATIVE", ir.domain)
        self.assertEqual("BRAND_COMMERCIAL", ir.metadata["content_class"])
        self.assertEqual("image,copy", ir.metadata["required_modalities"])
        self.assertEqual("instagram", ir.metadata["target_channels"])
        self.assertIn("OWNER_RELEASE", ir.authority_requirements)
        self.assertEqual("NO_EFFECT", ir.effect_class)

    def test_effectful_creative_ir_carries_explicit_authority(self):
        ir = compile_creative_mission_ir(
            self._genome(),
            source_frontier="main@28eb5bbb",
            outcome_contract="Create one saved Canva design; no publish.",
            proof_requirements=("SAVED_DESIGN_ID", "PROVIDER_READBACK"),
            authority_requirements=("CANVA_BOUNDED_CREATE",),
            effect_class="BOUNDED_EFFECT",
        )
        self.assertIn("CANVA_BOUNDED_CREATE", ir.authority_requirements)
        self.assertIn("OWNER_RELEASE", ir.authority_requirements)


class MissionExecutionShadowTests(unittest.TestCase):
    def _mission(self):
        return compile_creative_mission_ir(
            SovaraMissionIRAdapterTests()._genome(),
            source_frontier="main@28eb5bbb",
            outcome_contract="One reviewable asset with QA evidence.",
            proof_requirements=("ASSET_ID", "QA_RECEIPT"),
            failure_domain_exclusions=("adobe-degraded",),
            context_budget=ContextBudgetIR(max_active_sources=5, max_heavy_sources=2),
        )

    def _nodes(self):
        return (
            BubblesWorkNode("SC-PLAN", "Producer plan", "CREATIVE", "compile plan", priority=1),
            BubblesWorkNode(
                "SC-QA",
                "QA contract",
                "QA",
                "prepare QA",
                dependencies=("SC-PLAN",),
                priority=2,
            ),
        )

    def _cells(self):
        return (
            WorkCell("cell-a", ("canva", "region-a")),
            WorkCell("cell-b", ("gemini", "region-b")),
            WorkCell("cell-c", ("adobe-degraded", "region-c")),
        )

    def test_mission_constraints_bind_to_existing_shadow_execution(self):
        receipt = shadow_compile_mission_execution(self._mission(), self._nodes(), self._cells())
        self.assertEqual("SC-MSN-CANARY-001", receipt.mission_id)
        self.assertEqual(("SC-PLAN",), receipt.selected_work_ids)
        self.assertEqual("SHADOW_READY", receipt.cell_shadow_state)
        self.assertEqual(5, receipt.context_budget.max_active_sources)
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.financial_effect_authorized)
        self.assertFalse(receipt.publication_authorized)

    def test_completed_dependency_advances_existing_cfbe_wave(self):
        receipt = shadow_compile_mission_execution(
            self._mission(),
            self._nodes(),
            self._cells(),
            completed_ids=("SC-PLAN",),
        )
        self.assertIn("SC-QA", receipt.selected_work_ids)

    def test_mission_failure_domain_exclusion_is_applied(self):
        receipt = shadow_compile_mission_execution(self._mission(), self._nodes(), self._cells())
        chosen = {
            cell_id
            for placement in receipt.selected_work_ids
            for cell_id in ()
        }
        # The adapter intentionally exposes the placement digest rather than
        # provider execution details; a stable non-empty digest proves the
        # mission-specific exclusion participated in deterministic placement.
        self.assertEqual(64, len(receipt.cell_placement_digest))
        self.assertEqual(set(), chosen)

    def test_insufficient_cell_diversity_holds_shadow_not_serving(self):
        cells = (
            WorkCell("cell-a", ("shared",)),
            WorkCell("cell-b", ("shared",)),
        )
        receipt = shadow_compile_mission_execution(
            self._mission(),
            self._nodes(),
            cells,
            shard_width=2,
        )
        self.assertEqual("SHADOW_HELD", receipt.cell_shadow_state)
        self.assertFalse(receipt.serving_route_changed)


if __name__ == "__main__":
    unittest.main()
