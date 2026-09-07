import sqlite3
import tempfile
import unittest
from pathlib import Path

from federation.aurora_omega_v1 import (
    AppreciationFinding,
    AuroraOmegaAgent,
    Evidence,
    Lens,
    TerminalEvent,
)
from federation.aurora_state_store_v1 import (
    AuroraStateStore,
    StateConflictError,
    StateIntegrityError,
)


class AuroraStateStoreV1Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "aurora.sqlite"
        self.store = AuroraStateStore(self.db)
        self.agent = AuroraOmegaAgent()

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        state = self.agent.new_mission(
            "M-PERSIST",
            "Sustain a long-horizon mission across process/context resets",
            ("built", "verified"),
            lens=Lens.GENIUS_APPRECIATION,
        )
        for kind in ("ORIGINALITY", "SYNTHESIS", "SIGNIFICANCE"):
            self.agent.add_appreciation_finding(
                state,
                AppreciationFinding(f"F-{kind}", kind, f"{kind} claim", ("src",), .9),
            )
        state.open_unknowns.append("runtime binding")
        self.agent.record_event(state, TerminalEvent.EXPERIMENT_RESULT, {"step": 1})
        self.agent.add_evidence(
            state, Evidence("proof-1", "TEST", "deterministic test", True, True)
        )
        return state

    def test_roundtrip_preserves_mission_state_and_event_chain(self):
        state = self.state()
        digest = self.store.save(state)
        loaded = self.store.load(state.mission_id)
        self.assertEqual(state.mission_id, loaded.mission_id)
        self.assertEqual(state.version, loaded.version)
        self.assertEqual(state.contract.objective, loaded.contract.objective)
        self.assertEqual(state.open_unknowns, loaded.open_unknowns)
        self.assertEqual(state.events[-1].event_hash, loaded.events[-1].event_hash)
        self.assertEqual(64, len(digest))

    def test_optimistic_version_check_rejects_stale_writer(self):
        state = self.state()
        self.store.save(state)
        old_version = state.version
        self.agent.record_event(state, TerminalEvent.CORRECTION, {"x": 1})
        self.store.save(state, expected_stored_version=old_version)

        stale = self.state()
        with self.assertRaises(StateConflictError):
            self.store.save(stale, expected_stored_version=old_version)

    def test_version_regression_rejected_even_without_explicit_cas(self):
        state = self.state()
        self.store.save(state)
        state.version += 5
        self.store.save(state)
        state.version -= 10
        with self.assertRaises(StateConflictError):
            self.store.save(state)

    def test_payload_tampering_is_detected(self):
        state = self.state()
        self.store.save(state)
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE aurora_missions SET payload_json = payload_json || ' ' WHERE mission_id = ?",
                (state.mission_id,),
            )
        with self.assertRaises(StateIntegrityError):
            self.store.load(state.mission_id)

    def test_list_missions_is_deterministic(self):
        a = self.state()
        self.store.save(a)
        b = self.agent.new_mission("M-SECOND", "Second mission", ("done",))
        self.store.save(b)
        self.assertEqual(
            ("M-PERSIST", "M-SECOND"), tuple(x[0] for x in self.store.list_missions())
        )


if __name__ == "__main__":
    unittest.main()
