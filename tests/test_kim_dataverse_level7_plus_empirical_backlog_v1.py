from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_empirical_backlog_v1 import BacklogClass, default_empirical_backlog


class KimDataverseLevel7PlusEmpiricalBacklogTests(unittest.TestCase):
    def test_phoenix_repair_is_top_autopilot_work_not_owner_task(self) -> None:
        backlog = default_empirical_backlog()
        self.assertEqual("repair-current-phoenix", backlog[0].item_id)
        self.assertEqual(BacklogClass.AUTOPILOT, backlog[0].backlog_class)
        self.assertFalse(backlog[0].owner_action_required)

    def test_only_wif_hardening_is_explicit_owner_action_in_default_backlog(self) -> None:
        owner = [item for item in default_empirical_backlog() if item.owner_action_required]
        self.assertEqual(1, len(owner))
        self.assertEqual("harden-google-wif", owner[0].item_id)

    def test_owner_value_collection_is_autonomous_evidence_collection_not_owner_task(self) -> None:
        item = next(item for item in default_empirical_backlog() if item.item_id == "collect-owner-value-pairs")
        self.assertEqual(BacklogClass.VALUE, item.backlog_class)
        self.assertFalse(item.owner_action_required)


if __name__ == "__main__":
    unittest.main()
