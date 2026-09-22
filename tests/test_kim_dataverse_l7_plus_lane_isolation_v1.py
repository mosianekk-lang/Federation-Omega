from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_lane_isolation_v1 import WorkLane, WorkLaneState, executable_lanes


class KimDataverseLevel7PlusLaneIsolationTests(unittest.TestCase):
    def test_blocked_provider_lane_does_not_freeze_independent_ready_lane(self) -> None:
        lanes = (
            WorkLane("google", WorkLaneState.BLOCKED, blocker_scope="WIF"),
            WorkLane("phoenix", WorkLaneState.READY),
        )
        self.assertEqual(("phoenix",), executable_lanes(lanes))

    def test_dependency_on_blocked_lane_is_held_but_other_lane_continues(self) -> None:
        lanes = (
            WorkLane("google", WorkLaneState.BLOCKED),
            WorkLane("dependent", WorkLaneState.READY, dependencies=("google",)),
            WorkLane("independent", WorkLaneState.READY),
        )
        self.assertEqual(("independent",), executable_lanes(lanes))

    def test_unknown_dependency_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            executable_lanes((WorkLane("a", WorkLaneState.READY, dependencies=("missing",)),))


if __name__ == "__main__":
    unittest.main()
