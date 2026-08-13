from __future__ import annotations

import unittest

from bubbles.executive_technology_management_lab import (
    ExecutiveTechnologyManagementLab,
    TechnologyInvestment,
    VendorScorecard,
    synthetic_reference_portfolio,
    synthetic_reference_vendors,
)


class ExecutiveTechnologyManagementLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = ExecutiveTechnologyManagementLab(annual_budget=6_000_000)

    def test_reference_portfolio_is_within_budget_and_deterministic(self) -> None:
        first = self.lab.assess_portfolio(synthetic_reference_portfolio(), synthetic_reference_vendors())
        second = self.lab.assess_portfolio(synthetic_reference_portfolio(), synthetic_reference_vendors())
        self.assertLessEqual(first["annual_commitment"], first["annual_budget"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual("LOCAL_DEMONSTRATION_VERIFIED", first["proof_state"])

    def test_over_budget_portfolio_fails_closed(self) -> None:
        item = TechnologyInvestment(
            "BIG", "Overspend", 6_100_000, 7_000_000, 8_000_000, 10,
            "CIO", "value", 1.0,
        )
        with self.assertRaisesRegex(ValueError, "exceeds annual synthetic budget"):
            self.lab.assess_portfolio((item,))

    def test_missing_owner_or_kpi_is_rejected(self) -> None:
        item = TechnologyInvestment(
            "NOOWNER", "No owner", 100, 300, 600, 10, "", "value", 1.0,
        )
        with self.assertRaisesRegex(ValueError, "owner and KPI"):
            self.lab.assess_portfolio((item,))

    def test_unobserved_benefit_cannot_be_claimed_as_realised(self) -> None:
        ai = next(item for item in synthetic_reference_portfolio() if item.investment_id == "INV-AI")
        self.assertEqual("TARGET_HYPOTHESIS_NOT_OBSERVED", self.lab.benefit_state(ai))

    def test_vendor_score_is_bounded_and_exit_plan_matters(self) -> None:
        healthy = synthetic_reference_vendors()[0]
        result = self.lab.vendor_health(healthy)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

        locked = VendorScorecard("LOCKED", "Locked Vendor", 1000, 99.0, 99.0, 10, 90, False)
        locked_result = self.lab.vendor_health(locked)
        self.assertEqual("REVIEW", locked_result["decision"])

    def test_unknown_dependency_fails_closed(self) -> None:
        item = TechnologyInvestment(
            "DEP", "Dependency test", 100, 300, 600, 10,
            "Owner", "metric", 1.0, dependencies=("MISSING",),
        )
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            self.lab.assess_portfolio((item,))

    def test_truth_boundary_preserves_personal_evidence_separation(self) -> None:
        receipt = self.lab.assess_portfolio(synthetic_reference_portfolio(), synthetic_reference_vendors())
        boundary = receipt["truth_boundary"]
        self.assertIn("synthetic", boundary.lower())
        self.assertIn("not evidence that Kim personally", boundary)
        self.assertIn("Ledger approval", boundary)

    def test_safe_claim_does_not_assert_real_budget_or_roi(self) -> None:
        claim = self.lab.safe_claim().lower()
        self.assertIn("synthetic", claim)
        self.assertNotIn("managed a real", claim)
        self.assertNotIn("verified roi", claim)
        self.assertGreaterEqual(len(self.lab.forbidden_claims()), 5)


if __name__ == "__main__":
    unittest.main()
