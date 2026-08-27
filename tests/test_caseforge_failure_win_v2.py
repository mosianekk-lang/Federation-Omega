from __future__ import annotations

import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from evidenceops.caseforge.federation_autonomous_controller import AutonomousRegressionPlanner
from evidenceops.caseforge.federation_evolution_runtime import FailureMemoryEntry


class CaseforgeFailureWinV2ReceiverCanaryTests(unittest.TestCase):
    def test_caseforge_native_regression_planner_and_v2_canary(self) -> None:
        failure = FailureMemoryEntry(
            "STALE_BASE_HEAD_REJECTED",
            "RECUT_CURRENT_MAIN",
            "FWV2-CASEFORGE-CANARY",
        )
        regression = AutonomousRegressionPlanner().from_failure(failure)
        self.assertIn("recut from current main", regression.expected_behavior)
        self.assertIn("weaken ancestry", regression.prohibited_behavior)

        incumbent = PerformanceVector(quality=8, reliability=8, proof=9, speed=2, owner_burden=1)
        candidate = PerformanceVector(
            quality=8,
            reliability=8,
            proof=9,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
            owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-CASEFORGE-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="CASEFORGE-Ω",
                    objective="preempt a synthetic evolution-regression drift risk",
                    claim="a known failure class may recur without a bound regression",
                    observed_fruit="synthetic failure-memory contract only; no provider effect",
                    desired_outcome="prewarm a current failure-derived regression route",
                    failure_code="SYNTHETIC_CASEFORGE_REGRESSION_DRIFT",
                    material=False,
                    precursor_signals=("failure-memory-fixture", "regression-fixture"),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="caseforge-current-regression-fixture",
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                        expected_value=2.0,
                    ),
                ),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
