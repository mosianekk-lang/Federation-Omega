from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_current_source_signals_v1 import current_source_signals
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import assess_levels


class KimDataverseLevel7PlusCurrentSourceSignalsTests(unittest.TestCase):
    def test_source_projection_reaches_level6_but_not_level7_without_empirical_evidence(self) -> None:
        levels = assess_levels(current_source_signals())
        by_level = {item.level: item for item in levels}
        self.assertTrue(by_level[5].qualified)
        self.assertTrue(by_level[6].qualified)
        self.assertFalse(by_level[7].qualified)
        self.assertFalse(by_level[8].qualified)

    def test_empirical_level7_flags_are_explicitly_false(self) -> None:
        signals = current_source_signals()
        self.assertFalse(signals["persistent_no_chat_continuity"])
        self.assertFalse(signals["irreducible_owner_interruptions_only"])
        self.assertFalse(signals["verified_value_retention"])
        self.assertFalse(signals["lane_local_failure_isolation"])


if __name__ == "__main__":
    unittest.main()
