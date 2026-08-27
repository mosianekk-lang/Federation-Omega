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
from formation_omega.powerhouse import FormationOmega, ProofState, SurfaceReadback


class FormationOmegaFailureWinV2ReceiverCanaryTests(unittest.TestCase):
    def test_formation_native_proof_and_surface_gate_then_v2_canary(self) -> None:
        decision = FormationOmega.claim_decision(ProofState.VERIFIED, ProofState.CONTESTED)
        self.assertTrue(decision.downgraded)
        self.assertEqual(ProofState.CONTESTED, decision.permitted)

        verified = SurfaceReadback(
            surface="GitHub",
            expected_semantics="formation-omega@1.0",
            observed_semantics="formation-omega@1.0",
            authority_verified=True,
            target_verified=True,
            version_verified=True,
        )
        stale = SurfaceReadback(
            surface="ProviderRuntime",
            expected_semantics="formation-omega@1.0",
            observed_semantics=None,
            authority_verified=False,
            target_verified=True,
            version_verified=False,
        )
        self.assertTrue(FormationOmega.surface_harmonized(verified))
        self.assertFalse(FormationOmega.all_surfaces_harmonized((verified, stale)))

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
                    event_id="FWV2-FORMATION-OMEGA-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="FORMATION-OMEGA Unified Powerhouse",
                    objective="preempt a synthetic cross-surface harmonisation drift risk",
                    claim="one surface may appear harmonized without exact local readback",
                    observed_fruit="synthetic control-plane evidence only; no provider effect",
                    desired_outcome="prewarm a current proof/readback-bounded formation route",
                    failure_code="SYNTHETIC_FORMATION_SURFACE_DRIFT",
                    material=False,
                    precursor_signals=("surface-readback-fixture", "claim-ceiling-fixture"),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="formation-current-readback-fixture",
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
