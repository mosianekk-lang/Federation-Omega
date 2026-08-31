from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

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


def test_latest_observed_preference_wins_without_rewriting_history() -> None:
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

    assert first.node_id == second.node_id
    projection = twin.projection(now=T2)
    assert projection["preferences"]["completion mode"] == "continue safe work"
    assert projection["preference_count"] == 1
    assert projection["event_count"] == 2
    assert projection["event_chain_valid"] is True


def test_mission_episode_and_owner_burden_are_measured_separately() -> None:
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
    assert projection["mission_count"] == 1
    assert projection["accepted_outcomes"] == 1
    assert projection["burden_observation_count"] == 1
    assert projection["owner_intervention_seconds"] == 10.0
    assert projection["clarification_count"] == 1
    assert projection["correction_count"] == 0
    assert projection["external_effects"] == 0


def test_negative_owner_burden_fails_closed() -> None:
    twin = BubblesDigitalTwinState()
    with pytest.raises(ValueError, match="OWNER_INTERVENTION_SECONDS_NON_NEGATIVE_REQUIRED"):
        twin.observe_owner_burden(
            OwnerBurdenObservation(
                mission_id="mission-1",
                observed_at=T1,
                proof_ref="proof:burden-negative",
                intervention_seconds=-1.0,
            )
        )


def test_durable_multi_snapshot_seal_restore_and_readback() -> None:
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
            assert first.store_readback_verified is True
            assert first.event_count == 1
            assert first.external_effects == 0

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
            assert second.store_readback_verified is True
            assert second.event_count == 2
            assert second.snapshot_sha256 != first.snapshot_sha256

            latest = store.latest_snapshot(fabric_id="BUBBLES_DIGITAL_TWIN")
            assert latest is not None
            assert latest["snapshot_sha256"] == second.snapshot_sha256
            assert latest["event_count"] == 2

            restored = BubblesDigitalTwinState.restore(store)
            restored_projection = restored.projection(now=T2)
            assert restored_projection["preference_count"] == 1
            assert restored_projection["mission_count"] == 1
            assert restored_projection["event_count"] == 2
            assert restored_projection["event_chain_valid"] is True


def test_three_snapshots_preserve_monotonic_event_history() -> None:
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

            assert [r1.event_count, r2.event_count, r3.event_count] == [1, 2, 3]
            assert len({r1.snapshot_sha256, r2.snapshot_sha256, r3.snapshot_sha256}) == 3
            restored = BubblesDigitalTwinState.restore(store)
            assert restored.model.verify_event_chain() is True
            assert restored.projection(now=T3)["preferences"]["autonomy"] == "bounded-safe-continuation"
