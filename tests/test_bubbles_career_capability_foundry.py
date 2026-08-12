from __future__ import annotations

import unittest
from pathlib import Path

from bubbles.career_capability_foundry import (
    CareerCapabilityFoundry,
    GapClass,
    GrowthState,
)


ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ROOT / "bubbles" / "career_market_signals_20260812.json"
EXISTING_ROLES = {
    "Bubbles",
    "Forge",
    "Sparks",
    "Pulse",
    "Patch",
    "Ledger",
    "Sentinel",
    "Bridge",
    "Scout",
    "Prism",
    "Beacon",
    "Showcase",
}


class CareerCapabilityFoundryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.foundry = CareerCapabilityFoundry()
        self.roles = self.foundry.load_role_signals(SIGNALS)
        self.by_role = {role.role_id: role for role in self.roles}

    def assessment_map(self, **kwargs):
        return {item.capability_id: item for item in self.foundry.assess(self.roles, **kwargs)}

    def test_seed_has_two_live_vacancies_and_four_sector_benchmarks(self) -> None:
        self.assertEqual(6, len(self.roles))
        self.assertEqual(2, sum(role.signal_type == "VACANCY" for role in self.roles))
        self.assertEqual(4, sum(role.signal_type == "SECTOR_BENCHMARK" for role in self.roles))

    def test_enko_maps_to_reusable_business_technology_capabilities(self) -> None:
        hits = set(self.foundry.match_role(self.by_role["ENKO-BTSM-20260812"]))
        required = {
            "CAP-EA",
            "CAP-HE-DIGITAL",
            "CAP-API",
            "CAP-DATA-BI",
            "CAP-CHANGE",
            "CAP-IT-FIN",
            "CAP-VENDOR",
            "CAP-PPM",
        }
        self.assertTrue(required.issubset(hits), (required - hits, hits))

    def test_regenesys_maps_to_academic_governance_and_higher_ed(self) -> None:
        hits = set(self.foundry.match_role(self.by_role["REGENESYS-GM-SOT-20260812"]))
        self.assertIn("CAP-ACADEMIC-GOV", hits)
        self.assertIn("CAP-HE-DIGITAL", hits)
        self.assertIn("CAP-DIGITAL-CAMPUS", hits)
        self.assertIn("CAP-PPM", hits)

    def test_rosebank_benchmark_deepens_student_lifecycle_and_platform_signals(self) -> None:
        hits = set(self.foundry.match_role(self.by_role["ROSEBANK-DIGITAL-ENABLEMENT-BENCHMARK-20260812"]))
        self.assertIn("CAP-HE-DIGITAL", hits)
        self.assertIn("CAP-LMS-SIS-ERP", hits)
        self.assertIn("CAP-DIGITAL-CAMPUS", hits)
        self.assertIn("CAP-IT-FIN", hits)

    def test_up_benchmark_deepens_api_and_integration_signal(self) -> None:
        hits = set(self.foundry.match_role(self.by_role["UP-MIDDLEWARE-INTEGRATION-BENCHMARK-20260812"]))
        self.assertIn("CAP-API", hits)
        self.assertIn("CAP-EA", hits)

    def test_recurring_or_strategic_gaps_are_promoted_to_build(self) -> None:
        assessments = self.assessment_map()
        self.assertEqual(GrowthState.BUILD, assessments["CAP-EA"].growth_state)
        self.assertEqual(GrowthState.BUILD, assessments["CAP-ACADEMIC-GOV"].growth_state)
        self.assertEqual(GrowthState.BUILD, assessments["CAP-LMS-SIS-ERP"].growth_state)
        self.assertEqual(GrowthState.BUILD, assessments["CAP-IT-GRC"].growth_state)

    def test_bubbles_coverage_does_not_become_personal_experience(self) -> None:
        assessments = self.assessment_map(bubbles_verified={"CAP-EA"})
        self.assertEqual(GapClass.USER_EVIDENCE_GAP, assessments["CAP-EA"].gap_class)
        self.assertNotEqual(GapClass.COVERED, assessments["CAP-EA"].gap_class)
        self.assertIn("human owner", assessments["CAP-EA"].truth_boundary)

    def test_user_evidence_does_not_self_certify_bubbles_capability(self) -> None:
        assessments = self.assessment_map(user_evidence={"CAP-EA"})
        self.assertEqual(GapClass.BUBBLES_CAPABILITY_GAP, assessments["CAP-EA"].gap_class)

    def test_only_dual_evidence_is_covered(self) -> None:
        assessments = self.assessment_map(user_evidence={"CAP-EA"}, bubbles_verified={"CAP-EA"})
        self.assertEqual(GapClass.COVERED, assessments["CAP-EA"].gap_class)
        self.assertEqual(GrowthState.TESTED, assessments["CAP-EA"].growth_state)

    def test_minimum_squads_reuse_existing_roles_and_always_include_ledger(self) -> None:
        assessments = self.foundry.assess(self.roles)
        for assessment in assessments:
            self.assertEqual("Bubbles", assessment.squad[0])
            self.assertIn("Ledger", assessment.squad)
            self.assertTrue(set(assessment.squad).issubset(EXISTING_ROLES), assessment.squad)
            self.assertLessEqual(len(assessment.squad), len(EXISTING_ROLES))

    def test_backlog_digest_is_deterministic(self) -> None:
        assessments = self.foundry.assess(self.roles)
        first = self.foundry.backlog(assessments)
        second = self.foundry.backlog(assessments)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first, second)

    def test_capabilities_not_observed_are_not_in_backlog(self) -> None:
        one_role = (self.by_role["REGENESYS-GM-SOT-20260812"],)
        ids = {item.capability_id for item in self.foundry.assess(one_role)}
        self.assertNotIn("CAP-CLOUD", ids)
        self.assertNotIn("CAP-API", ids)

    def test_cloud_pack_requires_provider_readback_gate(self) -> None:
        cloud = self.foundry.by_id["CAP-CLOUD"]
        gates = self.foundry._proof_gates(cloud)
        self.assertIn("PROVIDER_READBACK", gates)
        self.assertEqual("LEDGER_APPROVED_CLAIM", gates[-1])


if __name__ == "__main__":
    unittest.main()
