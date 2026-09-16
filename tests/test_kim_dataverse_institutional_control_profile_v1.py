from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_institutional_control_profile_v1 import default_profile


class KimDataverseInstitutionalControlProfileTests(unittest.TestCase):
    def test_profile_has_one_authority_plane_and_no_new_duplicate_control_planes(self) -> None:
        profile = default_profile()
        self.assertEqual(1, profile.authority_planes)
        self.assertEqual(0, profile.new_scheduler_planes)
        self.assertEqual(0, profile.new_memory_roots)
        self.assertEqual(0, profile.new_provider_executors)
        self.assertFalse(profile.external_effect_authorized)
        self.assertEqual("SOL 6.2", profile.constitutional_kernel)


if __name__ == "__main__":
    unittest.main()
