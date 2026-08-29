from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest

from sovara.creative.version_tree_crash_drill import (
    CHECKPOINT_AFTER_REFS,
    CHECKPOINT_BEFORE_REFS,
    prepare_crash_checkpoint,
)
from sovara.creative.version_tree_store import FileVersionTreeStore


_CONFIRM = "SOVARA_LOCAL_CRASH_DRILL_ONLY"


class SovaraVersionTreeProcessCrashDrillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.asset_id = "ASSET-PROCESS-CRASH-001"
        self.store = FileVersionTreeStore(self.root, self.asset_id)
        self.tree, self.initial_receipt = self.store.initialize(
            content=b"authoritative-v1",
            metadata={"source": "synthetic"},
        )
        self.initial_head = self.tree.branch_heads()["main"]
        self.processes: list[subprocess.Popen[str]] = []

    def tearDown(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        self.temp.cleanup()

    def _spawn_until_checkpoint(self, checkpoint: str) -> tuple[subprocess.Popen[str], dict]:
        marker = self.root / f"{checkpoint}.json"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "sovara.creative.version_tree_crash_drill",
                "--root",
                str(self.root),
                "--asset-id",
                self.asset_id,
                "--checkpoint",
                checkpoint,
                "--marker",
                str(marker),
                "--expected-head",
                self.initial_head,
                "--content",
                f"candidate-{checkpoint}",
                "--confirm",
                _CONFIRM,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.processes.append(process)

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if marker.exists():
                payload = json.loads(marker.read_text(encoding="utf-8"))
                return process, payload
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(
                    f"crash-drill worker exited before checkpoint: rc={process.returncode} "
                    f"stdout={stdout!r} stderr={stderr!r}"
                )
            time.sleep(0.02)
        self.fail(f"crash-drill checkpoint marker was not produced: {checkpoint}")

    def _kill_abruptly(self, process: subprocess.Popen[str]) -> int:
        process.kill()
        process.communicate(timeout=5)
        assert process.returncode is not None
        return process.returncode

    def test_crash_after_immutable_objects_before_refs_preserves_old_authority(self) -> None:
        process, marker = self._spawn_until_checkpoint(CHECKPOINT_BEFORE_REFS)
        returncode = self._kill_abruptly(process)
        self.assertNotEqual(0, returncode)
        self.assertFalse(marker["refs_replaced"])

        candidate_head = marker["candidate_head_after"]
        self.assertTrue((self.store.node_dir / f"{candidate_head}.json").exists())

        restarted_tree, restarted_receipt = FileVersionTreeStore(
            self.root, self.asset_id
        ).load()
        self.assertEqual(self.initial_head, restarted_tree.branch_heads()["main"])
        self.assertEqual(1, restarted_tree.node_count)
        self.assertEqual(1, restarted_receipt.generation)
        self.assertEqual(
            self.initial_receipt.tree_receipt_sha256,
            restarted_receipt.tree_receipt_sha256,
        )
        self.assertNotIn(candidate_head, restarted_tree.lineage(self.initial_head))

    def test_crash_after_refs_replace_before_readback_recovers_new_authority(self) -> None:
        process, marker = self._spawn_until_checkpoint(CHECKPOINT_AFTER_REFS)
        returncode = self._kill_abruptly(process)
        self.assertNotEqual(0, returncode)
        self.assertTrue(marker["refs_replaced"])

        restarted_tree, restarted_receipt = FileVersionTreeStore(
            self.root, self.asset_id
        ).load()
        candidate_head = marker["candidate_head_after"]
        self.assertEqual(candidate_head, restarted_tree.branch_heads()["main"])
        self.assertEqual(2, restarted_tree.node_count)
        self.assertEqual(2, restarted_receipt.generation)
        self.assertEqual(
            f"candidate-{CHECKPOINT_AFTER_REFS}".encode("utf-8"),
            restarted_tree.content(candidate_head),
        )
        refs, _, _ = self.store._read_refs()
        self.assertEqual(
            self.initial_receipt.refs_sha256,
            refs["previous_refs_sha256"],
        )

    def test_checkpoint_marker_is_explicitly_local_and_no_effect(self) -> None:
        process, marker = self._spawn_until_checkpoint(CHECKPOINT_BEFORE_REFS)
        self._kill_abruptly(process)
        self.assertTrue(marker["local_filesystem_only"])
        self.assertFalse(marker["external_effect_performed"])
        self.assertFalse(marker["provider_effect_performed"])
        self.assertFalse(marker["production_deployment_performed"])

    def test_worker_refuses_without_exact_local_only_confirmation(self) -> None:
        marker = self.root / "refused.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "sovara.creative.version_tree_crash_drill",
                "--root",
                str(self.root),
                "--asset-id",
                self.asset_id,
                "--checkpoint",
                CHECKPOINT_BEFORE_REFS,
                "--marker",
                str(marker),
                "--expected-head",
                self.initial_head,
                "--confirm",
                "WRONG",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(64, completed.returncode)
        self.assertIn("exact local-only confirmation required", completed.stderr)
        self.assertFalse(marker.exists())

    def test_direct_function_rejects_unknown_checkpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported crash checkpoint"):
            prepare_crash_checkpoint(
                root=self.root,
                asset_id=self.asset_id,
                checkpoint="UNKNOWN",
                marker=self.root / "unknown.json",
                expected_head=self.initial_head,
                content=b"candidate",
            )


if __name__ == "__main__":
    unittest.main()
