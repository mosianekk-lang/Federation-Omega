from __future__ import annotations

from dataclasses import replace
import unittest

from sovara.creative.version_tree import (
    BranchConflictError,
    VersionTree,
    VersionTreeError,
)


class SovaraCreativeVersionTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = VersionTree("ASSET-DEMO-001")
        self.root = self.tree.create_root(
            content=b"frame-v1",
            metadata={"source": "synthetic", "format": "png"},
        )

    def test_root_is_content_addressed_and_receipt_is_no_effect(self) -> None:
        receipt = self.tree.receipt()
        self.assertTrue(receipt.integrity_verified)
        self.assertEqual(1, receipt.node_count)
        self.assertFalse(receipt.external_effect_performed)
        self.assertFalse(receipt.provider_effect_performed)
        self.assertFalse(receipt.destructive_mutation_performed)
        self.assertEqual(self.root.version_id, receipt.branch_heads["main"])

    def test_metadata_is_read_only(self) -> None:
        with self.assertRaises(TypeError):
            self.root.metadata["source"] = "mutated"  # type: ignore[index]
        self.assertEqual("synthetic", self.root.metadata["source"])
        self.assertTrue(self.tree.verify_integrity())

    def test_commit_requires_compare_and_swap_head(self) -> None:
        v2 = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"frame-v2",
            metadata={"edit": "grade"},
        )
        with self.assertRaises(BranchConflictError):
            self.tree.commit(
                branch="main",
                expected_head=self.root.version_id,
                content=b"stale-write",
            )
        self.assertEqual(v2.version_id, self.tree.branch_heads()["main"])

    def test_branch_commit_does_not_move_main(self) -> None:
        self.tree.create_branch(branch="alt", from_version=self.root.version_id)
        alt = self.tree.commit(
            branch="alt",
            expected_head=self.root.version_id,
            content=b"alternate-grade",
        )
        self.assertEqual(self.root.version_id, self.tree.branch_heads()["main"])
        self.assertEqual(alt.version_id, self.tree.branch_heads()["alt"])

    def test_merge_records_two_distinct_parents(self) -> None:
        self.tree.create_branch(branch="alt", from_version=self.root.version_id)
        alt = self.tree.commit(
            branch="alt",
            expected_head=self.root.version_id,
            content=b"alternate-grade",
        )
        main = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"main-grade",
        )
        merged = self.tree.merge(
            target_branch="main",
            expected_target_head=main.version_id,
            source_version=alt.version_id,
            merged_content=b"resolved-grade",
            metadata={"resolution": "manual-synthetic"},
        )
        self.assertEqual((main.version_id, alt.version_id), merged.parent_ids)
        self.assertEqual("MERGE", merged.operation)
        self.assertTrue(self.tree.verify_integrity())

    def test_rollback_is_append_only_and_preserves_old_nodes(self) -> None:
        v2 = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"frame-v2",
        )
        before = self.tree.node_count
        rollback = self.tree.rollback(
            branch="main",
            expected_head=v2.version_id,
            target_version=self.root.version_id,
            metadata={"reason": "synthetic-regression"},
        )
        self.assertEqual(before + 1, self.tree.node_count)
        self.assertEqual(self.root.version_id, rollback.rollback_of)
        self.assertEqual(b"frame-v1", self.tree.content(rollback.version_id))
        self.assertEqual(b"frame-v2", self.tree.content(v2.version_id))
        self.assertEqual((v2.version_id,), rollback.parent_ids)

    def test_identical_replay_is_idempotent(self) -> None:
        node1 = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"frame-v2",
            metadata={"edit": "grade"},
        )
        node2 = self.tree._make_node(
            content=b"frame-v2",
            parents=(self.root.version_id,),
            operation="COMMIT",
            metadata={"edit": "grade"},
        )
        self.assertEqual(node1.canonical_record(), node2.canonical_record())
        self.assertEqual(node1.version_id, node2.version_id)
        self.assertEqual(2, self.tree.node_count)

    def test_branch_recreation_conflict_fails_closed(self) -> None:
        self.tree.create_branch(branch="alt", from_version=self.root.version_id)
        v2 = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"v2",
        )
        with self.assertRaises(BranchConflictError):
            self.tree.create_branch(branch="alt", from_version=v2.version_id)

    def test_merge_same_parent_is_rejected(self) -> None:
        with self.assertRaises(VersionTreeError):
            self.tree.merge(
                target_branch="main",
                expected_target_head=self.root.version_id,
                source_version=self.root.version_id,
                merged_content=b"no-op",
            )

    def test_lineage_is_parent_first_and_complete(self) -> None:
        v2 = self.tree.commit(
            branch="main",
            expected_head=self.root.version_id,
            content=b"v2",
        )
        v3 = self.tree.commit(
            branch="main",
            expected_head=v2.version_id,
            content=b"v3",
        )
        self.assertEqual(
            (self.root.version_id, v2.version_id, v3.version_id),
            self.tree.lineage(v3.version_id),
        )

    def test_metadata_normalization_is_deterministic(self) -> None:
        t1 = VersionTree("A")
        r1 = t1.create_root(content=b"x", metadata={"b": 2, "a": 1})
        t2 = VersionTree("A")
        r2 = t2.create_root(content=b"x", metadata={"a": 1, "b": 2})
        self.assertEqual(r1.version_id, r2.version_id)

    def test_tampered_node_is_detected(self) -> None:
        self.tree._nodes[self.root.version_id] = replace(
            self.root,
            metadata={"tampered": True},
        )
        self.assertFalse(self.tree.verify_integrity())
        self.assertFalse(self.tree.receipt().integrity_verified)

    def test_tampered_content_is_detected(self) -> None:
        self.tree._content[self.root.content_sha256] = b"tampered"
        self.assertFalse(self.tree.verify_integrity())

    def test_unknown_rollback_target_is_rejected(self) -> None:
        with self.assertRaises(VersionTreeError):
            self.tree.rollback(
                branch="main",
                expected_head=self.root.version_id,
                target_version="missing",
            )

    def test_whitespace_branch_is_rejected(self) -> None:
        with self.assertRaises(VersionTreeError):
            self.tree.create_branch(branch="bad branch", from_version=self.root.version_id)


if __name__ == "__main__":
    unittest.main()
