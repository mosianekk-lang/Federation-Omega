from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_autonomic_control_fabric_v1 import AutonomicEvent, EventClass
from benchmarking.cfbe_omega.kim_dataverse_institutional_bridge_v1 import compile_institutional_snapshot, snapshot_truth_boundary
from benchmarking.cfbe_omega.kim_dataverse_institutional_twin_v1 import CapabilityHealth, CapabilityObservation
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import MaturityState, Objective
from benchmarking.cfbe_omega.kim_dataverse_level8_frontier_v1 import InformationRoute, TimescaleObjective


class KimDataverseInstitutionalBridgeTests(unittest.TestCase):
    def test_snapshot_composes_existing_controls_without_execution_authority(self) -> None:
        snapshot = compile_institutional_snapshot(
            objectives=(Objective("o1", 5, 5, required_capabilities=("cap",)),),
            events=(AutonomicEvent("e1", EventClass.MISSION, "lane", True, True),),
            capabilities=(
                CapabilityObservation(
                    "cap",
                    "a" * 40,
                    MaturityState.TESTED,
                    CapabilityHealth.HEALTHY,
                    ("proof:cap",),
                ),
            ),
        )
        self.assertFalse(snapshot.execution_authorized)
        self.assertFalse(snapshot.external_effect_authorized)
        boundary = snapshot_truth_boundary(snapshot)
        self.assertEqual("INSTITUTIONAL_CONTROL_SNAPSHOT_ONLY", boundary["truth"])

    def test_frontier_plan_is_optional_and_non_authorizing(self) -> None:
        snapshot = compile_institutional_snapshot(
            objectives=(Objective("o1", 1, 1),),
            events=(),
            capabilities=(),
            frontier_objectives=(TimescaleObjective("o1", "NOW", 1, 1, 1, 0),),
            information_routes=(InformationRoute("read", 1, 1, 0, 0),),
        )
        self.assertIsNotNone(snapshot.frontier_plan)
        self.assertFalse(snapshot.frontier_plan.external_effect_authorized)

    def test_unknown_objective_dependency_still_fails_closed_through_bridge(self) -> None:
        with self.assertRaises(ValueError):
            compile_institutional_snapshot(
                objectives=(Objective("o1", 1, 1, dependencies=("missing",)),),
                events=(),
                capabilities=(),
            )


if __name__ == "__main__":
    unittest.main()
