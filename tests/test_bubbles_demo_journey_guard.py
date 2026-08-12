from __future__ import annotations

import unittest

from bubbles.demo_journey_guard import DemoJourneyGuard


class PrismDemoJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = DemoJourneyGuard.load()

    def test_both_demo_journeys_are_registered_and_safe(self) -> None:
        self.assertEqual({"DEMO-IPEP-SAFE-001", "DEMO-K10-SAFE-001"}, set(self.guard.journeys))
        self.assertTrue(all(j["safe_data_only"] for j in self.guard.journeys.values()))

    def test_ipep_search_result_requires_provenance_fields(self) -> None:
        safe = {
            "source_item_id": "SYN-001",
            "segment_id": "SEG-001",
            "start_seconds": 1.0,
            "end_seconds": 2.0,
            "review_state": "UNREVIEWED",
            "citation": "audio:SYN-001#segment=SEG-001&t=1.000-2.000",
        }
        self.assertTrue(self.guard.ipep_result_is_safe(safe))
        unsafe = dict(safe)
        unsafe.pop("review_state")
        self.assertFalse(self.guard.ipep_result_is_safe(unsafe))

    def test_ipep_journey_can_complete_from_existing_local_proofs(self) -> None:
        proofs = {key: "verified" for key in self.guard.journeys["DEMO-IPEP-SAFE-001"]["completion_requirements"]}
        assessment = self.guard.assess("DEMO-IPEP-SAFE-001", proofs)
        self.assertTrue(assessment["complete"])
        self.assertEqual("DEMO_PROOF_COMPLETE", assessment["execution_state"])

    def test_k10_cannot_claim_render_before_real_export_proofs(self) -> None:
        proofs = {
            "brief_receipt": "BRIEF-1",
            "scene_plan": "SCENES-1",
            "asset_manifest": "ASSETS-1",
            "canva_design_reference": "CANVA-1",
        }
        assessment = self.guard.assess("DEMO-K10-SAFE-001", proofs)
        self.assertFalse(assessment["complete"])
        self.assertFalse(self.guard.k10_render_claim_allowed(proofs))
        self.assertIn("rendered_asset_ref", assessment["missing_proofs"])
        self.assertIn("export_receipt", assessment["missing_proofs"])

    def test_k10_render_claim_requires_both_render_and_export_receipt(self) -> None:
        required = self.guard.journeys["DEMO-K10-SAFE-001"]["completion_requirements"]
        proofs = {key: f"proof:{key}" for key in required}
        self.assertTrue(self.guard.k10_render_claim_allowed(proofs))


if __name__ == "__main__":
    unittest.main()
