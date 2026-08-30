from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from omega_one.transaction_store import (
    IdempotencyReservationConflict,
    InjectedStorageFault,
    LegacyMigrationError,
    SQLiteStateStore,
    StateRevisionConflict,
    canonical_digest,
)


def blank():
    return {
        "missions": {}, "tasks": {}, "workers": {}, "leases": {}, "fences": {},
        "dispatch_counts": {}, "effects": {}, "permits": {}, "certificates": {}, "events": [],
    }


def event(kind: str, previous: str = "GENESIS"):
    row = {"type": kind, "body": {"value": kind}, "at": "2026-08-30T00:00:00Z", "previous": previous}
    row["hash"] = canonical_digest(row)
    return row


class TransactionStoreTests(unittest.TestCase):
    def test_schema_one_database_migrates_to_schema_two_without_state_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control-state.sqlite3"
            store = SQLiteStateStore(path)
            state = blank()
            state["missions"]["M1"] = {"version": 1}
            store.commit(state, expected_revision=0)
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version=1")
            connection.execute("UPDATE metadata SET value='1' WHERE key='schema_version'")
            connection.commit()
            connection.close()

            migrated = SQLiteStateStore(path)
            loaded, revision = migrated.load(blank())
            self.assertEqual(migrated.status()["schema_version"], 2)
            self.assertEqual(revision, 1)
            self.assertEqual(loaded["missions"], state["missions"])

    def test_incremental_commit_updates_only_changed_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1, "state": "ACTIVE"}
            state["events"].append(event("MISSION_SUBMITTED"))
            first = store.commit(state, expected_revision=0)
            self.assertEqual((first.rows_upserted, first.events_appended), (1, 1))

            state["dispatch_counts"]["alpha"] = 1
            second = store.commit(state, expected_revision=1)
            self.assertEqual(second.rows_upserted, 1)
            self.assertEqual(second.rows_deleted, 0)
            self.assertEqual(second.events_appended, 0)
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 2)
            self.assertEqual(loaded["missions"]["M1"]["version"], 1)
            self.assertEqual(loaded["dispatch_counts"], {"alpha": 1})

    def test_exception_before_commit_rolls_back_every_change(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1}
            store.commit(state, expected_revision=0)
            state["missions"]["M2"] = {"version": 1}
            with self.assertRaisesRegex(InjectedStorageFault, "INJECTED_BEFORE_COMMIT"):
                store.commit(state, expected_revision=1, fault_at="before_commit")
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 1)
            self.assertNotIn("M2", loaded["missions"])
            self.assertTrue(store.verify_integrity())

    def test_legacy_migration_is_hash_bound_one_time_and_source_preserving(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "control-state.json"
            state = blank()
            state["dispatch_counts"] = {"alpha": 7}
            state["events"] = [event("LEGACY")]
            legacy.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            original = legacy.read_bytes()
            store = SQLiteStateStore(root / "control-state.sqlite3")
            receipt = store.migrate_legacy(legacy, blank())
            self.assertIsNotNone(receipt)
            self.assertEqual(legacy.read_bytes(), original)
            self.assertIsNone(store.migrate_legacy(legacy, blank()))
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 1)
            self.assertEqual(loaded["dispatch_counts"], {"alpha": 7})
            self.assertEqual(store.status()["migrations"][0]["source_sha256"], receipt["source_sha256"])

    def test_invalid_legacy_json_fails_closed_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "control-state.json"
            legacy.write_bytes(b'{"missions":')
            original = legacy.read_bytes()
            store = SQLiteStateStore(root / "control-state.sqlite3")
            with self.assertRaisesRegex(LegacyMigrationError, "LEGACY_JSON_INVALID"):
                store.migrate_legacy(legacy, blank())
            self.assertEqual(legacy.read_bytes(), original)
            self.assertEqual(store.current_revision(), 0)

    def test_integrity_detects_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control-state.sqlite3"
            store = SQLiteStateStore(path)
            state = blank()
            state["missions"]["M1"] = {"version": 1}
            store.commit(state, expected_revision=0)
            connection = sqlite3.connect(path)
            connection.execute("UPDATE state_rows SET payload_json='{}' WHERE collection='missions'")
            connection.commit()
            connection.close()
            self.assertFalse(store.verify_integrity())

    def test_online_backup_restores_identical_semantic_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SQLiteStateStore(root / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1, "state": "ACTIVE"}
            store.commit(state, expected_revision=0)
            receipt = store.backup_to(root / "backup.sqlite3")
            restored = SQLiteStateStore(receipt["path"])
            restored_state, restored_revision = restored.load(blank())
            self.assertTrue(receipt["integrity_valid"])
            self.assertEqual(restored_revision, 1)
            self.assertEqual(restored_state["missions"], state["missions"])

    def test_revision_fencing_serializes_contending_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control-state.sqlite3"
            first = SQLiteStateStore(path, timeout_seconds=2)
            second = SQLiteStateStore(path, timeout_seconds=2)
            barrier = threading.Barrier(2)
            outcomes = []
            lock = threading.Lock()

            def writer(store, mission_id):
                state = blank()
                state["missions"][mission_id] = {"version": 1}
                barrier.wait()
                try:
                    store.commit(state, expected_revision=0)
                    result = "COMMITTED"
                except StateRevisionConflict:
                    result = "FENCED"
                with lock:
                    outcomes.append(result)

            threads = [
                threading.Thread(target=writer, args=(first, "M1")),
                threading.Thread(target=writer, args=(second, "M2")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["COMMITTED", "FENCED"])
            loaded, revision = first.load(blank())
            self.assertEqual(revision, 1)
            self.assertEqual(len(loaded["missions"]), 1)

    def test_reservation_conflict_rolls_back_state_and_outbox(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1}
            store.commit(
                state,
                expected_revision=0,
                reservations=[{"idempotency_key": "shared", "task_key": "M1:v1:A", "mission_id": "M1", "mission_version": 1}],
            )
            state["missions"]["M2"] = {"version": 1}
            with self.assertRaisesRegex(IdempotencyReservationConflict, "IDEMPOTENCY_KEY_CONFLICT"):
                store.commit(
                    state,
                    expected_revision=1,
                    reservations=[{"idempotency_key": "shared", "task_key": "M2:v1:B", "mission_id": "M2", "mission_version": 1}],
                    outbox={"outbox_id": "admission:M2:v1", "mission_id": "M2", "mission_version": 1, "payload": {"mission": "M2"}},
                )
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 1)
            self.assertNotIn("M2", loaded["missions"])
            self.assertEqual(store.pending_outbox(), [])

    def test_outbox_failure_is_recoverable_and_idempotently_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            store.commit(
                state,
                expected_revision=0,
                outbox={"outbox_id": "admission:M1:v1", "mission_id": "M1", "mission_version": 1, "payload": {"mission": "M1"}},
            )
            self.assertEqual(len(store.pending_outbox()), 1)
            first_claim = store.claim_outbox("test-claim-1")
            self.assertEqual(first_claim["outbox_id"], "admission:M1:v1")
            store.mark_outbox_failed("admission:M1:v1", "test-claim-1", "simulated interruption")
            self.assertEqual(store.pending_outbox()[0]["attempts"], 1)
            second_claim = store.claim_outbox("test-claim-2")
            self.assertEqual(second_claim["attempts"], 1)
            store.mark_outbox_applied("admission:M1:v1", "test-claim-2")
            store.mark_outbox_applied("admission:M1:v1", "test-claim-2")
            self.assertEqual(store.pending_outbox(), [])
            self.assertEqual(store.status()["pending_outbox"], 0)

    def test_transition_outbox_is_atomic_recoverable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1}
            receipt = store.commit(
                state,
                expected_revision=0,
                transition_outbox={
                    "transition_id": "dispatch:test-wave",
                    "transition_kind": "DISPATCH_WAVE",
                    "mission_id": "M1",
                    "mission_version": 1,
                    "payload": {"lease_seconds": 60, "assignments": []},
                },
            )
            self.assertEqual(receipt.transition_outbox_added, 1)
            self.assertEqual(store.status()["pending_transition_outbox"], 1)
            claimed = store.claim_transition("transition-test")
            self.assertEqual(claimed["transition_id"], "dispatch:test-wave")
            store.mark_transition_failed("dispatch:test-wave", "transition-test", "injected")
            self.assertEqual(store.pending_transitions()[0]["attempts"], 1)
            claimed = store.claim_transition("transition-retry")
            store.mark_transition_applied("dispatch:test-wave", "transition-retry")
            store.mark_transition_applied("dispatch:test-wave", "transition-retry")
            self.assertEqual(store.pending_transitions(), [])
            self.assertEqual(store.status()["pending_outbox"], 0)

    def test_claimed_transition_and_control_state_finalize_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            state["missions"]["M1"] = {"version": 1, "state": "ACTIVE"}
            store.commit(
                state,
                expected_revision=0,
                transition_outbox={
                    "transition_id": "proof-finalize:M1:v1:A",
                    "transition_kind": "PROOF_FINALIZATION",
                    "mission_id": "M1",
                    "mission_version": 1,
                    "payload": {"binding": "one"},
                },
            )
            claimed = store.claim_transition("proof-claim")
            state["certificates"]["M1:v1:A"] = {"certificate_id": "cert-one"}
            store.commit(
                state,
                expected_revision=1,
                applied_transition={
                    "transition_id": claimed["transition_id"],
                    "claim_token": "proof-claim",
                },
            )
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 2)
            self.assertEqual(loaded["certificates"]["M1:v1:A"]["certificate_id"], "cert-one")
            self.assertEqual(store.pending_transitions(), [])

    def test_transition_acknowledgement_fence_rolls_back_state_on_wrong_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            store.commit(
                state,
                expected_revision=0,
                transition_outbox={
                    "transition_id": "proof-finalize:M1:v1:A",
                    "transition_kind": "PROOF_FINALIZATION",
                    "mission_id": "M1",
                    "mission_version": 1,
                    "payload": {"binding": "one"},
                },
            )
            store.claim_transition("right-claim")
            state["missions"]["M1"] = {"state": "PROVEN"}
            with self.assertRaisesRegex(Exception, "TRANSITION_APPLY_TARGET_MISSING"):
                store.commit(
                    state,
                    expected_revision=1,
                    applied_transition={
                        "transition_id": "proof-finalize:M1:v1:A",
                        "claim_token": "wrong-claim",
                    },
                )
            loaded, revision = store.load(blank())
            self.assertEqual(revision, 1)
            self.assertNotIn("M1", loaded["missions"])

    def test_transition_id_replay_rejects_changed_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(Path(directory) / "control-state.sqlite3")
            state = blank()
            transition = {
                "transition_id": "proof-finalize:M1:v1:A",
                "transition_kind": "PROOF_FINALIZATION",
                "mission_id": "M1",
                "mission_version": 1,
                "payload": {"output_digest": "first", "fencing_token": 1},
            }
            store.commit(state, expected_revision=0, transition_outbox=transition)
            changed = dict(transition)
            changed["payload"] = {"output_digest": "changed", "fencing_token": 1}
            with self.assertRaisesRegex(Exception, "TRANSITION_OUTBOX_ID_CONFLICT"):
                store.commit(state, expected_revision=1, transition_outbox=changed)
            self.assertEqual(store.current_revision(), 1)
            self.assertEqual(store.pending_transitions()[0]["payload"]["output_digest"], "first")


if __name__ == "__main__":
    unittest.main()
