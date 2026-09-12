from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_source_scorecard_v1 import score_source_programme


class KimDataverseLevel7PlusSourceScorecardTests(unittest.TestCase):
    def test_source_complete_but_empirical_provider_and_value_empty_cannot_claim_level7(self) -> None:
        signals = {
            "objective_ecology": True,
            "resource_economy": True,
            "unified_autonomic_loops": True,
            "digital_twin": True,
            "dynamic_reorganization": True,
            "architectural_entropy_controller": True,
            "constitutional_amendment_court": True,
            "capability_market": True,
            "owner_interruption_firewall": True,
            "autonomy_debt": True,
            "causal_learning": True,
            "information_value_budgeting": True,
            "negative_knowledge_diffusion": True,
            "no_self_authority_promotion": True,
        }
        score = score_source_programme(signals)
        self.assertEqual(100.0, score.architecture_score)
        self.assertEqual(100.0, score.control_plane_score)
        self.assertEqual(0.0, score.empirical_score)
        self.assertEqual(0.0, score.provider_score)
        self.assertEqual(0.0, score.value_score)
        self.assertFalse(score.level7_claim_allowed)

    def test_only_complete_all_axes_allows_level7_claim(self) -> None:
        keys = {
            "objective_ecology",
            "resource_economy",
            "unified_autonomic_loops",
            "digital_twin",
            "dynamic_reorganization",
            "architectural_entropy_controller",
            "constitutional_amendment_court",
            "capability_market",
            "owner_interruption_firewall",
            "autonomy_debt",
            "causal_learning",
            "information_value_budgeting",
            "negative_knowledge_diffusion",
            "no_self_authority_promotion",
            "persistent_no_chat_continuity",
            "observed_maintenance_self_resolution",
            "observed_recovery_self_resolution",
            "observed_owner_interrupt_reduction",
            "provider_native_readback",
            "provider_wait_wake",
            "cross_machine_handoff",
            "prospective_owner_value",
            "sustained_value",
        }
        score = score_source_programme({key: True for key in keys})
        self.assertTrue(score.level7_claim_allowed)


if __name__ == "__main__":
    unittest.main()
