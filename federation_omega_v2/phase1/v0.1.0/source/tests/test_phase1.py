from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from federation_omega_v2 import CanonicalQueryService, Event, EventStore, compile_mission


class Phase1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "state.sqlite"
        self.store = EventStore(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def event(self, event_id="EVT-001", event_type="STATE_SET", payload=None):
        return Event(
            event_id=event_id,
            entity_id="SYS-FEDERATION-OMEGA",
            event_type=event_type,
            occurred_at="2026-08-04T18:00:00+00:00",
            observed_at="2026-08-04T18:00:01+00:00",
            source="SRC-TEST",
            authority="A1",
            payload=payload or {"state": {"status": "ACTIVE", "version": "2.0"}},
        )

    def test_append_and_project(self):
        result = self.store.append(self.event())
        self.assertEqual(result["state"], "APPENDED")
        projection = self.store.project("SYS-FEDERATION-OMEGA")
        self.assertEqual(projection["state"]["status"], "ACTIVE")

    def test_idempotent_replay(self):
        first = self.store.append(self.event())
        second = self.store.append(self.event())
        self.assertEqual(first["event_hash"], second["event_hash"])
        self.assertEqual(second["state"], "IDEMPOTENT_REPLAY")

    def test_conflicting_event_id_fails(self):
        self.store.append(self.event())
        with self.assertRaises(ValueError):
            self.store.append(self.event(payload={"state": {"status": "OTHER"}}))

    def test_hash_chain_verifies(self):
        self.store.append(self.event())
        self.store.append(
            self.event(
                event_id="EVT-002",
                event_type="STATE_PATCH",
                payload={"patch": {"health": "GREEN"}},
            )
        )
        proof = self.store.verify()
        self.assertEqual(proof["quick_check"], "ok")
        self.assertEqual(proof["event_count"], 2)

    def test_tamper_is_detected(self):
        self.store.append(self.event())
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                "UPDATE federation_events SET payload_json=? WHERE event_id=?",
                ('{"state":{"status":"TAMPERED"}}', "EVT-001"),
            )
            connection.commit()
        with self.assertRaises(ValueError):
            self.store.verify()

    def test_patch_projection(self):
        self.store.append(self.event())
        self.store.append(
            self.event(
                event_id="EVT-002",
                event_type="STATE_PATCH",
                payload={"patch": {"proof": "VERIFIED"}},
            )
        )
        self.assertEqual(
            self.store.project("SYS-FEDERATION-OMEGA")["state"]["proof"],
            "VERIFIED",
        )

    def test_status_projection(self):
        self.store.append(
            self.event(
                event_type="STATUS_SET",
                payload={"status": "HELD"},
            )
        )
        self.assertEqual(self.store.project("SYS-FEDERATION-OMEGA")["state"]["status"], "HELD")

    def test_invalid_naive_timestamp_rejected(self):
        bad = Event(
            event_id="EVT-003",
            entity_id="SYS-FEDERATION-OMEGA",
            event_type="STATUS_SET",
            occurred_at="2026-08-04T18:00:00",
            observed_at="2026-08-04T18:00:01+00:00",
            source="SRC-TEST",
            authority="A1",
            payload={"status": "ACTIVE"},
        )
        with self.assertRaises(ValueError):
            self.store.append(bad)

    def test_compiler_is_deterministic(self):
        left = compile_mission("Build the verified Federation world model")
        right = compile_mission("  Build   the verified Federation world model ")
        self.assertEqual(left.mission_id, right.mission_id)
        self.assertEqual(left.contract_sha256, right.contract_sha256)

    def test_compiler_extracts_deadline(self):
        mission = compile_mission("Complete phase one by 2026-08-31 with proof")
        self.assertEqual(mission.deadline, "2026-08-31")

    def test_compiler_rejects_external_effects_at_a1(self):
        with self.assertRaises(ValueError):
            compile_mission(
                "Execute a verified external action",
                authority_ceiling="A1",
                external_effects_allowed=True,
            )

    def test_compiler_defaults_proof_requirements(self):
        mission = compile_mission("Build a verified internal mission contract")
        self.assertIn("Target readback", mission.proof_requirements)

    def test_save_and_query_mission(self):
        mission = compile_mission("Build a canonical mission query service")
        self.store.save_mission(mission.to_dict())
        result = CanonicalQueryService(self.store).mission(mission.mission_id)
        self.assertEqual(result["proof_state"], "READBACK_VERIFIED")

    def test_mission_id_conflict_fails(self):
        mission = compile_mission("Build a canonical mission query service")
        data = mission.to_dict()
        self.store.save_mission(data)
        altered = dict(data)
        altered["contract_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.store.save_mission(altered)

    def test_entity_query_unknown(self):
        result = CanonicalQueryService(self.store).entity("SYS-UNKNOWN")
        self.assertEqual(result["proof_state"], "SOURCE_LOCATED")
        self.assertEqual(result["event_count"], 0)

    def test_route_selection(self):
        service = CanonicalQueryService(self.store)
        self.assertEqual(service.route("Prepare legal evidence")["system"], "EVIDENCEOPS")
        self.assertEqual(service.route("Deploy software")["system"], "FEDERATION-ICT")
        self.assertFalse(service.route("Research trading strategy")["external_effects"])


if __name__ == "__main__":
    unittest.main()
