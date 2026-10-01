from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_native_receipt.py"
NATIVE_EXE = os.environ.get("FUSE_NATIVE_EXE", "")
SOURCE_SHA = os.environ.get("FEDERATION_SOURCE_SHA", "0" * 40)


def z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def task(
    task_id: str,
    *,
    task_type: str = "system_status",
    parameters: dict | None = None,
    issued: datetime | None = None,
    expires: datetime | None = None,
    correlation_id: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    issued = issued or (now - timedelta(seconds=2))
    expires = expires or (now + timedelta(minutes=5))
    return {
        "schema": "FUSE-WINDOWS-NATIVE-TASK-V1",
        "task_id": task_id,
        "correlation_id": correlation_id or f"corr-{task_id}",
        "issued_by": "FUSE/FDOF",
        "task_type": task_type,
        "issued_at": z(issued),
        "expires_at": z(expires),
        "parameters": parameters or {},
        "effect": "READ_ONLY",
    }


@unittest.skipUnless(os.name == "nt" and NATIVE_EXE and Path(NATIVE_EXE).is_file(), "native Windows executable not available")
class NativeTrunkContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.key_name = "FUSE-WINDOWS-NATIVE-TEST-" + uuid4().hex

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, payload: dict, *, expect: int = 0, receipt_out: Path | None = None) -> subprocess.CompletedProcess[str]:
        task_path = self.root / (payload["task_id"] + "-" + uuid4().hex + ".json")
        task_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        cmd = [
            NATIVE_EXE,
            "execute",
            "--task-json",
            str(task_path),
            "--state-dir",
            str(self.state),
            "--key-name",
            self.key_name,
        ]
        if receipt_out is not None:
            cmd.extend(["--receipt-out", str(receipt_out)])
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=90, check=False)
        self.assertEqual(expect, proc.returncode, msg=f"stdout={proc.stdout}\nstderr={proc.stderr}")
        return proc

    def _receipt(self, proc: subprocess.CompletedProcess[str]) -> dict:
        value = json.loads(proc.stdout.strip())
        self.assertIsInstance(value, dict)
        return value

    def _journal(self) -> list[dict]:
        path = self.state / "native-journal.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _verify(self, receipt_path: Path, task_path: Path | None = None, *, expect: int = 0) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            str(VERIFY),
            "--receipt",
            str(receipt_path),
            "--source-sha",
            SOURCE_SHA,
            "--journal",
            str(self.state / "native-journal.jsonl"),
        ]
        if task_path is not None:
            cmd.extend(["--task", str(task_path)])
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=60, check=False)
        self.assertEqual(expect, proc.returncode, msg=f"stdout={proc.stdout}\nstderr={proc.stderr}")
        return proc

    def test_system_status_signed_receipt_and_source_binding(self) -> None:
        payload = task("status-001")
        task_path = self.root / "status-task.json"
        task_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        receipt_path = self.root / "status-receipt.json"
        proc = subprocess.run(
            [NATIVE_EXE, "execute", "--task-json", str(task_path), "--state-dir", str(self.state), "--key-name", self.key_name, "--receipt-out", str(receipt_path)],
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        receipt = self._receipt(proc)
        self.assertEqual("COMPLETED_VERIFIED_NATIVE", receipt["state"])
        self.assertEqual(SOURCE_SHA.lower(), receipt["source_sha"])
        self.assertEqual("system_status", receipt["result"]["operation"])
        self.assertFalse(receipt["safety"]["external_effect"])
        verified = self._verify(receipt_path, task_path)
        self.assertEqual("VERIFIED", json.loads(verified.stdout)["state"])

    def test_current_user_cng_identity_persists_across_processes(self) -> None:
        first = self._receipt(self._run(task("identity-001")))
        second = self._receipt(self._run(task("identity-002")))
        self.assertEqual(first["public_key_spki_b64"], second["public_key_spki_b64"])
        self.assertNotEqual(first["task_sha256"], second["task_sha256"])

    def test_heavy_sha256_is_bounded_and_effect_free(self) -> None:
        payload = task(
            "heavy-001",
            task_type="heavy_sha256",
            parameters={
                "bytes_per_round": 262144,
                "rounds": 2,
                "requested_workers": 2,
                "requested_memory_mb": 128,
                "max_seconds": 30,
                "seed_hex": "ab" * 32,
            },
        )
        receipt = self._receipt(self._run(payload))
        result = receipt["result"]
        self.assertEqual(524288, result["total_bytes"])
        self.assertEqual(64, len(result["sha256"]))
        self.assertTrue(result["generated_in_memory"])
        self.assertTrue(result["resource_governor_bound"])
        for key in ("filesystem_usage", "network_usage", "shell_process_usage", "gpu_usage", "external_effect"):
            self.assertFalse(result[key])

    def test_exact_duplicate_is_idempotent_and_does_not_reexecute(self) -> None:
        payload = task(
            "heavy-replay-001",
            task_type="heavy_sha256",
            parameters={
                "bytes_per_round": 131072,
                "rounds": 1,
                "requested_workers": 2,
                "requested_memory_mb": 64,
                "max_seconds": 30,
                "seed_hex": "cd" * 32,
            },
        )
        first = self._run(payload)
        second = self._run(payload)
        self.assertEqual(first.stdout.strip(), second.stdout.strip())
        kinds = [entry["kind"] for entry in self._journal()]
        self.assertEqual(1, kinds.count("ACCEPTED"))
        self.assertEqual(1, kinds.count("COMPLETED"))
        self.assertEqual(1, kinds.count("REPLAY"))

    def test_same_task_id_different_payload_fails_closed(self) -> None:
        original = task("collision-001", correlation_id="corr-a")
        changed = task("collision-001", correlation_id="corr-b")
        self._run(original)
        rejected = self._run(changed, expect=2)
        self.assertIn("TASK_ID_COLLISION", rejected.stderr)
        self.assertIn("REJECTED_COLLISION", [entry["kind"] for entry in self._journal()])

    def test_expired_ttl_is_rejected_before_acceptance(self) -> None:
        now = datetime.now(timezone.utc)
        expired = task("expired-001", issued=now - timedelta(minutes=10), expires=now - timedelta(minutes=1))
        proc = self._run(expired, expect=2)
        self.assertIn("TASK_EXPIRED", proc.stderr)
        journal = self.state / "native-journal.jsonl"
        if journal.exists():
            self.assertNotIn("ACCEPTED", [entry["kind"] for entry in self._journal()])

    def test_unknown_task_kind_is_rejected_before_acceptance(self) -> None:
        payload = task("unknown-001", task_type="shell")
        proc = self._run(payload, expect=2)
        self.assertIn("TASK_TYPE_NOT_ALLOWLISTED", proc.stderr)
        journal = self.state / "native-journal.jsonl"
        if journal.exists():
            self.assertNotIn("ACCEPTED", [entry["kind"] for entry in self._journal()])

    def test_receipt_tamper_is_rejected_by_independent_verifier(self) -> None:
        receipt_path = self.root / "receipt.json"
        payload = task("tamper-001")
        self._run(payload, receipt_out=receipt_path)
        tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
        tampered["result"]["machine_name"] = "tampered"
        receipt_path.write_text(json.dumps(tampered, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        proc = self._verify(receipt_path, expect=1)
        self.assertTrue("HASH_MISMATCH" in proc.stderr or "RECEIPT_SIGNATURE_INVALID" in proc.stderr)

    def test_journal_corruption_blocks_next_execution(self) -> None:
        self._run(task("journal-001"))
        journal = self.state / "native-journal.jsonl"
        lines = journal.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["kind"] = "CORRUPTED"
        lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
        journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
        proc = self._run(task("journal-002"), expect=2)
        self.assertIn("JOURNAL_DIGEST_INVALID", proc.stderr)

    def test_accepted_is_durable_before_completed(self) -> None:
        self._run(task("ordering-001"))
        entries = self._journal()
        accepted = next(i for i, entry in enumerate(entries) if entry["kind"] == "ACCEPTED")
        completed = next(i for i, entry in enumerate(entries) if entry["kind"] == "COMPLETED")
        self.assertLess(accepted, completed)
        self.assertEqual(entries[completed]["previous_hash"], entries[accepted]["entry_hash"])

    def test_heavy_parameter_escape_is_fail_closed(self) -> None:
        payload = task(
            "heavy-extra-001",
            task_type="heavy_sha256",
            parameters={
                "bytes_per_round": 1024,
                "rounds": 1,
                "requested_workers": 1,
                "requested_memory_mb": 64,
                "max_seconds": 10,
                "seed_hex": "ef" * 32,
                "command": "whoami",
            },
        )
        proc = self._run(payload, expect=2)
        self.assertIn("UNKNOWN_HEAVY_PARAMETERS:command", proc.stderr)


if __name__ == "__main__":
    unittest.main()
