from __future__ import annotations

import unittest

from bubbles.ict_organisation_leadership_lab import (
    ICTOrganisationLeadershipLab,
    ICTRole,
    ServiceDemand,
    SourcingOption,
    synthetic_reference_demands,
    synthetic_reference_roles,
    synthetic_reference_sourcing_options,
)


class ICTOrganisationLeadershipLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = ICTOrganisationLeadershipLab()

    def test_reference_assessment_is_deterministic_and_proof_bound(self) -> None:
        first = self.lab.assess_organisation(
            synthetic_reference_roles(),
            synthetic_reference_demands(),
            synthetic_reference_sourcing_options(),
        )
        second = self.lab.assess_organisation(
            synthetic_reference_roles(),
            synthetic_reference_demands(),
            synthetic_reference_sourcing_options(),
        )
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual("LOCAL_DEMONSTRATION_VERIFIED", first["proof_state"])
        self.assertIn("not evidence that Kim personally", first["truth_boundary"])
        self.assertIn("Ledger approval", first["truth_boundary"])

    def test_capacity_gap_is_exposed_not_hidden(self) -> None:
        roles = (ICTRole("R1", "Lead", "infra", 1.0, 90, ("network",), ("network",), True),)
        demands = (ServiceDemand("S1", "Network", 2_000, 90, ("infra",)),)
        result = self.lab.capacity_gaps(roles, demands)
        self.assertEqual("CAPACITY_GAP", result["infra"]["state"])
        self.assertLess(result["infra"]["surplus_gap_hours"], 0)

    def test_skill_gap_is_explicit(self) -> None:
        gaps = self.lab.skill_gaps(synthetic_reference_roles())
        self.assertIn("R-INF", gaps)
        self.assertIn("cloud", gaps["R-INF"])
        self.assertIn("dr", gaps["R-INF"])

    def test_critical_role_without_successor_is_flagged(self) -> None:
        risks = self.lab.succession_risks(synthetic_reference_roles())
        self.assertIn("R-INF", risks)
        self.assertIn("R-APP", risks)
        self.assertNotIn("R-CYB", risks)

    def test_sourcing_comparison_requires_one_capability(self) -> None:
        options = (
            SourcingOption("cloud", "INSOURCE", 100, 20, 80, 80),
            SourcingOption("network", "HYBRID", 100, 20, 80, 80),
        )
        with self.assertRaisesRegex(ValueError, "one capability"):
            self.lab.choose_sourcing(options)

    def test_sourcing_decision_is_bounded_and_has_governance_boundary(self) -> None:
        decision = self.lab.choose_sourcing(synthetic_reference_sourcing_options())
        self.assertIn(decision["recommended_model"], {"INSOURCE", "OUTSOURCE", "HYBRID"})
        self.assertGreaterEqual(decision["score"], 0)
        self.assertLessEqual(decision["score"], 100)
        self.assertIn("Synthetic decision support", decision["decision_boundary"])

    def test_invalid_criticality_fails_closed(self) -> None:
        role = ICTRole("BAD", "Bad", "infra", 1.0, 101, ("network",), ("network",), False)
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            self.lab.assess_organisation((role,), synthetic_reference_demands())

    def test_safe_claim_does_not_inflate_personal_people_authority(self) -> None:
        claim = self.lab.safe_claim().lower()
        self.assertIn("synthetic", claim)
        self.assertNotIn("managed staff", claim)
        self.assertGreaterEqual(len(self.lab.forbidden_claims()), 5)


if __name__ == "__main__":
    unittest.main()
