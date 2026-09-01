from __future__ import annotations

import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sovara.creative.version_tree_store import FileVersionTreeStore


def _concurrent_commit_worker(root: str, asset_id: str, expected_head: str, payload: bytes, gate, queue) -> None:
    store = FileVersionTreeStore(Path(root), asset_id)
    gate.wait()
    try:
        tree, receipt = store.commit(
            branch="main",
            expected_head=expected_head,
            content=payload,
        )
        queue.put(("ok", receipt.generation, tree.branch_heads()["main"]))
    except Exception as exc:  # child process returns only the public failure class/name
        queue.put((type(exc).__name__, None, None))


class SovaraCreativeVersionTreeProcessLockTests(unittest.TestCase):
    def test_two_process_writers_are_serialized_without_lost_update(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            asset_id = "ASSET-PROCESS-LOCK-001"
            store = FileVersionTreeStore(root, asset_id)
            tree, initial = store.initialize(content=b"root")
            expected_head = tree.branch_heads()["main"]
            self.assertEqual(1, initial.generation)

            ctx = multiprocessing.get_context("spawn")
            gate = ctx.Event()
            queue = ctx.Queue()
            workers = [
                ctx.Process(
                    target=_concurrent_commit_worker,
                    args=(str(root), asset_id, expected_head, payload, gate, queue),
                )
                for payload in (b"writer-a", b"writer-b")
            ]
            for worker in workers:
                worker.start()
            gate.set()
            for worker in workers:
                worker.join(timeout=15)
                self.assertFalse(worker.is_alive(), "concurrent writer did not terminate")
                self.assertEqual(0, worker.exitcode)

            results = sorted(queue.get(timeout=2)[0] for _ in workers)
            self.assertEqual(["BranchConflictError", "ok"], results)

            final_tree, final_receipt = FileVersionTreeStore(root, asset_id).load()
            self.assertEqual(2, final_receipt.generation)
            self.assertEqual(2, final_tree.node_count)
            final_head = final_tree.branch_heads()["main"]
            self.assertIn(final_tree.content(final_head), {b"writer-a", b"writer-b"})
            self.assertTrue(final_receipt.integrity_verified)
            self.assertTrue(final_receipt.restart_readback_verified)


if __name__ == "__main__":
    unittest.main()
