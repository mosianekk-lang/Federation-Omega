from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from federation.living_state.store import LivingStateStore
from federation.living_state.world_model import (
    FabricError, LivingWorldModel, NodeKind, ProofMaturity, Provenance, WorldNode,
)

NOW = "2026-08-28T04:00:00+00:00"


def model_with_node() -> LivingWorldModel:
    model = LivingWorldModel()
    model.observe_node(WorldNode(
        "system:A", NodeKind.SYSTEM, "A", "ACTIVE", {"value": 1},
        Provenance("source", "proof", NOW, ProofMaturity.DETERMINISTIC_TESTED, 3600, .9),
    ))
    return model


class LivingStateStoreTests(unittest.TestCase):
    def test_event_log_replays_exact_snapshot(self):
        model = model_with_node()
        restored = LivingWorldModel.replay(model.export_event_log())
        self.assertEqual(model.snapshot(now=NOW)["snapshot_sha256"], restored.snapshot(now=NOW)["snapshot_sha256"])

    def test_tampered_event_log_fails_closed(self):
        model = model_with_node()
        events = [dict(x) for x in model.export_event_log()]
        events[0] = dict(events[0]); events[0]["payload"] = dict(events[0]["payload"])
        events[0]["payload"]["node"] = dict(events[0]["payload"]["node"])
        events[0]["payload"]["node"]["state"] = "TAMPERED"
        with self.assertRaises(FabricError):
            LivingWorldModel.replay(events)

    def test_sqlite_seal_restore_and_readback(self):
        model = model_with_node()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "omega4-shared.sqlite3"
            with LivingStateStore(path) as store:
                receipt = store.seal(model, now=NOW)
                self.assertTrue(receipt.store_readback_verified)
                self.assertEqual(receipt.external_effects, 0)
                self.assertEqual(store.latest_snapshot()["snapshot_sha256"], model.snapshot(now=NOW)["snapshot_sha256"])
                restored = store.restore()
                self.assertEqual(restored.snapshot(now=NOW)["snapshot_sha256"], model.snapshot(now=NOW)["snapshot_sha256"])

    def test_store_coexists_with_existing_omega4_tables(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shared.sqlite3"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE missions (mission_id TEXT PRIMARY KEY, objective TEXT)")
            conn.execute("INSERT INTO missions VALUES ('M','Objective')")
            conn.commit(); conn.close()
            with LivingStateStore(path) as store:
                store.seal(model_with_node(), now=NOW)
            conn = sqlite3.connect(path)
            row = conn.execute("SELECT objective FROM missions WHERE mission_id='M'").fetchone()
            living = conn.execute("SELECT COUNT(*) FROM living_state_events").fetchone()[0]
            conn.close()
            self.assertEqual(row[0], "Objective"); self.assertGreater(living, 0)

    def test_sequence_collision_rolls_back(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "store.sqlite3"
            model = model_with_node()
            with LivingStateStore(path) as store:
                store.seal(model, now=NOW)
                store.connection.execute(
                    "UPDATE living_state_events SET event_digest='bad' WHERE fabric_id='FEDERATION' AND sequence=1"
                )
                store.connection.commit()
                with self.assertRaises(FabricError):
                    store.seal(model, now=NOW)


if __name__ == "__main__":
    unittest.main()
