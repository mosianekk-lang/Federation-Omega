from __future__ import annotations

import unittest

from bubbles.higher_ed_it_grc_lab import Control, HigherEdITGRCLab, Risk


class HigherEdITGRCLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = HigherEdITGRCLab()

    def test_reference_model_covers_all_required_domains(self) -> None:
        self.assertEqual(set(self.lab.required_domains), {c.domain for c in self.lab.controls})

    def test_reference_risks_map_only_to_known_controls(self) -> None:
        known = {c.control_id for c in self.lab.controls}
        for risk in self.lab.risks:
            self.assertTrue(set(risk.controls).issubset(known))

    def test_complete_synthetic_evidence_reaches_deterministic_tested(self) -> None:
        report = self.lab.assurance_report(self.lab.complete_synthetic_evidence())
        self.assertEqual("DETERMINISTIC_TESTED", report["maturity"])
        self.assertEqual(report["control_count"], report["pass_count"])
        self.assertEqual(0, report["gap_count"])

    def test_missing_evidence_fails_closed(self) -> None:
        evidence = self.lab.complete_synthetic_evidence()
        evidence.pop("IAM-01:access review receipt")
        report = self.lab.assurance_report(evidence)
        self.assertEqual("IMPLEMENTED_WITH_EVIDENCE_GAPS", report["maturity"])
        iam = next(item for item in report["controls"] if item["control_id"] == "IAM-01")
        self.assertEqual("EVIDENCE_GAP", iam["status"])
        self.assertIn("access review receipt", iam["missing_evidence"])

    def test_missing_required_domain_is_rejected(self) -> None:
        controls = tuple(c for c in self.lab.controls if c.domain != "audit_and_evidence")
        with self.assertRaises(ValueError):
            HigherEdITGRCLab(controls=controls, risks=())

    def test_unknown_risk_control_is_rejected(self) -> None:
        bad = Risk("BAD", "unknown mapping", 2, 2, ("NOPE",), "none")
        with self.assertRaises(ValueError):
            HigherEdITGRCLab(risks=(bad,))

    def test_receipt_is_deterministic_and_truth_bound(self) -> None:
        first = self.lab.receipt()
        second = self.lab.receipt()
        self.assertEqual(first, second)
        self.assertEqual(64, len(first["sha256"]))
        self.assertIn("synthetic higher-education IT governance", first["safe_claim"])
        self.assertIn("performed a real university IT audit", first["forbidden_claims"])

    def test_control_requires_evidence_test_and_owner(self) -> None:
        broken = Control("BROKEN", "strategy_and_governance", "x", (), "", "", "HIGH")
        controls = tuple(c for c in self.lab.controls if c.domain != "strategy_and_governance") + (broken,)
        with self.assertRaises(ValueError):
            HigherEdITGRCLab(controls=controls, risks=())


if __name__ == "__main__":
    unittest.main()
