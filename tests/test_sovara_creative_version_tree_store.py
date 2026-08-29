from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sovara.creative.version_tree import BranchConflictError, VersionTree
from sovara.creative.version_tree_store import (
    FileVersionTreeStore,
    StoreAlreadyInitializedError,
    StoreConcurrentMutationError,
    StoreCorruptionError,
    StoreNotInitializedError,
    VersionTreeStoreError,
    _canonical_json_bytes,
)


class SovaraCreativeVersionTreeStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.asset_id = "ASSET-DEMO-DURABLE-001"
        self.store = FileVersionTreeStore(self.root, self.asset_id)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _initialize(self):
        return self.store.initialize(
            content=b"frame-v1",
            metadata={"source": "synthetic", "format": "png"},
        )

    def test_uninitialized_store_fails_closed(self) -> None:
        with self.assertRaises(StoreNotInitializedError):
            self.store.load()

    def test_initialize_then_restart_reconstructs_exact_tree(self) -> None:
        tree, receipt = self._initialize()
        restarted = FileVersionTreeStore(self.root, self.asset_id)
        loaded, reread = restarted.load()
        self.assertEqual(tree.receipt().receipt_sha256, loaded.receipt().receipt_sha256)
        self.assertEqual(receipt.receipt_sha256, reread.receipt_sha256)
        self.assertEqual(1, reread.generation)
        self.assertTrue(reread.restart_readback_verified)
        self.assertTrue(reread.integrity_verified)
        self.assertTrue(reread.local_filesystem_only)
        self.assertFalse(reread.external_effect_performed)
        self.assertFalse(reread.provider_effect_performed)
        self.assertFalse(reread.production_deployment_performed)

    def test_initialize_twice_is_rejected(self) -> None:
        self._initialize()
        with self.assertRaises(StoreAlreadyInitializedError):
            self._initialize()

    def test_commit_survives_restart_and_advances_generation(self) -> None:
        tree, first = self._initialize()
        root = tree.branch_heads()["main"]
        committed, second = self.store.commit(
            branch="main",
            expected_head=root,
            content=b"frame-v2",
            metadata={"edit": "grade"},
        )
        self.assertEqual(2, second.generation)
        self.assertNotEqual(root, committed.branch_heads()["main"])
        restarted, reread = FileVersionTreeStore(self.root, self.asset_id).load()
        self.assertEqual(committed.branch_heads(), restarted.branch_heads())
        self.assertEqual(second.tree_receipt_sha256, reread.tree_receipt_sha256)
        self.assertNotEqual(first.refs_sha256, second.refs_sha256)

    def test_branch_merge_and_rollback_survive_multiple_restarts(self) -> None:
        tree, _ = self._initialize()
        root = tree.branch_heads()["main"]

        tree, _ = self.store.create_branch(branch="alt", from_version=root)
        tree, _ = self.store.commit(
            branch="alt",
            expected_head=root,
            content=b"alt-v2",
        )
        alt_head = tree.branch_heads()["alt"]

        restarted = FileVersionTreeStore(self.root, self.asset_id)
        tree, _ = restarted.commit(
            branch="main",
            expected_head=root,
            content=b"main-v2",
        )
        main_head = tree.branch_heads()["main"]

        tree, _ = restarted.merge(
            target_branch="main",
            expected_target_head=main_head,
            source_version=alt_head,
            merged_content=b"merged-v3",
            metadata={"resolution": "synthetic"},
        )
        merge_head = tree.branch_heads()["main"]
        self.assertEqual(2, len(tree.node(merge_head).parent_ids))

        tree, receipt = restarted.rollback(
            branch="main",
            expected_head=merge_head,
            target_version=root,
            metadata={"reason": "recovery-drill"},
        )
        rollback_head = tree.branch_heads()["main"]
        self.assertEqual(root, tree.node(rollback_head).rollback_of)
        self.assertEqual(b"frame-v1", tree.content(rollback_head))
        self.assertEqual(6, receipt.generation)

        final_tree, final_receipt = FileVersionTreeStore(
            self.root, self.asset_id
        ).load()
        self.assertEqual(tree.branch_heads(), final_tree.branch_heads())
        self.assertEqual(receipt.tree_receipt_sha256, final_receipt.tree_receipt_sha256)

    def test_stale_branch_writer_is_rejected_after_another_commit(self) -> None:
        tree, _ = self._initialize()
        root = tree.branch_heads()["main"]
        self.store.commit(
            branch="main",
            expected_head=root,
            content=b"winner",
        )
        with self.assertRaises(BranchConflictError):
            FileVersionTreeStore(self.root, self.asset_id).commit(
                branch="main",
                expected_head=root,
                content=b"stale-loser",
            )

    def test_guarded_refs_replace_rejects_concurrent_change(self) -> None:
        tree, _ = self._initialize()
        prior_refs, _, prior_sha = self.store._read_refs()
        root = tree.branch_heads()["main"]
        self.store.commit(
            branch="main",
            expected_head=root,
            content=b"new-head",
        )
        with self.assertRaises(StoreConcurrentMutationError):
            self.store._replace_refs_guarded(
                prior_refs,
                expected_current_refs_sha256=prior_sha,
            )

    def test_previous_refs_hash_chains_generations(self) -> None:
        tree, first = self._initialize()
        root = tree.branch_heads()["main"]
        self.store.commit(
            branch="main",
            expected_head=root,
            content=b"v2",
        )
        refs, _, _ = self.store._read_refs()
        self.assertEqual(first.refs_sha256, refs["previous_refs_sha256"])

    def test_temporary_partial_files_are_non_authoritative(self) -> None:
        tree, receipt = self._initialize()
        (self.store.node_dir / ".interrupted-node.tmp").write_bytes(b"partial")
        (self.store.blob_dir / ".interrupted-blob.tmp").write_bytes(b"partial")
        loaded, reread = FileVersionTreeStore(self.root, self.asset_id).load()
        self.assertEqual(tree.receipt().receipt_sha256, loaded.receipt().receipt_sha256)
        self.assertEqual(receipt.receipt_sha256, reread.receipt_sha256)

    def test_unreachable_orphan_objects_from_interrupted_commit_are_ignored(self) -> None:
        tree, receipt = self._initialize()
        orphan_tree = VersionTree(self.asset_id)
        orphan = orphan_tree.create_root(
            content=b"interrupted-orphan",
            metadata={"crash": "before-refs"},
        )
        (self.store.blob_dir / f"{orphan.content_sha256}.bin").write_bytes(
            b"interrupted-orphan"
        )
        payload = {"version_id": orphan.version_id, **orphan.canonical_record()}
        (self.store.node_dir / f"{orphan.version_id}.json").write_bytes(
            _canonical_json_bytes(payload)
        )

        loaded, reread = FileVersionTreeStore(self.root, self.asset_id).load()
        self.assertEqual(1, loaded.node_count)
        self.assertEqual(tree.branch_heads(), loaded.branch_heads())
        self.assertEqual(receipt.receipt_sha256, reread.receipt_sha256)

    def test_corrupted_refs_hash_fails_closed(self) -> None:
        self._initialize()
        refs = json.loads(self.store.refs_path.read_text(encoding="utf-8"))
        refs["generation"] = 999
        self.store.refs_path.write_text(json.dumps(refs), encoding="utf-8")
        with self.assertRaisesRegex(StoreCorruptionError, "refs state hash mismatch"):
            self.store.load()

    def test_corrupted_blob_fails_closed(self) -> None:
        tree, _ = self._initialize()
        head = tree.branch_heads()["main"]
        content_sha = tree.node(head).content_sha256
        (self.store.blob_dir / f"{content_sha}.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(StoreCorruptionError, "blob content hash mismatch"):
            self.store.load()

    def test_corrupted_node_fails_closed(self) -> None:
        tree, _ = self._initialize()
        head = tree.branch_heads()["main"]
        path = self.store.node_dir / f"{head}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["metadata"]["tampered"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(StoreCorruptionError, "node canonical hash mismatch"):
            self.store.load()

    def test_missing_node_fails_closed(self) -> None:
        tree, _ = self._initialize()
        head = tree.branch_heads()["main"]
        (self.store.node_dir / f"{head}.json").unlink()
        with self.assertRaisesRegex(StoreCorruptionError, "missing immutable node"):
            self.store.load()

    def test_unsafe_asset_ids_are_rejected_before_filesystem_access(self) -> None:
        bad = ("../escape", "a/b", "a\\b", "..", "safe..unsafe", " has-space")
        for asset_id in bad:
            with self.subTest(asset_id=asset_id):
                with self.assertRaises(VersionTreeStoreError):
                    FileVersionTreeStore(self.root, asset_id)

    @unittest.skipIf(os.name == "nt", "symlink semantics vary on Windows runners")
    def test_symlinked_asset_directory_is_rejected(self) -> None:
        target = self.root / "outside"
        target.mkdir()
        asset_parent = self.root / "assets"
        asset_parent.mkdir()
        (asset_parent / self.asset_id).symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(StoreCorruptionError, "symlinked storage path"):
            self.store.initialize(content=b"x")

    def test_repeated_load_receipt_is_deterministic(self) -> None:
        self._initialize()
        _, first = self.store.load()
        _, second = FileVersionTreeStore(self.root, self.asset_id).load()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
