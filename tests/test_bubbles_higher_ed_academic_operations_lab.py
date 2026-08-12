from __future__ import annotations

import unittest

from bubbles.higher_ed_academic_operations_lab import AcademicProcess, AcademicRisk, HigherEdAcademicOperationsLab


class HigherEdAcademicOperationsLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = HigherEdAcademicOperationsLab()

    def test_reference_model_covers_required_domains(self) -> None:
        self.assertEqual(set(self.lab.required_domains), {p.domain for p in self.lab.processes})

    def test_complete_synthetic_evidence_reaches_deterministic_tested(self) -> None:
        report = self.lab.operating_report(self.lab.complete_synthetic_evidence())
        self.assertEqual("DETERMINISTIC_TESTED", report["maturity"])
        self.assertEqual(report["process_count"], report["pass_count"])
        self.assertEqual(0, report["gap_count"])

    def test_missing_assessment_moderation_fails_closed(self) -> None:
        evidence = self.lab.complete_synthetic_evidence()
        evidence.pop("ASM-01:moderation record")
        report = self.lab.operating_report(evidence)
        self.assertEqual("IMPLEMENTED_WITH_EVIDENCE_GAPS", report["maturity"])
        assessment = next(item for item in report["processes"] if item["process_id"] == "ASM-01")
        self.assertEqual("EVIDENCE_GAP", assessment["status"])
        self.assertIn("moderation record", assessment["missing_evidence"])

    def test_missing_domain_rejected(self) -> None:
        processes = tuple(p for p in self.lab.processes if p.domain != "academic_integrity")
        with self.assertRaises(ValueError):
            HigherEdAcademicOperationsLab(processes=processes, risks=())

    def test_unknown_risk_process_rejected(self) -> None:
        bad = AcademicRisk("BAD", "bad", ("UNKNOWN",), "none", "HIGH")
        with self.assertRaises(ValueError):
            HigherEdAcademicOperationsLab(risks=(bad,))

    def test_process_must_have_owner_evidence_and_test(self) -> None:
        broken = AcademicProcess("BROKEN", "programme_lifecycle", "x", "", (), "")
        processes = tuple(p for p in self.lab.processes if p.domain != "programme_lifecycle") + (broken,)
        with self.assertRaises(ValueError):
            HigherEdAcademicOperationsLab(processes=processes, risks=())

    def test_receipt_deterministic_and_truth_bound(self) -> None:
        first = self.lab.receipt()
        second = self.lab.receipt()
        self.assertEqual(first, second)
        self.assertEqual(64, len(first["sha256"]))
        self.assertIn("synthetic School-of-Technology academic operations model", first["safe_claim"])
        self.assertIn("served as a dean or academic head", first["forbidden_claims"])

    def test_integrity_process_never_implies_automated_guilt(self) -> None:
        process = next(p for p in self.lab.processes if p.process_id == "INT-01")
        self.assertIn("no automated guilt inference", process.control_test)


if __name__ == "__main__":
    unittest.main()
