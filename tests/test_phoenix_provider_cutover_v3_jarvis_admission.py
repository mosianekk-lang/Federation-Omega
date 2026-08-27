from __future__ import annotations

import unittest
from pathlib import Path

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.jarvis_ao5 import JarvisAO5Engine
from ao_harmonic_v3.models import PerformanceVector
from verification.jarvis_ao5_public_safe_canary import build_public_safe_request


ROOT = Path(__file__).resolve().parents[1]


class JarvisAdmissionTests(unittest.TestCase):
    """Bind a focused JARVIS v2 receiver canary to the existing Airlock wildcard.

    This bridge executes the native public-safe JarvisAO5Engine directly and
    then invokes Failure-Win v2 on a synthetic no-effect precursor. Historical
    JARVIS regressions remain source evidence and are not silently converted
    into a new mandatory release gate. No workflow, permission, credential, or
    external authority is added.
    """

    def test_jarvis_native_and_failure_win_v2_invocation(self) -> None:
        native = JarvisAO5Engine().run(build_public_safe_request())
        self.assertEqual(64, len(native.receipt_sha256))
        self.assertFalse(native.truth_boundary["external_effect"])

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
                    event_id="FWV2-JARVIS-AIRLOCK-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="JARVIS",
                    objective="preempt a synthetic assurance-drift risk",
                    claim="a downstream assurance projection may become stale",
                    observed_fruit="synthetic precursor only; no external effect",
                    desired_outcome="prewarm a current fail-closed assurance route",
                    failure_code="SYNTHETIC_JARVIS_ASSURANCE_DRIFT",
                    material=False,
                    precursor_signals=("stale-assurance-fixture", "proof-drift-fixture"),
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

        self.assertEqual("FAILURE-TO-OPERATIONAL-WIN-V2", result.kernel)
        self.assertTrue(result.vector_gate_passed)
        self.assertIn("jarvis-current-assurance-readback-fixture", result.selected_route_ids)
        self.assertFalse(result.proof_graph.complete)
        self.assertNotEqual(FailureWinState.OPERATIONAL_WIN_VERIFIED, result.state)

    def test_native_and_failure_win_sources_are_present(self) -> None:
        required = (
            ROOT / "ao_harmonic_v3" / "jarvis_ao5.py",
            ROOT / "verification" / "jarvis_ao5_public_safe_canary.py",
            ROOT / "ao_harmonic_v3" / "failure_win_v2.py",
        )
        self.assertTrue(all(path.is_file() for path in required))


if __name__ == "__main__":
    unittest.main()
