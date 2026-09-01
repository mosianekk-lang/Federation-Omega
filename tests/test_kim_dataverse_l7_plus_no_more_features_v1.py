from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_no_more_features_v1 import FEATURE_GROWTH_ALLOWED_DURING_ADMISSION


class KimDataverseLevel7PlusNoMoreFeaturesTests(unittest.TestCase):
    def test_feature_growth_is_disabled_during_admission(self) -> None:
        self.assertFalse(FEATURE_GROWTH_ALLOWED_DURING_ADMISSION)


if __name__ == "__main__":
    unittest.main()
