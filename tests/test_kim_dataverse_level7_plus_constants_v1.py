from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_constants_v1 import (
    LEVEL7_MAX_AVOIDABLE_OWNER_INTERRUPTION_RATE,
    LEVEL7_MIN_MAINTENANCE_EPISODES,
    LEVEL7_MIN_MAINTENANCE_SELF_RESOLUTION_RATE,
    LEVEL7_MIN_NO_CHAT_RESUMES,
    LEVEL7_MIN_OWNER_VALUE_PAIRS,
    LEVEL7_MIN_RECOVERY_EPISODES,
    LEVEL7_MIN_RECOVERY_SELF_RESOLUTION_RATE,
)


class KimDataverseLevel7PlusConstantsTests(unittest.TestCase):
    def test_level7_thresholds_are_nontrivial(self) -> None:
        self.assertGreaterEqual(LEVEL7_MIN_MAINTENANCE_EPISODES, 10)
        self.assertGreaterEqual(LEVEL7_MIN_RECOVERY_EPISODES, 10)
        self.assertGreaterEqual(LEVEL7_MIN_NO_CHAT_RESUMES, 3)
        self.assertGreaterEqual(LEVEL7_MIN_OWNER_VALUE_PAIRS, 30)
        self.assertLessEqual(LEVEL7_MAX_AVOIDABLE_OWNER_INTERRUPTION_RATE, 0.05)
        self.assertGreaterEqual(LEVEL7_MIN_MAINTENANCE_SELF_RESOLUTION_RATE, 0.95)
        self.assertGreaterEqual(LEVEL7_MIN_RECOVERY_SELF_RESOLUTION_RATE, 0.95)


if __name__ == "__main__":
    unittest.main()
