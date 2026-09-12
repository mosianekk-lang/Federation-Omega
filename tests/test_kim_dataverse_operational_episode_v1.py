from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_operational_episode_v1 import OperationalEpisode, validate_operational_episode


class KimDataverseOperationalEpisodeTests(unittest.TestCase):
    def test_clean_episode_compiles_evidence_receipt(self) -> None:
        episode = OperationalEpisode("e", "m", "a" * 40, True, True, True, True, False, False, True, ("proof",))
        receipt = validate_operational_episode(episode)
        self.assertTrue(receipt.startswith("sha256:"))

    def test_avoidable_owner_interruption_is_rejected_for_level7_episode(self) -> None:
        episode = OperationalEpisode("e", "m", "a" * 40, True, True, True, True, True, False, True, ("proof",))
        with self.assertRaises(ValueError):
            validate_operational_episode(episode)

    def test_irreducible_owner_interruption_is_admissible(self) -> None:
        episode = OperationalEpisode("e", "m", "a" * 40, True, True, True, True, True, True, True, ("proof",))
        self.assertTrue(validate_operational_episode(episode).startswith("sha256:"))

    def test_verified_complete_without_proof_fails_closed(self) -> None:
        episode = OperationalEpisode("e", "m", "a" * 40, True, True, True, True, False, False, True, ())
        with self.assertRaises(ValueError):
            validate_operational_episode(episode)


if __name__ == "__main__":
    unittest.main()
