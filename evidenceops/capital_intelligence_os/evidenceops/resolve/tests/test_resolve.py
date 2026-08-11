from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from resolve.engine import ResolveEngine
from resolve.models import AttemptStatus, CompletionGate, EvidenceJob, ExecutionLane, FailureClass, LaneResult
from resolve.transport import reconstruct, segment_file, sha256_file
from resolve.verification import verify_sqlite, verify_zip


class ResolveTests(unittest.TestCase):
    def test_switches_lane_and_closes_only_after_independent_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = ResolveEngine(tmp)
            engine.register_lane(ExecutionLane(
                "broken-cloud",
                lambda job: LaneResult(AttemptStatus.FAILED, {"error": "invalid_target"}, FailureClass.AUTHORITY),
                authority=0.9, reliability=0.9, proof_quality=0.9,
            ))
            engine.register_lane(ExecutionLane(
                "github-runner",
                lambda job: LaneResult(AttemptStatus.SUCCESS, {"provider_id": "run-123", "size": 42}),
                authority=0.8, reliability=0.8, proof_quality=0.9,
            ))
            gates = [
                CompletionGate("provider_readback", "Provider execution readback"),
                CompletionGate("independent_readback", "Independent result verification"),
            ]
            job = EvidenceJob(
                "job-1", "extract", {"id": "source"}, [{"name": "corpus"}], gates,
                ResolveEngine.idempotency_key("extract", {"id": "source"}, [{"name": "corpus"}]),
            )
            receipt = engine.execute(job, verifier=lambda job, provider: {"ok": provider["size"] == 42, "sha256": "verified"})
            self.assertEqual(receipt["status"], "COMPLETE_VERIFIED")
            self.assertEqual(len(receipt["attempts"]), 2)
            self.assertFalse(engine.lanes["broken-cloud"].enabled)
            self.assertTrue(receipt["learned_rules"])

    def test_refuses_complete_without_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = ResolveEngine(tmp)
            engine.register_lane(ExecutionLane("writer", lambda job: LaneResult(AttemptStatus.SUCCESS, {"id": "x"})))
            job = EvidenceJob(
                "job-2", "publish", {"id": "s"}, [{"name": "o"}],
                [CompletionGate("provider_readback", "Provider"), CompletionGate("independent_readback", "Independent")],
                "key",
            )
            receipt = engine.execute(job)
            self.assertEqual(receipt["status"], "PARTIAL")
            self.assertEqual(receipt["proof_level"], "PROVIDER_READBACK")

    def test_segment_reconstruct_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "evidence.bin"
            source.write_bytes((b"EvidenceOps-RESOLVE" * 200_000) + b"end")
            parts = root / "parts"
            manifest = segment_file(source, parts, 512 * 1024)
            output = root / "rebuilt.bin"
            result = reconstruct(parts / "evidence.bin.transport.json", parts, output)
            self.assertEqual(result["sha256"], sha256_file(source))
            self.assertEqual(manifest["part_count"], len(manifest["parts"]))
            self.assertEqual(source.read_bytes(), output.read_bytes())

    def test_zip_and_sqlite_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "shard.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
                handle.writestr("message.eml", "Subject: Test\n\nEvidence")
            self.assertTrue(verify_zip(archive)["ok"])

            database = root / "corpus.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, subject TEXT)")
            connection.execute("INSERT INTO messages(subject) VALUES ('MPMB298')")
            connection.commit()
            connection.close()
            result = verify_sqlite(database, {"messages": "SELECT COUNT(*) FROM messages"})
            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["messages"], 1)

    def test_verified_job_is_idempotent_on_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}

            def execute(job):
                calls["count"] += 1
                return LaneResult(AttemptStatus.SUCCESS, {"provider_id": "once"})

            engine = ResolveEngine(tmp)
            engine.register_lane(ExecutionLane("single", execute))
            gates = [
                CompletionGate("provider_readback", "Provider"),
                CompletionGate("independent_readback", "Independent"),
            ]
            job = EvidenceJob("job-replay", "publish", {"id": "s"}, [{"name": "o"}], gates, "stable-key")
            first = engine.execute(job, verifier=lambda job, result: {"ok": True})
            second = engine.execute(job, verifier=lambda job, result: {"ok": True})
            self.assertEqual(first, second)
            self.assertEqual(calls["count"], 1)

    def test_ledger_is_valid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = ResolveEngine(tmp)
            engine.register_lane(ExecutionLane("lane", lambda job: LaneResult(AttemptStatus.SUCCESS, {})))
            records = [json.loads(line) for line in (Path(tmp) / "resolve_ledger.jsonl").read_text().splitlines()]
            self.assertEqual(records[0]["event_type"], "LANE_REGISTERED")


if __name__ == "__main__":
    unittest.main()
