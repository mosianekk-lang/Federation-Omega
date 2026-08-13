from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from evidenceops.capital_intelligence_os.demo_pack import CIOSDemoPackBuilder
from evidenceops.capital_intelligence_os.qualification import InternalQualificationCourt


class QualificationCourtTests(unittest.TestCase):
    def test_qualification_court_passes_all_transparent_checks(self):
        report = InternalQualificationCourt().run()
        self.assertTrue(report.passed)
        self.assertEqual(report.score, 1.0)
        self.assertEqual(report.fatal_failures, ())
        self.assertEqual(len(report.receipt_sha256), 64)
        self.assertEqual(report.qualification_class, "SYNTHETIC_DETERMINISTIC_QUALIFICATION")

    def test_qualification_receipt_is_deterministic(self):
        first = InternalQualificationCourt().run()
        second = InternalQualificationCourt().run()
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(
            [(check.check_id, check.passed) for check in first.checks],
            [(check.check_id, check.passed) for check in second.checks],
        )

    def test_qualification_covers_numeric_counterfactual_and_authority_domains(self):
        report = InternalQualificationCourt().run()
        ids = {check.check_id for check in report.checks}
        required = {
            "DCF_ANALYTIC_ORACLE",
            "IRR_ANALYTIC_ORACLE",
            "QOE_EVIDENCE_THRESHOLD",
            "DILIGENCE_BOUNDARY_ORACLE",
            "THESIS_HARD_GATE",
            "AUTHORITY_CONSTITUTION",
            "LEVERAGE_NORMALIZATION_ORACLE",
            "MISSING_EVIDENCE_COUNTERFACTUAL",
            "OFF_THESIS_COUNTERFACTUAL",
            "DETERMINISTIC_ECONOMIC_REPLAY",
        }
        self.assertTrue(required.issubset(ids))


class DemoPackTests(unittest.TestCase):
    def test_demo_pack_is_synthetic_proof_safe_and_human_gated(self):
        pack = CIOSDemoPackBuilder().build()
        manifest = pack["manifest"]
        brief = pack["decision_brief"]
        self.assertEqual(manifest["classification"], "PUBLIC_SAFE_SYNTHETIC_DEMONSTRATION")
        self.assertTrue(manifest["journey_passed"])
        self.assertTrue(manifest["qualification_passed"])
        self.assertGreaterEqual(manifest["contradiction_count"], 1)
        self.assertEqual(manifest["authority"]["final_acquisition"], "REQUIRE_HUMAN")
        self.assertEqual(manifest["authority"]["live_order"], "DENY")
        self.assertEqual(manifest["authority"]["private_to_public_market"], "DENY")
        self.assertEqual(len(pack["pack_sha256"]), 64)
        self.assertIn("SYNTHETIC DEMONSTRATION ONLY", pack["files"]["case_study.md"])

        self.assertEqual(brief["fact_scope"], "SYNTHETIC_FIXTURE_ONLY")
        self.assertTrue(brief["verified_facts"])
        self.assertTrue(all("SYNTHETIC FIXTURE INPUT" in fact for fact in brief["verified_facts"]))
        self.assertNotIn("MODEL OUTPUT", "\n".join(brief["verified_facts"]))
        self.assertTrue(brief["model_outputs"])
        self.assertTrue(all(row["status"] == "MODEL_OUTPUT" for row in brief["model_outputs"]))
        self.assertEqual(brief["evidence_findings"][0]["status"], "EVIDENCE_SYSTEM_OBSERVATION")
        self.assertTrue(brief["requires_human_decision"])

    def test_demo_pack_writes_complete_portfolio_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "cios-demo"
            receipt = CIOSDemoPackBuilder().write(root)
            expected = {
                "manifest.json",
                "decision_brief.json",
                "qualification_receipt.json",
                "case_study.md",
                "dashboard.html",
                "pack_receipt.json",
            }
            self.assertEqual({path.name for path in root.iterdir()}, expected)
            self.assertEqual(len(receipt["pack_sha256"]), 64)
            self.assertFalse(receipt["external_effects"])
            self.assertGreater((root / "dashboard.html").stat().st_size, 100)
            brief_text = (root / "decision_brief.json").read_text()
            self.assertIn("requires_human_decision", brief_text)
            self.assertIn("model_outputs", brief_text)
            self.assertIn("SYNTHETIC_FIXTURE_ONLY", brief_text)


if __name__ == "__main__":
    unittest.main()
