import copy
import json
import tempfile
import unittest
from pathlib import Path

from benchmark_fabric.readiness import evaluate, render_markdown, validate


ROOT = Path(__file__).resolve().parents[1]
STANDARD = json.loads((ROOT / "benchmark_fabric/catalog/readiness_standard.json").read_text())
ASSESSMENT = json.loads((ROOT / "benchmark_fabric/evidence/readiness_assessment_2026-08-22.json").read_text())


class ReadinessTests(unittest.TestCase):
    def test_current_profiles_use_strict_minimum(self):
        report = evaluate(STANDARD, ASSESSMENT)
        states = {item["id"]: item["readiness"] for item in report["releaseProfiles"]}
        self.assertEqual({"benchmark_operations": "R3", "jarvis_provider_runtime": "R0", "full_federation": "R0"}, states)

    def test_score_views_cannot_be_combined(self):
        assessment = copy.deepcopy(ASSESSMENT)
        assessment["combinedScore"] = 42
        with self.assertRaisesRegex(ValueError, "combinedScore"):
            validate(STANDARD, assessment)

    def test_failed_provider_canary_is_not_promoted(self):
        report = evaluate(STANDARD, ASSESSMENT)
        item = next(x for x in report["components"] if x["id"] == "gemini_provider_canary")
        self.assertEqual("R2", item["effectiveLevel"])
        self.assertFalse(item["promotionEligible"])
        self.assertIn("provider_canary_failed", item["demotionReasons"])

    def test_identity_failure_demotes_to_r1(self):
        assessment = copy.deepcopy(ASSESSMENT)
        component = next(x for x in assessment["components"] if x["id"] == "google_wif_identity")
        component["currentLevel"] = "R4"
        report = evaluate(STANDARD, assessment)
        item = next(x for x in report["components"] if x["id"] == "google_wif_identity")
        self.assertEqual("R1", item["effectiveLevel"])

    def test_stale_provider_evidence_demotes(self):
        assessment = copy.deepcopy(ASSESSMENT)
        component = next(x for x in assessment["components"] if x["id"] == "knowledge_repository")
        component["evidence"][0]["verifiedAt"] = "2025-01-01T00:00:00Z"
        report = evaluate(STANDARD, assessment)
        item = next(x for x in report["components"] if x["id"] == "knowledge_repository")
        self.assertEqual("R3", item["effectiveLevel"])
        self.assertIn("evidence_stale_or_missing", item["demotionReasons"])

    def test_unknown_profile_component_fails_closed(self):
        standard = copy.deepcopy(STANDARD)
        standard["releaseProfiles"][0]["criticalComponentIds"].append("not_real")
        with self.assertRaisesRegex(ValueError, "unknown components"):
            validate(standard, ASSESSMENT)

    def test_output_is_deterministic_and_renderable(self):
        first = evaluate(STANDARD, ASSESSMENT)
        second = evaluate(STANDARD, ASSESSMENT)
        self.assertEqual(first, second)
        markdown = render_markdown(first)
        self.assertIn("Benchmark operations | R3 | R6", markdown)
        self.assertIn("No combined or averaged score", markdown)


if __name__ == "__main__":
    unittest.main()
