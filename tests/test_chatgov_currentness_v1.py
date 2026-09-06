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
from bubbles.chat_governor_omega3.hosted_provider_readback_v1 import (
    HOST_CURRENTNESS_SUBJECT,
    HostedProviderReadbackAdapter,
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
    source_ref: str = "provider:readback",
) -> CurrentnessRecord:
    return CurrentnessRecord(
        projection_id=projection_id,
        mission_id=mission_id,
        subject=subject,
        state="CURRENT_LOOKING_PERSISTED_LABEL",
        observed_at=observed_at,
        expires_at=expires_at,
        source_ref=source_ref,
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


def provider_payload() -> dict:
    return {
        "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
        "mutation_attempted": False,
        "secret_values_recorded": False,
        "surfaces": {},
        "surface_corrections": {
            "archon_apps_script_exact_deployment": {
                "schema": "BUBBLES-ARCHON-APPS-SCRIPT-DEPLOYMENT-PROBE-V1",
                "mutation_attempted": False,
                "credential_values_recorded": False,
            }
        },
    }


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
                plan=plan, connector="GitHub", action="read-main", target="refs/heads/main",
                fn=provider_read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="epoch-1", effect_class="READ_ONLY",
                currentness=current, currentness_subject=SUBJECT,
            )
            second = gateway.execute(
                plan=plan, connector="GitHub", action="read-main", target="refs/heads/main",
                fn=provider_read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="epoch-1", effect_class="READ_ONLY",
                currentness=current, currentness_subject=SUBJECT,
            )
            stale = resolve_currentness(
                [record("expired", observed_at="2026-09-05T22:00:00+02:00", expires_at=NOW)],
                mission_id=MISSION, subject=SUBJECT, now=NOW,
            )
            third = gateway.execute(
                plan=plan, connector="GitHub", action="read-main", target="refs/heads/main",
                fn=provider_read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="epoch-1", effect_class="READ_ONLY",
                currentness=stale, currentness_subject=SUBJECT,
            )
            self.assertFalse(first["reused"])
            self.assertTrue(second["reused"])
            self.assertFalse(third["reused"])
            self.assertTrue(third["currentness_refresh_performed"])
            self.assertEqual(SUBJECT, third["currentness_subject"])
            self.assertEqual(2, len(calls))

    def test_changed_provider_anchor_cannot_reuse_old_durable_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            calls: list[int] = []

            def read():
                calls.append(1)
                return {"semantic": "ok", "version": len(calls)}

            epoch1 = CurrentnessDecision(
                state=CURRENT, mission_id=MISSION, subject=SUBJECT,
                projection_id="p1", source_ref="provider:epoch-1",
            )
            epoch2 = CurrentnessDecision(
                state=CURRENT, mission_id=MISSION, subject=SUBJECT,
                projection_id="p2", source_ref="provider:epoch-2",
            )
            first = gateway.execute(
                plan=mission_plan(), connector="GitHub", action="read", target="resource",
                fn=read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="same-source-code", effect_class="READ_ONLY",
                currentness=epoch1, currentness_subject=SUBJECT,
            )
            same = gateway.execute(
                plan=mission_plan(), connector="GitHub", action="read", target="resource",
                fn=read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="same-source-code", effect_class="READ_ONLY",
                currentness=epoch1, currentness_subject=SUBJECT,
            )
            changed = gateway.execute(
                plan=mission_plan(), connector="GitHub", action="read", target="resource",
                fn=read, semantic_check=lambda p: p["semantic"] == "ok",
                source_version="same-source-code", effect_class="READ_ONLY",
                currentness=epoch2, currentness_subject=SUBJECT,
            )
            self.assertFalse(first["reused"])
            self.assertTrue(same["reused"])
            self.assertFalse(changed["reused"])
            self.assertNotEqual(first["idempotency_key"], changed["idempotency_key"])
            self.assertEqual(2, len(calls))

    def test_currentness_requires_explicit_expected_subject(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            decision = CurrentnessDecision(
                state=CURRENT, mission_id=MISSION, subject=SUBJECT,
                projection_id="p1", source_ref="provider:epoch-1",
            )
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_SUBJECT_REQUIRED"):
                gateway.execute(
                    plan=mission_plan(), connector="GitHub", action="read", target="resource",
                    fn=lambda: {"ok": True}, effect_class="READ_ONLY", currentness=decision,
                )

    def test_wrong_subject_fails_before_handler(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            calls: list[int] = []
            decision = CurrentnessDecision(
                state=CURRENT, mission_id=MISSION, subject="OTHER_SUBJECT",
                projection_id="p1", source_ref="provider:epoch-1",
            )
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_SUBJECT_MISMATCH"):
                gateway.execute(
                    plan=mission_plan(), connector="GitHub", action="read", target="resource",
                    fn=lambda: calls.append(1) or {"ok": True}, effect_class="READ_ONLY",
                    currentness=decision, currentness_subject=SUBJECT,
                )
            self.assertEqual([], calls)

    def test_reusable_decision_requires_provider_or_projection_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            decision = CurrentnessDecision(state=CURRENT, mission_id=MISSION, subject=SUBJECT)
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_REUSE_ANCHOR_REQUIRED"):
                gateway.execute(
                    plan=mission_plan(), connector="GitHub", action="read", target="resource",
                    fn=lambda: {"ok": True}, effect_class="READ_ONLY",
                    currentness=decision, currentness_subject=SUBJECT,
                )

    def test_stale_currentness_blocks_non_read_handler_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            calls: list[int] = []
            stale = CurrentnessDecision(
                state=REFRESH_REQUIRED, mission_id=MISSION, subject=SUBJECT,
                projection_id="expired", stale_action="FRESH_PROVIDER_READBACK",
                reasons=("EXPIRED",),
            )
            with self.assertRaisesRegex(RuntimeError, "CURRENTNESS_REFRESH_REQUIRED_BEFORE_NON_READ"):
                gateway.execute(
                    plan=mission_plan(), connector="GitHub", action="write-like-test", target="resource",
                    fn=lambda: calls.append(1) or {"ok": True}, effect_class="BOUNDED_EFFECT",
                    currentness=stale, currentness_subject=SUBJECT, retry_attempts=1,
                )
            self.assertEqual([], calls)

    def test_currentness_mission_mismatch_fails_before_handler(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            gateway = ConnectorGateway(DurableState(str(Path(td) / "state.sqlite3")))
            decision = CurrentnessDecision(
                state=CURRENT, mission_id="wrong", subject=SUBJECT,
                projection_id="p1", source_ref="provider:epoch-1",
            )
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_MISSION_MISMATCH"):
                gateway.execute(
                    plan=mission_plan(), connector="GitHub", action="read", target="resource",
                    fn=lambda: {"ok": True}, effect_class="READ_ONLY",
                    currentness=decision, currentness_subject=SUBJECT,
                )


class HostedProviderCurrentnessBindingTests(unittest.TestCase):
    HOST_MISSION = "MISSION-FUSE-BUBBLES-HOST-ADOPTER-20260905-001"

    def _decision(self, *, anchor: str, subject: str = HOST_CURRENTNESS_SUBJECT) -> CurrentnessDecision:
        return CurrentnessDecision(
            state=CURRENT, mission_id=self.HOST_MISSION, subject=subject,
            projection_id="host-current", source_ref=anchor,
        )

    def test_missing_supplier_fails_toward_real_provider_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = str(Path(td) / "host.sqlite3")
            calls: list[int] = []

            def reader():
                calls.append(1)
                return provider_payload()

            _, receipt1 = HostedProviderReadbackAdapter(
                state_path=state_path, source_version="source-1",
                mission_currentness_ref="DOCUMENTARY_ONLY",
            ).execute(reader)
            _, receipt2 = HostedProviderReadbackAdapter(
                state_path=state_path, source_version="source-1",
                mission_currentness_ref="DOCUMENTARY_ONLY",
            ).execute(reader)
            self.assertEqual(2, len(calls))
            self.assertFalse(receipt1["currentness_supplier_bound"])
            self.assertFalse(receipt2["currentness_supplier_bound"])
            self.assertFalse(receipt2["chatgov_gateway"]["results"][0]["reused"])
            self.assertTrue(receipt2["chatgov_gateway"]["results"][0]["currentness_refresh_performed"])
            self.assertFalse(receipt2["mission_currentness_ref_authoritative"])

    def test_fresh_same_anchor_reuses_but_changed_anchor_executes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = str(Path(td) / "host.sqlite3")
            calls: list[int] = []

            def reader():
                calls.append(1)
                return provider_payload()

            epoch1 = lambda: self._decision(anchor="provider:epoch-1")
            epoch2 = lambda: self._decision(anchor="provider:epoch-2")
            _, first = HostedProviderReadbackAdapter(
                state_path=state_path, source_version="source-1",
                mission_currentness_ref="DOC", currentness_supplier=epoch1,
            ).execute(reader)
            _, same = HostedProviderReadbackAdapter(
                state_path=state_path, source_version="source-1",
                mission_currentness_ref="DOC", currentness_supplier=epoch1,
            ).execute(reader)
            _, changed = HostedProviderReadbackAdapter(
                state_path=state_path, source_version="source-1",
                mission_currentness_ref="DOC", currentness_supplier=epoch2,
            ).execute(reader)
            self.assertEqual(2, len(calls))
            self.assertFalse(first["chatgov_gateway"]["results"][0]["reused"])
            self.assertTrue(same["chatgov_gateway"]["results"][0]["reused"])
            self.assertFalse(changed["chatgov_gateway"]["results"][0]["reused"])
            self.assertNotEqual(
                same["chatgov_gateway"]["results"][0]["idempotency_key"],
                changed["chatgov_gateway"]["results"][0]["idempotency_key"],
            )

    def test_wrong_host_subject_fails_before_provider_reader(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            calls: list[int] = []
            adapter = HostedProviderReadbackAdapter(
                state_path=str(Path(td) / "host.sqlite3"), source_version="source-1",
                mission_currentness_ref="DOC",
                currentness_supplier=lambda: self._decision(anchor="provider:epoch-1", subject="WRONG"),
            )
            with self.assertRaisesRegex(ValueError, "CURRENTNESS_SUBJECT_MISMATCH"):
                adapter.execute(lambda: calls.append(1) or provider_payload())
            self.assertEqual([], calls)

    def test_missing_supplier_refresh_is_still_singleflight_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            calls: list[int] = []
            adapter = HostedProviderReadbackAdapter(
                state_path=str(Path(td) / "host.sqlite3"), source_version="source-1",
                mission_currentness_ref="DOC",
            )

            def reader():
                calls.append(1)
                return provider_payload()

            _, receipt = adapter.execute(reader, prove_singleflight=True)
            self.assertEqual(1, len(calls))
            self.assertTrue(receipt["singleflight_proof"]["verified"])
            self.assertFalse(receipt["currentness_supplier_bound"])
            self.assertEqual(REFRESH_REQUIRED, receipt["currentness_decision"]["state"])


if __name__ == "__main__":
    unittest.main()
