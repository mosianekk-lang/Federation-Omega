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
from ao_harmonic_v3.jarvis_ao5 import ExecutionState, JarvisAO5Engine
from ao_harmonic_v3.models import PerformanceVector
from verification.jarvis_ao5_public_safe_canary import build_public_safe_request


class JarvisFailureWinV2ReceiverCanaryTests(unittest.TestCase):
    """No-effect v2 invocation canary composed with the native JARVIS suite."""

    def test_jarvis_native_canary_is_healthy_before_failure_win_invocation(self) -> None:
        native = JarvisAO5Engine().run(build_public_safe_request())
        self.assertEqual(ExecutionState.S22_NEXT_ACTION.value, native.execution_state)
        self.assertEqual("PASS", native.replay_state)
        self.assertEqual("PASS", native.semantic_qa["state"])
        self.assertFalse(native.truth_boundary["external_effect"])

    def test_jarvis_precursor_canary_invokes_v2_without_behavior_promotion(self) -> None:
        incumbent = PerformanceVector(
            quality=7,
            reliability=7,
            proof=8,
            speed=2,
            owner_burden=1,
        )
        candidate = PerformanceVector(
            quality=7,
            reliability=7,
            proof=8,
            speed=5,
            owner_time_recovered=2,
            recovery_gain=2,
            owner_burden=0,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-JARVIS-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="JARVIS",
                    objective="preempt a synthetic assurance-drift risk",
                    claim="a downstream assurance projection may become stale",
                    observed_fruit="synthetic precursor only; no external effect",
                    desired_outcome="prewarm a current fail-closed assurance route",
                    failure_code="SYNTHETIC_JARVIS_ASSURANCE_DRIFT",
                    material=False,
                    precursor_signals=("stale-assurance-fixture", "proof-drift-fixture"),
                    recent_route_history=("legacy-assurance-projection-fixture",),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="jarvis-current-assurance-readback-fixture",
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
        self.assertEqual(("jarvis-current-assurance-readback-fixture",), result.prewarm_route_ids)
        self.assertTrue(result.vector_gate_passed)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)


if __name__ == "__main__":
    unittest.main()
