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


class CFBEFailureWinV2ReceiverCanaryTests(unittest.TestCase):
    """Exercise Failure-Win v2 inside the existing CFBE Airlock host.

    This is a deterministic no-effect receiver invocation canary. It must not
    be interpreted as real benchmark recovery, provider execution, soak, or
    behavioral completion.
    """

    def test_cfbe_precursor_canary_invokes_v2_without_self_promotion(self) -> None:
        incumbent = PerformanceVector(
            quality=6,
            reliability=6,
            proof=6,
            speed=1,
            owner_burden=1,
        )
        candidate = PerformanceVector(
            quality=6,
            reliability=6,
            proof=6,
            speed=4,
            owner_time_recovered=2,
            recovery_gain=2,
            owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-CFBE-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="CFBE-Ω",
                    objective="preempt a synthetic benchmark telemetry-staleness risk",
                    claim="a benchmark lane may become stale before the next decision",
                    observed_fruit="synthetic precursor only; no provider effect",
                    desired_outcome="prewarm a current, reversible benchmark readback route",
                    failure_code="SYNTHETIC_CFBE_STALENESS_PRECURSOR",
                    material=False,
                    precursor_signals=("stale-telemetry-fixture", "zero-denominator-fixture"),
                    recent_route_history=("legacy-stale-snapshot-fixture",),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="cfbe-refresh-current-readback-fixture",
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                        expected_value=2.0,
                        expected_cost=0.0,
                        expected_risk=0.0,
                    ),
                ),
            )
        )

        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertEqual(("cfbe-refresh-current-readback-fixture",), result.prewarm_route_ids)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)

    def test_cfbe_host_canary_requires_real_followup_before_behavior_proof(self) -> None:
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-CFBE-NO-EFFECT-HOLD",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="CFBE-Ω",
                    objective="hold receiver maturity at the proven scope",
                    claim="hosted invocation is not operational behavior proof",
                    observed_fruit="deterministic test result only",
                    desired_outcome="require real failure-derived proof and soak",
                    failure_code="SYNTHETIC_CFBE_PROOF_BOUNDARY",
                    material=False,
                    precursor_signals=("proof-boundary-fixture",),
                )
            )
        )
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
