from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_system_entropy_v1 import EntropyAction, SystemShape, entropy_summary, evaluate_system_entropy


class KimDataverseSystemEntropyTests(unittest.TestCase):
    def test_high_overlap_systems_are_merge_review_not_auto_merged(self) -> None:
        decisions = evaluate_system_entropy(
            (
                SystemShape("a", ("schedule", "retry", "state"), False, False, False, False, 3, True),
                SystemShape("b", ("schedule", "retry", "state"), False, False, False, False, 2, True),
            )
        )
        self.assertTrue(all(item.action == EntropyAction.MERGE_REVIEW for item in decisions))
        self.assertTrue(all(not item.destructive_action_authorized for item in decisions))

    def test_permanent_low_value_agent_becomes_dynamic_role_review(self) -> None:
        decision = evaluate_system_entropy(
            (
                SystemShape("agent", ("review",), False, False, False, False, 1, False, permanent_agent=True),
                SystemShape("other", ("execute",), False, False, False, False, 3, True),
            )
        )[0]
        self.assertEqual(EntropyAction.CONVERT_TO_DYNAMIC_ROLE_REVIEW, decision.action)

    def test_unused_system_is_retirement_review_only(self) -> None:
        decisions = evaluate_system_entropy(
            (
                SystemShape("unused", ("old",), False, False, False, False, 0, False),
                SystemShape("active", ("new",), False, False, False, False, 5, True),
            )
        )
        by_id = {item.system_id: item for item in decisions}
        self.assertEqual(EntropyAction.RETIRE_REVIEW, by_id["unused"].action)
        self.assertFalse(by_id["unused"].destructive_action_authorized)

    def test_duplicate_control_plane_shape_is_policy_conversion_review(self) -> None:
        decisions = evaluate_system_entropy(
            (
                SystemShape("dup-plane", ("special",), True, True, False, False, 4, True),
                SystemShape("other", ("other",), False, False, False, False, 4, True),
            )
        )
        by_id = {item.system_id: item for item in decisions}
        self.assertEqual(EntropyAction.CONVERT_TO_POLICY_REVIEW, by_id["dup-plane"].action)

    def test_distinct_valuable_system_is_retained(self) -> None:
        decisions = evaluate_system_entropy(
            (
                SystemShape("sol", ("authority", "state"), False, False, False, True, 10, True),
                SystemShape("sovara", ("provider", "readback"), False, False, True, False, 10, True),
            )
        )
        self.assertTrue(all(item.action == EntropyAction.RETAIN for item in decisions))
        summary = entropy_summary(decisions)
        self.assertEqual(2, summary["RETAIN"])


if __name__ == "__main__":
    unittest.main()
