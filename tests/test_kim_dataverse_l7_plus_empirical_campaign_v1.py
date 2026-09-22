from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_empirical_campaign_v1 import LEVEL7_CAMPAIGN


class KimDataverseLevel7PlusEmpiricalCampaignTests(unittest.TestCase):
    def test_campaign_requires_real_nontrivial_observations(self) -> None:
        self.assertGreaterEqual(LEVEL7_CAMPAIGN.maintenance_target, 10)
        self.assertGreaterEqual(LEVEL7_CAMPAIGN.recovery_target, 10)
        self.assertGreaterEqual(LEVEL7_CAMPAIGN.no_chat_resume_target, 3)
        self.assertGreaterEqual(LEVEL7_CAMPAIGN.owner_value_pair_target, 30)
        self.assertGreaterEqual(LEVEL7_CAMPAIGN.provider_native_target, 1)
        self.assertFalse(LEVEL7_CAMPAIGN.synthetic_allowed)
        self.assertFalse(LEVEL7_CAMPAIGN.shadow_counts_as_owner_value)


if __name__ == "__main__":
    unittest.main()
