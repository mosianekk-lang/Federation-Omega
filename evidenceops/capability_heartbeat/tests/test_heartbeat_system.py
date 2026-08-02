from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from evidenceops.capability_heartbeat.engine import HeartbeatError
from evidenceops.capability_heartbeat.foundation.errors import FreshnessError, ReplayError, SignatureError
from evidenceops.capability_heartbeat.system import EvidenceOpsHeartbeatSystem
from evidenceops.capability_heartbeat.tests.integration_helpers import (
    EXPIRES,
    MISSION,
    NOW,
    ROOT_TX,
    TRACE,
    authority,
    envelope,
    observation,
)


ROOT = Path(__file__).resolve().parents[3]
SURFACES = ROOT / "evidenceops/capability_heartbeat/surface_registry.json"


class HeartbeatSystemIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.authority = authority()
        self.system = EvidenceOpsHeartbeatSystem(
            Path(self.temp.name) / "heartbeat.db",
            repository_root=ROOT,
            authority=self.authority,
        )
        self.registry = self.system.load_surface_registry(SURFACES)
        self.index = self.system.index_surfaces(self.registry, observed_at=NOW)

    def tearDown(self):
        self.system.close()
        self.temp.cleanup()

    def signed_event(self, signed, **changes):
        value = {
            "schema": "EVIDENCEOPS-CHAT-TURN-EVENT-2",
            "event_id": "EVENT-SYNTHETIC-ONE",
            "surface_id": "evidenceops",
            "sequence": signed.sequence,
            "observed_at": NOW,
            "destination_node_id": "NODE-EVIDENCEOPS",
            "envelope_id": signed.envelope_id,
            "idempotency_key": signed.idempotency_key,
        }
        value.update(changes)
        return value

    def test_surface_and_scheduler_paths_are_inventory_only(self):
        self.assertEqual(self.index["surface_count"], len(self.registry["surfaces"]))
        before = self.system.conn.execute(
            "SELECT SUM(attempt_count) FROM adapter_cases"
        ).fetchone()[0]
        report = self.system.remediation_cycle(observed_at=NOW)
        after = self.system.conn.execute(
            "SELECT SUM(attempt_count) FROM adapter_cases"
        ).fetchone()[0]
        self.assertTrue(report["inventory_only"])
        self.assertFalse(report["scheduler_authority"])
        self.assertTrue(all(not item["automatic_action_allowed"] for item in report["cases"]))
        self.assertEqual(before, after)

    def test_signed_turn_is_atomic_idempotent_and_destination_receipted(self):
        _, result, signed = envelope(self.authority)
        first = self.system.ingest_turn(self.signed_event(signed), lineage=(signed,))
        second = self.system.ingest_turn(self.signed_event(signed), lineage=(signed,))
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["response"]["authority_source"], "VERIFIED_V4_FOUNDATION")
        self.assertEqual(first["response"]["authority_ceiling"], "A0")
        self.assertEqual(first["signed_destination_receipt"]["envelope_id"], signed.envelope_id)
        self.assertEqual(len(self.system.outbox("NODE-ROOT")), 1)
        self.assertEqual(
            first["response"]["recommendations"],
            [
                {
                    "role": item.role.value,
                    "capability_code": item.capability_code,
                    "score": item.score,
                    "blocker_code": item.blocker_code.value,
                }
                for item in result.recommendations
            ],
        )

    def test_operation_id_replay_with_changed_full_payload_fails(self):
        _, _, first = envelope(self.authority)
        self.system.ingest_turn(self.signed_event(first), lineage=(first,))
        _, second = self.authority.build_root_envelope(
            observations=(observation(code="CAP-OTHER"),),
            now="2026-08-02T12:00:01Z",
            expires_at=EXPIRES,
            trace_id=TRACE,
            root_transaction_id=ROOT_TX,
            mission_code=MISSION,
            sequence=1,
        )
        with self.assertRaisesRegex(ReplayError, "TURN_OPERATION_IDEMPOTENCY_CONFLICT"):
            self.system.ingest_turn(self.signed_event(second), lineage=(second,))

    def test_forged_signature_fails_closed(self):
        _, _, signed = envelope(self.authority)
        forged = replace(signed, signature="hmac-sha256:" + "0" * 64)
        with self.assertRaises(SignatureError):
            self.system.ingest_turn(self.signed_event(forged), lineage=(forged,))

    def test_future_envelope_fails_closed(self):
        _, future = self.authority.build_root_envelope(
            observations=(observation(),),
            now="2026-08-02T12:00:50Z",
            expires_at="2026-08-02T12:05:00Z",
            trace_id=TRACE,
            root_transaction_id=ROOT_TX,
            mission_code=MISSION,
            sequence=1,
        )
        with self.assertRaises(FreshnessError):
            self.system.ingest_turn(self.signed_event(future), lineage=(future,))

    def test_raw_turn_content_and_static_fixture_are_rejected(self):
        _, _, signed = envelope(self.authority)
        with self.assertRaisesRegex(HeartbeatError, "raw or unknown"):
            self.system.ingest_turn(
                self.signed_event(signed, task_summary="raw task"), lineage=(signed,)
            )
        fixture = json.loads(
            (ROOT / "evidenceops/capability_heartbeat/current_turn_event.json").read_text(encoding="utf-8")
        )
        with self.assertRaises(HeartbeatError):
            self.system.ingest_turn(fixture, lineage=(signed,))

    def test_unhosted_or_catalogue_available_surface_cannot_authorize_ingress(self):
        _, _, signed = envelope(self.authority)
        with self.assertRaisesRegex(HeartbeatError, "unhosted or catalogue-only"):
            self.system.ingest_turn(
                self.signed_event(signed, surface_id="chatgpt"), lineage=(signed,)
            )

    def test_reconciliation_does_not_infer_live_chat_awareness(self):
        _, _, signed = envelope(self.authority)
        self.system.ingest_turn(self.signed_event(signed), lineage=(signed,))
        report = self.system.reconcile(observed_at="2026-08-02T13:00:00Z")
        self.assertEqual(report["stale_count"], 1)
        self.assertEqual(report["active_count"], 0)
        self.assertFalse(report["adapter_remediation"]["scheduler_authority"])

    def test_connector_seed_never_persists_raw_result_summary(self):
        seed = self.system.seed_connector(
            chat_id="NODE-ROOT",
            connector_id="CONNECTOR-GOOGLE-DRIVE",
            privacy_tier="P1",
            created_at=NOW,
        )
        self.system.record_connector_cycle(
            seed_id=seed["seed_id"], operation_id="OP-ONE", phase="PRE",
            capability="CAP-DRIVESEARCH", status="AUTHORIZED", created_at=NOW,
        )
        post = self.system.record_connector_cycle(
            seed_id=seed["seed_id"], operation_id="OP-ONE", phase="POST",
            capability="CAP-DRIVESEARCH", status="SUCCESS", result_summary="raw result",
            created_at="2026-08-02T12:00:11Z",
        )
        self.assertIsNone(post["result_summary"])
        self.assertNotIn("raw result", json.dumps(post))
        self.assertTrue(post["result_ref"].startswith("sha256:"))

    def test_signed_sequence_gap_is_sync_pending_and_replay_is_rejected(self):
        _, _, first = envelope(self.authority)
        self.system.ingest_turn(self.signed_event(first), lineage=(first,))
        _, third = self.authority.build_root_envelope(
            observations=(observation(),),
            now="2026-08-02T12:00:02Z",
            expires_at=EXPIRES,
            trace_id=TRACE,
            root_transaction_id=ROOT_TX,
            mission_code=MISSION,
            sequence=3,
        )
        gap = self.system.ingest_turn(
            self.signed_event(
                third, event_id="EVENT-SYNTHETIC-THREE", observed_at="2026-08-02T12:00:12Z"
            ),
            lineage=(third,),
        )
        self.assertEqual(gap["node_state"], "NODE_SYNC_PENDING")
        self.assertEqual(gap["response"]["sequence_gap"], 1)
        with self.assertRaises(ReplayError):
            self.system.ingest_turn(
                self.signed_event(
                    first, event_id="EVENT-SYNTHETIC-REPLAY", observed_at="2026-08-02T12:00:13Z"
                ),
                lineage=(first,),
            )

    def test_connector_post_requires_committed_pre_event(self):
        seed = self.system.seed_connector(
            chat_id="NODE-ROOT", connector_id="CONNECTOR-GOOGLE-DRIVE",
            privacy_tier="P2", created_at=NOW,
        )
        with self.assertRaisesRegex(HeartbeatError, "POST requires"):
            self.system.record_connector_cycle(
                seed_id=seed["seed_id"], operation_id="OP-MISSING-PRE", phase="POST",
                capability="CAP-DRIVESEARCH", status="SUCCESS", result_summary="raw result",
                created_at="2026-08-02T12:00:11Z",
            )

    def test_p1_signed_storage_contains_no_raw_chat_or_task_fields(self):
        _, _, signed = envelope(self.authority)
        self.system.ingest_turn(self.signed_event(signed), lineage=(signed,))
        payload = self.system.conn.execute(
            "SELECT payload_json FROM turn_events"
        ).fetchone()["payload_json"]
        self.assertNotIn("task_summary", payload)
        self.assertNotIn("chat_id", payload)
        self.assertNotIn("message", payload)
        self.assertIn('"raw_content_included":false', payload)


if __name__ == "__main__":
    unittest.main()
