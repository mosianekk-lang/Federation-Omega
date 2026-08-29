from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from sovara.creative.gemini_design_promotion import (
    EXPECTED_OUTPUT_SHA256,
    PromotionError,
    can_promote_to_source_candidate,
    evaluate_manifest,
    load_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance" / "sovara_gemini_g2_design_promotion_v1.json"


class SovaraGeminiDesignPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = load_manifest(MANIFEST)

    def test_verified_provider_semantic_proof_is_bound(self) -> None:
        source = self.payload["source_proof"]
        self.assertEqual(33206987595, source["workflow_run_id"])
        self.assertEqual("BuuRaovIGfL1tALF9JSYBQ", source["response_id"])
        self.assertEqual("gemini-3.1-pro-preview", source["model_version"])
        self.assertEqual(12, source["proposal_count"])
        self.assertTrue(source["semantic_verified"])
        self.assertTrue(source["provider_native_readback"])
        self.assertEqual(EXPECTED_OUTPUT_SHA256, source["output_sha256"])

    def test_design_promotion_is_source_candidate_only(self) -> None:
        summary = evaluate_manifest(self.payload)
        self.assertEqual("PERMITTED_WITH_GATES", summary.status)
        self.assertEqual("SOURCE_CANDIDATE", summary.promotion_ceiling)
        self.assertTrue(can_promote_to_source_candidate(self.payload))
        self.assertFalse(summary.deployment_authorized)
        self.assertFalse(summary.provider_effect_authorized)

    def test_all_twelve_proposals_are_adjudicated(self) -> None:
        summary = evaluate_manifest(self.payload)
        self.assertEqual(12, len(summary.source_candidates) + len(summary.evidence_holds))
        self.assertEqual(
            {"PROP-03", "PROP-06", "PROP-10", "PROP-11"},
            set(summary.evidence_holds),
        )

    def test_model_ranking_and_absolute_claims_do_not_become_authority(self) -> None:
        promotion = self.payload["promotion"]
        rules = self.payload["normalization_rules"]
        self.assertFalse(promotion["model_ranking_authority"])
        self.assertFalse(promotion["model_output_is_design_authority"])
        self.assertFalse(rules["absolute_claims_promoted"])
        self.assertTrue(rules["guarantee_language_becomes_testable_hypothesis"])
        self.assertTrue(rules["predicted_roi_is_not_realised_roi"])

    def test_tampered_response_id_fails_closed(self) -> None:
        tampered = deepcopy(self.payload)
        tampered["source_proof"]["response_id"] = ""
        with self.assertRaises(PromotionError):
            evaluate_manifest(tampered)

    def test_tampered_semantic_state_fails_closed(self) -> None:
        tampered = deepcopy(self.payload)
        tampered["source_proof"]["semantic_verified"] = False
        with self.assertRaises(PromotionError):
            evaluate_manifest(tampered)

    def test_tampered_output_hash_fails_closed(self) -> None:
        tampered = deepcopy(self.payload)
        tampered["source_proof"]["output_sha256"] = "0" * 64
        with self.assertRaises(PromotionError):
            evaluate_manifest(tampered)

    def test_production_authority_injection_fails_closed(self) -> None:
        tampered = deepcopy(self.payload)
        tampered["promotion"]["deployment_authorized"] = True
        with self.assertRaises(PromotionError):
            evaluate_manifest(tampered)

    def test_evidence_holds_require_explicit_gates(self) -> None:
        tampered = deepcopy(self.payload)
        for decision in tampered["decisions"]:
            if decision["proposal_id"] == "PROP-06":
                decision["hold_gates"] = []
        with self.assertRaises(PromotionError):
            evaluate_manifest(tampered)


if __name__ == "__main__":
    unittest.main()
