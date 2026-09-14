from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_autonomic_control_fabric_v1 import (
    AutonomicEvent,
    EventClass,
    LaneState,
    compile_autonomic_wave,
    maintenance_incident_from_ci,
    provider_authority_event,
    summarize_wave,
)
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import OwnerBoundary


class KimDataverseAutonomicControlFabricTests(unittest.TestCase):
    def test_phoenix_regression_routes_to_maintenance_without_owner(self) -> None:
        event = maintenance_incident_from_ci(
            run_id="33469890437",
            lane_id="phoenix",
            failure_fingerprint="workflow-free-core-test-leak",
        )
        wave = compile_autonomic_wave((event,))
        decision = wave.decisions[0]
        self.assertEqual(LaneState.DELEGATED, decision.state)
        self.assertEqual("AUTOFIX_BUBBLES_ENGINEERING_TO_PROOFOS", decision.route)
        self.assertFalse(decision.owner_interrupt)
        self.assertFalse(wave.external_effect_authorized)

    def test_provider_authority_hold_does_not_freeze_maintenance_lane(self) -> None:
        events = (
            provider_authority_event(event_id="wif", lane_id="google-provider"),
            maintenance_incident_from_ci(
                run_id="1",
                lane_id="phoenix",
                failure_fingerprint="regression",
            ),
        )
        wave = compile_autonomic_wave(events)
        by_id = {d.event_id: d for d in wave.decisions}
        self.assertEqual(LaneState.OWNER_REQUIRED, by_id["wif"].state)
        self.assertEqual(LaneState.DELEGATED, by_id["ci:1:regression"].state)
        self.assertTrue(wave.independent_lanes_continue)

    def test_mission_evolution_and_recovery_use_distinct_existing_routes(self) -> None:
        events = (
            AutonomicEvent("mission", EventClass.MISSION, "m", True, True),
            AutonomicEvent("evolution", EventClass.EVOLUTION, "e", True, True),
            AutonomicEvent("recovery", EventClass.RECOVERY, "r", True, True),
        )
        wave = compile_autonomic_wave(events)
        routes = {d.route for d in wave.decisions}
        self.assertEqual(3, len(routes))
        self.assertIn("BCO_PRIME_POLICY_MARKET_TO_SOL", routes)
        self.assertIn("CFBE_CHALLENGER_TO_SHADOW_COURT", routes)
        self.assertIn("FAILURE_WIN_SOVARA_OR_LOCAL_RECOVERY", routes)

    def test_duplicate_event_identity_fails_closed(self) -> None:
        event = AutonomicEvent("same", EventClass.MISSION, "m", True, True)
        with self.assertRaises(ValueError):
            compile_autonomic_wave((event, event))

    def test_unscoped_external_effect_never_becomes_delegated(self) -> None:
        event = AutonomicEvent(
            "effect",
            EventClass.MAINTENANCE,
            "lane",
            True,
            True,
            external_effect=True,
            owner_boundary=OwnerBoundary.NONE,
        )
        decision = compile_autonomic_wave((event,)).decisions[0]
        self.assertEqual(LaneState.OWNER_REQUIRED, decision.state)
        self.assertTrue(decision.owner_interrupt)

    def test_wave_receipt_is_deterministic_and_non_authorizing(self) -> None:
        event = maintenance_incident_from_ci(
            run_id="7",
            lane_id="phoenix",
            failure_fingerprint="abc",
        )
        first = compile_autonomic_wave((event,))
        second = compile_autonomic_wave((event,))
        self.assertEqual(first.receipt(), second.receipt())
        self.assertFalse(summarize_wave(first)["external_effect_authorized"])


if __name__ == "__main__":
    unittest.main()
