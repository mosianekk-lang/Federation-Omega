from pathlib import Path
import copy
import json
import sqlite3
import tempfile
import unittest

from federation_omega_v2 import EventStore, CanonicalQueryService, import_canonical_register
from federation_omega_v2.matter_adapter import (
    MatterControlSnapshot,
    evaluate_claims,
    import_matter,
    load_snapshot,
    run_phase3_mission,
)


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "state.sqlite"
        self.store = EventStore(self.db)
        self.root = Path(__file__).parents[2]
        self.snapshot = load_snapshot(self.root / "MATTER_CONTROL_SNAPSHOT.json")
        self.register = json.loads((self.root / "CANONICAL_SYSTEM_REGISTER.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_snapshot_valid(self):
        self.snapshot.validate()

    def test_02_counts_reconcile(self):
        state = self.snapshot.data["processing_state"]
        self.assertEqual(state["processed_units"] + state["remaining_units"], state["registered_units"])

    def test_03_duplicate_source_rejected(self):
        data = copy.deepcopy(self.snapshot.data)
        data["source_controls"].append(copy.deepcopy(data["source_controls"][0]))
        with self.assertRaises(ValueError):
            MatterControlSnapshot(data).validate()

    def test_04_external_effect_rejected(self):
        data = copy.deepcopy(self.snapshot.data)
        data["external_effects_allowed"] = True
        with self.assertRaises(ValueError):
            MatterControlSnapshot(data).validate()

    def test_05_send_state_rejected(self):
        data = copy.deepcopy(self.snapshot.data)
        data["communication_state"] = "SEND"
        with self.assertRaises(ValueError):
            MatterControlSnapshot(data).validate()

    def test_06_raw_field_rejected(self):
        data = copy.deepcopy(self.snapshot.data)
        data["message_body"] = "not allowed"
        with self.assertRaises(ValueError):
            MatterControlSnapshot(data).validate()

    def test_07_import_matter(self):
        import_canonical_register(self.store, self.register)
        result = import_matter(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(result["event"]["state"], "APPENDED")
        self.assertEqual(len(result["relationships"]), 4)

    def test_08_import_idempotent(self):
        import_matter(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        result = import_matter(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(result["event"]["state"], "IDEMPOTENT_REPLAY")

    def test_09_case_wall(self):
        wall = self.snapshot.data["case_wall"]
        self.assertIn("MPMB298-26", wall["separated_from"])
        self.assertEqual(wall["linked_source_extensions"][0]["matter"], "MPMB1435-26")

    def test_10_claim_hold_retaliation(self):
        self.assertEqual(evaluate_claims(self.snapshot, ["retaliation"])["held"][0]["state"], "CONFLICT_HELD_UNPROVEN")

    def test_11_claim_hold_causation(self):
        self.assertEqual(len(evaluate_claims(self.snapshot, ["causation"])["held"]), 1)

    def test_12_neutral_claim_accepted(self):
        self.assertEqual(len(evaluate_claims(self.snapshot, ["thirty registered units are processed"])["accepted"]), 1)

    def test_13_phase3_stage_count(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(result["stage_count"], 10)

    def test_14_phase3_zero_effects(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(result["external_effects"], 0)

    def test_15_no_raw_evidence(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertFalse(result["raw_evidence_imported"])

    def test_16_readiness_matches(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertTrue(result["readiness_comparison"]["match"])
        self.assertEqual(result["readiness_comparison"]["generated"], "NOT_COMPLETE")

    def test_17_owner_brief_generated(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(result["owner_brief"]["remaining"], 24)

    def test_18_restart_reconstructs_mission(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        projection = EventStore(self.db).project(result["mission"]["mission_id"])
        self.assertEqual(len(projection["state"]["stages"]), 10)

    def test_19_hash_chain_verifies(self):
        run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(self.store.verify()["quick_check"], "ok")

    def test_20_tamper_detected(self):
        result = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("UPDATE events SET payload='{}' WHERE entity_id=?", (result["mission"]["mission_id"],))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ValueError):
            self.store.verify()

    def test_21_four_charges(self):
        self.assertEqual(len(self.snapshot.data["charge_controls"]), 4)

    def test_22_five_evidence_streams(self):
        self.assertEqual(len(self.snapshot.data["evidence_streams"]), 5)

    def test_23_open_gaps_preserved(self):
        self.assertIn("EMPLOYER_BUNDLE_AND_EXCULPATORY_RECORDS", self.snapshot.data["open_gaps"])

    def test_24_completion_not_claimed(self):
        self.assertEqual(self.snapshot.data["processing_state"]["completion_state"], "NOT_COMPLETE")

    def test_25_matter_query(self):
        import_matter(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(CanonicalQueryService(self.store).system(self.snapshot.matter_id)["proof_state"], "READBACK_VERIFIED")

    def test_26_phase3_rerun_idempotent(self):
        first = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        second = run_phase3_mission(self.store, self.snapshot, "2026-08-04T19:46:00+00:00")
        self.assertEqual(first["mission"]["mission_id"], second["mission"]["mission_id"])
        self.assertEqual(self.store.project(first["mission"]["mission_id"])["event_count"], 10)


if __name__ == "__main__":
    unittest.main()
