from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from federation.bubbles_digital_twin_state import (
    BubblesDigitalTwinState,
    MissionEpisodeObservation,
    OwnerBurdenObservation,
    OwnerPreferenceObservation,
)
from federation.living_state.store import LivingStateStore


T1 = "2026-08-31T18:00:00+02:00"
T2 = "2026-08-31T18:05:00+02:00"
T3 = "2026-08-31T18:10:00+02:00"


class BubblesDigitalTwinStateTests(unittest.TestCase):
    def test_latest_observed_preference_wins_without_rewriting_history(self) -> None:
        twin = BubblesDigitalTwinState()
        first = twin.observe_preference(
            OwnerPreferenceObservation(
                key="completion mode",
                value="ask often",
                observed_at=T1,
                proof_ref="proof:owner-choice-1",
            )
        )
        second = twin.observe_preference(
            OwnerPreferenceObservation(
                key="completion mode",
                value="continue safe work",
                observed_at=T2,
                proof_ref="proof:owner-choice-2",
            )
        )

        self.assertEqual(first.node_id, second.node_id)
        projection = twin.projection(now=T2)
        self.assertEqual("continue safe work", projection["preferences"]["completion mode"])
        self.assertEqual(1, projection["preference_count"])
        self.assertEqual(2, projection["event_count"])
        self.assertTrue(projection["event_chain_valid"])

    def test_mission_episode_and_owner_burden_are_measured_separately(self) -> None:
        twin = BubblesDigitalTwinState()
        twin.observe_mission_episode(
            MissionEpisodeObservation(
                mission_id="mission-1",
                objective="close a bounded build",
                state="VERIFIED_COMPLETE",
                observed_at=T1,
                proof_ref="proof:mission-1",
                outcome_ref="artifact:mission-1",
                accepted=True,
                cycle_time_seconds=120.0,
                owner_intervention_seconds=10.0,
                clarification_count=1,
            )
        )
        twin.observe_owner_burden(
            OwnerBurdenObservation(
                mission_id="mission-1",
                observed_at=T2,
                proof_ref="proof:burden-1",
                intervention_seconds=10.0,
                clarification_count=1,
                correction_count=0,
            )
        )

        projection = twin.projection(now=T2)
        self.assertEqual(1, projection["mission_count"])
        self.assertEqual(1, projection["accepted_outcomes"])
        self.assertEqual(1, projection["burden_observation_count"])
        self.assertEqual(10.0, projection["owner_intervention_seconds"])
        self.assertEqual(1, projection["clarification_count"])
        self.assertEqual(0, projection["correction_count"])
        self.assertEqual(0, projection["external_effects"])

    def test_negative_owner_burden_fails_closed(self) -> None:
        twin = BubblesDigitalTwinState()
        with self.assertRaisesRegex(
            ValueError, "OWNER_INTERVENTION_SECONDS_NON_NEGATIVE_REQUIRED"
        ):
            twin.observe_owner_burden(
                OwnerBurdenObservation(
                    mission_id="mission-1",
                    observed_at=T1,
                    proof_ref="proof:burden-negative",
                    intervention_seconds=-1.0,
                )
            )

    def test_durable_multi_snapshot_seal_restore_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "living-state.sqlite"
            twin = BubblesDigitalTwinState()
            with LivingStateStore(path) as store:
                twin.observe_preference(
                    OwnerPreferenceObservation(
                        key="creative focus",
                        value="protect routine execution time",
                        observed_at=T1,
                        proof_ref="proof:preference-1",
                    )
                )
                first = twin.seal(store, now=T1)
                self.assertTrue(first.store_readback_verified)
                self.assertEqual(1, first.event_count)
                self.assertEqual(0, first.external_effects)

                twin.observe_mission_episode(
                    MissionEpisodeObservation(
                        mission_id="mission-2",
                        objective="prove multi-snapshot state",
                        state="DETERMINISTIC_TESTED",
                        observed_at=T2,
                        proof_ref="proof:mission-2",
                    )
                )
                second = twin.seal(store, now=T2)
                self.assertTrue(second.store_readback_verified)
                self.assertEqual(2, second.event_count)
                self.assertNotEqual(second.snapshot_sha256, first.snapshot_sha256)

                latest = store.latest_snapshot(fabric_id="BUBBLES_DIGITAL_TWIN")
                self.assertIsNotNone(latest)
                assert latest is not None
                self.assertEqual(second.snapshot_sha256, latest["snapshot_sha256"])
                self.assertEqual(2, latest["event_count"])

                restored = BubblesDigitalTwinState.restore(store)
                restored_projection = restored.projection(now=T2)
                self.assertEqual(1, restored_projection["preference_count"])
                self.assertEqual(1, restored_projection["mission_count"])
                self.assertEqual(2, restored_projection["event_count"])
                self.assertTrue(restored_projection["event_chain_valid"])

    def test_three_snapshots_preserve_monotonic_event_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "living-state.sqlite"
            twin = BubblesDigitalTwinState()
            with LivingStateStore(path) as store:
                twin.observe_preference(
                    OwnerPreferenceObservation(
                        key="autonomy",
                        value="bounded",
                        observed_at=T1,
                        proof_ref="proof:p1",
                    )
                )
                r1 = twin.seal(store, now=T1)

                twin.observe_owner_burden(
                    OwnerBurdenObservation(
                        mission_id="mission-3",
                        observed_at=T2,
                        proof_ref="proof:b1",
                        intervention_seconds=4.0,
                    )
                )
                r2 = twin.seal(store, now=T2)

                twin.observe_preference(
                    OwnerPreferenceObservation(
                        key="autonomy",
                        value="bounded-safe-continuation",
                        observed_at=T3,
                        proof_ref="proof:p2",
                    )
                )
                r3 = twin.seal(store, now=T3)

                self.assertEqual([1, 2, 3], [r1.event_count, r2.event_count, r3.event_count])
                self.assertEqual(3, len({r1.snapshot_sha256, r2.snapshot_sha256, r3.snapshot_sha256}))
                restored = BubblesDigitalTwinState.restore(store)
                self.assertTrue(restored.model.verify_event_chain())
                self.assertEqual(
                    "bounded-safe-continuation",
                    restored.projection(now=T3)["preferences"]["autonomy"],
                )


if __name__ == "__main__":
    unittest.main()
