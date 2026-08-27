import unittest

from ao_harmonic_v3.behavioral_convergence import (
    BehavioralConvergenceEngine,
    BehavioralConvergenceState,
    BehavioralOrigin,
)
from ao_harmonic_v3.event_bus import EventBus
from ao_harmonic_v3.failure_win_v2 import RecoveryRoute
from ao_harmonic_v3.models import FederationEvent, PerformanceVector


class FailureWinV2BehavioralConvergenceAirlockTests(unittest.TestCase):
    def _route(self):
        return RecoveryRoute(
            route_id="governed-pr-readmission",
            route_type="GOVERNED_REENTRY",
            performance=PerformanceVector(
                quality=5,
                reliability=6,
                proof=6,
                speed=5,
                owner_time_recovered=2,
                recovery_gain=2,
            ),
            proof_strength=1.0,
            reversibility=1.0,
            strategic_value=1.0,
        )

    def _real_provenance_failure(self):
        return FederationEvent(
            event_id="AIRLOCK-33037638447",
            event_type="FAILURE",
            source="Federation Omega",
            workstream="SOURCE_PROVENANCE",
            idempotency_key="AIRLOCK-33037638447",
            timestamp="2026-08-27T03:52:35Z",
            proof_class="PROVIDER_READBACK",
            payload={
                "behavioral_origin": "REAL_PROVIDER",
                "objective": "Keep current source admitted through governed provenance",
                "claim": "Current main should pass source provenance admission",
                "observed_fruit": "UNADMITTED_HISTORY after direct-main commit",
                "desired_outcome": "PR-governed admitted successor with exact readback",
                "failure_code": "SOURCE_PROVENANCE_UNADMITTED_DIRECT_MAIN",
                "provider": "github",
                "route_id": "direct-main-push",
                "material": True,
                "provider_dependent": True,
                "current": True,
                "independent_readback": True,
                "proof_refs": (
                    "github:airlock:33037638447",
                    "github:commit:ec7cbc9f1a5c0ae9fd6355852c9c4e2918620d43",
                    "source-provenance:4bc4068a8dc94f7998e33b6a947e92957f2292d2af7f6cae7de876c3ee08d2c1",
                ),
            },
        )

    def test_real_provider_failure_enters_behavior_proof_without_self_promotion(self):
        engine = BehavioralConvergenceEngine()
        result = engine.observe_federation_event(
            self._real_provenance_failure(),
            incumbent=PerformanceVector(quality=5, reliability=5, proof=5, speed=1),
            routes=(self._route(),),
            provider_dependent=True,
        )
        self.assertEqual(result.state, BehavioralConvergenceState.BEHAVIOR_PROOF_OPEN)
        self.assertTrue(result.empirical_failure_seen)
        self.assertFalse(result.behavior_proven)
        self.assertEqual(result.kernel_result["state"], "ROUTE_SELECTED")
        self.assertIn("FAILURE_FIRST_TEST", result.kernel_result["proof_graph"]["missing_nodes"])

    def test_event_bus_can_drive_engine_and_synthetic_fixture_stays_non_empirical(self):
        engine = BehavioralConvergenceEngine()
        bus = EventBus()
        bus.subscribe("FAILURE", engine.observe_federation_event)
        event = self._real_provenance_failure()
        synthetic = FederationEvent(
            **{
                **event.__dict__,
                "event_id": "AIRLOCK-SYNTHETIC",
                "idempotency_key": "AIRLOCK-SYNTHETIC",
                "payload": {**event.payload, "behavioral_origin": BehavioralOrigin.SYNTHETIC_TEST.value},
            }
        )
        results = bus.emit(synthetic)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].state, BehavioralConvergenceState.INVOCATION_ONLY_NON_EMPIRICAL)
        self.assertFalse(results[0].behavior_proven)

    def test_duplicate_event_bus_delivery_is_exactly_once(self):
        engine = BehavioralConvergenceEngine()
        bus = EventBus()
        bus.subscribe("FAILURE", engine.observe_federation_event)
        event = self._real_provenance_failure()
        first = bus.emit(event)
        second = bus.emit(event)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(engine.ledger_snapshot()), 1)


if __name__ == "__main__":
    unittest.main()
