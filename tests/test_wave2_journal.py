from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from omega_one.work_engine import DurableWorkerPlane, Job, Mission, SolRuntime, Workstream


class Wave2JournalTests(unittest.TestCase):
    def test_sol_append_does_not_rescan_and_replay_ignores_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = SolRuntime(root)
            runtime._events = lambda: (_ for _ in ()).throw(AssertionError("full journal scan"))
            runtime.register_mission(Mission("M1", "objective", ("done",), (), 1))
            runtime.register_workstream(Workstream("WS1", "M1", "work", (), 1, True))
            receipt = runtime.record_receipt(
                "WS1",
                "RESULT",
                "omega-work-engine",
                {"omega_publication_id": "pub-1", "value": 1},
            )
            runtime.append_event(
                "COMPLETION_EVALUATED",
                {"workstream_id": "WS1", "state": "VERIFIED", "missing": [], "omega_publication_id": "pub-1"},
            )
            runtime.append_event(
                "RELIABILITY_UPDATED",
                {
                    "action_class": "reason",
                    "attempts": 1,
                    "verified_successes": 1,
                    "success_rate": 1.0,
                    "autonomy": "AUTOMATIC",
                    "omega_publication_id": "pub-1",
                },
            )
            expected = json.loads(json.dumps(asdict(runtime.state)))
            root.joinpath("state.json").write_text(json.dumps({"stale": True}), encoding="utf-8")

            recovered = SolRuntime(root)
            self.assertEqual(asdict(recovered.state), expected)
            self.assertTrue(recovered.verify_event_chain())
            self.assertEqual(recovered.publication_receipts("WS1", "RESULT", "pub-1"), (receipt,))
            self.assertEqual(len(recovered.publication_completions("WS1", "pub-1")), 1)
            reliability = recovered.publication_reliability("pub-1")
            self.assertEqual(len(reliability), 1)
            self.assertEqual(reliability[0]["action_class"], "reason")

    def test_sol_sync_tail_applies_only_new_records(self):
        with tempfile.TemporaryDirectory() as directory:
            first = SolRuntime(directory)
            second = SolRuntime(directory)
            first.register_mission(Mission("M1", "objective", ("done",), (), 1))
            self.assertEqual(second.sync_tail(), 1)
            self.assertIn("M1", second.state.missions)
            self.assertEqual(second.sync_tail(), 0)

    def test_worker_append_is_scan_free_and_action_index_survives_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = DurableWorkerPlane(directory)
            worker._events = lambda: (_ for _ in ()).throw(AssertionError("full journal scan"))
            worker.enqueue(Job("J1", "M1", "WS1", "reason::J1", {}, "idem-1"))
            worker.enqueue(Job("J2", "M2", "WS2", "other::J2", {}, "idem-2"))
            leased = worker.lease("W1", "reason::J1")
            self.assertIsNotNone(leased)
            self.assertEqual(leased["job_id"], "J1")

            recovered = DurableWorkerPlane(directory)
            self.assertTrue(recovered.verify_event_chain())
            self.assertEqual(recovered._jobs_by_action_class["reason::J1"], {"J1"})
            self.assertEqual(recovered._jobs_by_action_class["other::J2"], {"J2"})


if __name__ == "__main__":
    unittest.main()
