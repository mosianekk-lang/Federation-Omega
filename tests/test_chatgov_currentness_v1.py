from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.currentness import (
    CURRENT,
    REFRESH_REQUIRED,
    CurrentnessDecision,
    CurrentnessRecord,
    resolve_currentness,
)
from bubbles.chat_governor_omega3.routing import MissionPlan
from bubbles.chat_governor_omega3.runtime import ConnectorGateway
from bubbles.chat_governor_omega3.state import DurableState


MISSION = "mission-currentness"
SUBJECT = "GITHUB_MAIN"
NOW = "2026-09-05T22:05:00+02:00"


def record(
    projection_id: str,
    *,
    observed_at: str,
    expires_at: str,
    event_valid: bool = True,
    source_epoch_valid: bool = True,
    provider_readback_valid: bool = True,
    mission_id: str = MISSION,
    subject: str = SUBJECT,
) -> CurrentnessRecord:
    return CurrentnessRecord(
        projection_id=projection_id,
        mission_id=mission_id,
        subject=subject,
        state="CURRENT_LOOKING_PERSISTED_LABEL",
        observed_at=observed_at,
        expires_at=expires_at,
        source_ref="provider:readback",
        stale_action="FRESH_GITHUB_MAIN",
        event_valid=event_valid,
        source_epoch_valid=source_epoch_valid,
        provider_readback_valid=provider_readback_valid,
    )


def mission_plan() -> MissionPlan:
    return MissionPlan(
        mission_id=MISSION,
        objective="resolve current provider source",
        mission_type="software_build",
        active_specialists=["Bubbles"],
        active_connectors=["GitHub"],
        excluded_connectors=[],
        retrieval_budget=3,
        tool_result_token_budget=2048,
        max_parallel_lanes=4,
        created_at=NOW,
    )


class CurrentnessResolverTests(unittest.TestCase):
    def test_exact_expiry_is_refresh_required_even_when_persisted_label_looks_current(self) -> None:
        decision = resolve_currentness(
            [record("p1", observed_at="2026-09-05T22:00:00+02:00", expires_at=NOW)],
            mission_id=MISSION,
            subject=SUBJECT,
            now=NOW,
        )
        self.assertEqual(REFRESH_REQUIRED, decision.state)
        self.assertFalse(decision.reusable)
        self.assertIn("p1:EXPIRED", decision.reasons)

    def test_newest_eligible_unexpired_row_wins_over_newer_expired_history(self) -> None:
        decision = resolve_currentness(
            [
                record("new-expired", observed_at="2026-09-05T22:04:00+02:00", expires_at=NOW),
                record("older-valid", observed_at="2026-09-05T22:03:00+02:00", expires_at="2026-09-05T22:06:00+02:00"),
            ],
            mission_id=MISSION,
            subject=SUBJECT,
            now=NOW,
        )
        self.assertEqual(CURRENT, decision.state)
        self.assertEqual("older-valid", decision.projection_id)
        self.assertTrue(decision.reusable)

    def test_event_source_and_provider_invalidations_precede_ttl(self) -> None:
        rows = [
            record("event", observed_at="2026-09-05T22:04:30+02:00", expires_at="2026-09-05T22:10:00+02:00", event_valid=False),
            record("source", observed_at="2026-09-05T22:04:20+02:00", expires_at="2026-09-05T22:10:00+02:00", source_epoch_valid=False),
            record("provider", observed_at="2026-09-05T22:04:10+02:00", expires_at="2026-09-05T22:10:00+02:00", provider_readback_valid=False),
        ]
        decision = resolve_currentness(rows, mission_id=MISSION, subject=SUBJECT, now=NOW)
        self.assertEqual(REFRESH_REQUIRED, decision.state)
        reasons = "|".join(decision.reasons)
        self.assertIn("EVENT_INVALIDATED", reasons)
        self.assertIn("SOURCE_EPOCH_INVALID", reasons)
        self.assertIn("PROVIDER_READBACK_INVALID", reasons)

    def test_lookup_is_exact_mission_plus_subject_not_subject_only(self) -> None:
        decision = resolve_currentness(
            [record("other", observed_at="2026-09-05T22:04:00+02:00", expires_at="2026-09-05T22:10:00+02:00", mission_id="other-mission")],
            mission_id=MISSION,
            subject=SUBJECT,
            now=NOW,
        )
        self.assertEqual(REFRESH_REQUIRED, decision.state)
        self.assertEqual(("NO_MATCHING_CURRENTNESS_RECORD",), decision.reasons)

    def test_naive_timestamp_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "OFFSET_AWARE"):
            resolve_currentness(
                [record("p1", observed_at="2026-09-05T22:00:00", expires_at="2026-09-05T22:10:00+02:00")],
                mission_id=MISSION,
                subject=SUBJECT,
                now=NOW,
            )


class ConnectorGatewayCurrentnessTests(unittest.TestCase):
    def test_current_receipt_reuses_but_stale_decision_forces_safe_read_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = DurableState(str(Path(td) / "state.sqlite3"))
            gateway = ConnectorGateway(state)
            plan = mission_plan()
            calls: list[int] = []
            current = resolve_currentness(
                [record("fresh", observed_at="2026-09-05T22:04:00+02:00", expires_at="2026-09-05T22:10:00+02:00")],
                mission_id=MISSION,
                subject=SUBJECT,
                now=NOW,
            )

            def provider_read():
                calls.append(1)
                return {"sha": f"v{len(calls)}", "semantic": "ok"}

            first = gateway.execute(
                plan=plan,
                connector="GitHub",
                action="read-main",
                target="refs/heads/main",
                fn=provider_read,
                semantic_check=lambda payload: payload["semantic"] == "ok",
                source_version="epoch-1",
                effect_class="READ_ONLY",
                currentness=current,
            )
            second = gateway.execute(
                plan=plan,
                connector="GitHub",
                action="read-main",
                target="refs/heads/main",
                fn=provider_read,
                semantic_check=lambda payload: payload["semantic"] == "ok",
                source_version="epoch-1",
                effect_class="READ_ONLY",
                currentness=current,
            )
            stale = resolve_currentness(
                [record("expired", observed_at="2026-09-05T22:00:00+02:00", expires_at=NOW)],
                mission_id=MISSION,
                subject=SUBJECT,
                now=NOW,
            )
            third = gateway.execute(
                plan=plan,
                connector="GitHub",
                action="read-main",
                target="refs/heads/main",
                fn=provider_read,
                semantic_check=lambda payload: payload["semantic"] == "ok",
                source_version="epoch-1",
                effect_class="READ_ONLY",
                currentness=stale,
            )

            self.assertFalse(first["reused"])
            self.assertTrue(second["reused"])
            self.assertFalse(third["reused"])
            self.assertTrue(third["currentness_refresh_performed"])
            self.assertEqual(2, len(calls))

    def test_stale_currentness_blocks_non_read_handler_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = DurableState(str(Path(td) / "state.sqlite3"))
            gateway = ConnectorGateway(state)
            calls: list[int] = []
            stale = CurrentnessDecision(
                state=REFRESH_REQUIRED,
                mission_id=MISSION,
                subject=SUBJECT,
                projection_id="expired",
                stale_action="FRESH_PROVIDER_READBACK",
                reasons=("EXPIRED",),
            )
            with self.assertRaisesRegex(RuntimeError, "CURRENTNESS_REFRESH_REQUIRED_BEFORE_NON_READ"):
                gateway.execute(
                    plan=mission_plan(),
                    connector="GitHub",
                    action="write-like-test",
                    target="resource",
                    fn=lambda: calls.append(1) or {"ok": True},
                    effect_class="BOUNDED_EFFECT",
                    currentness=stale,
                    retry_attempts=1,
                )
            self.assertEqual([], calls)

    def test_currentness_mission_mismatch_fails_before_handler(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = DurableState(str(Path(td) / "state.sqlite3"))
            gateway = ConnectorGateway(state)
            decision = CurrentnessDecision(state=CURRENT, mission_id="wrong", subject=SUBJECT)
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_MISSION_MISMATCH"):
                gateway.execute(
                    plan=mission_plan(),
                    connector="GitHub",
                    action="read",
                    target="resource",
                    fn=lambda: {"ok": True},
                    effect_class="READ_ONLY",
                    currentness=decision,
                )


if __name__ == "__main__":
    unittest.main()
