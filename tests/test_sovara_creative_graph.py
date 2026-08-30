import unittest

from sovara.creative.creative_graph import (
    CreativeGraph,
    CreativeGraphError,
    CreativeNodeKind,
    GraphConflictError,
    LockedNodeError,
)


class SovaraCreativeGraphTests(unittest.TestCase):
    def build_linear_graph(self):
        graph = CreativeGraph("mission-001")
        r1 = graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
            attributes={"idea": "launch"},
        )
        r2 = graph.add_node(
            expected_version=r1.version_id,
            node_id="shot-a",
            kind=CreativeNodeKind.SHOT,
            attributes={"camera": "eye-level"},
        )
        r3 = graph.add_node(
            expected_version=r2.version_id,
            node_id="asset-a",
            kind=CreativeNodeKind.ASSET,
            attributes={"format": "image"},
        )
        r4 = graph.add_dependency(
            expected_version=r3.version_id,
            source_id="concept",
            target_id="shot-a",
        )
        r5 = graph.add_dependency(
            expected_version=r4.version_id,
            source_id="shot-a",
            target_id="asset-a",
        )
        return graph, r5.version_id

    def test_root_is_deterministic_and_version_tree_integrity_is_preserved(self):
        a = CreativeGraph("mission-deterministic")
        b = CreativeGraph("mission-deterministic")
        self.assertEqual(a.head_version, b.head_version)
        self.assertEqual(a.state_sha256(), b.state_sha256())
        self.assertTrue(a.graph_receipt().version_tree_integrity_verified)

    def test_graph_commits_each_structural_change_into_version_tree(self):
        graph, head = self.build_linear_graph()
        receipt = graph.graph_receipt()
        self.assertEqual(receipt.version_id, head)
        self.assertEqual(graph.node_count, 3)
        self.assertEqual(graph.edge_count, 2)
        self.assertTrue(receipt.version_tree_integrity_verified)

    def test_dependency_cycle_is_rejected(self):
        graph, head = self.build_linear_graph()
        with self.assertRaises(CreativeGraphError):
            graph.add_dependency(
                expected_version=head,
                source_id="asset-a",
                target_id="concept",
            )

    def test_stale_writer_is_rejected_before_mutation(self):
        graph = CreativeGraph("mission-stale")
        old_head = graph.head_version
        receipt = graph.add_node(
            expected_version=old_head,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
        )
        with self.assertRaises(GraphConflictError):
            graph.add_node(
                expected_version=old_head,
                node_id="stale-node",
                kind=CreativeNodeKind.OTHER,
            )
        self.assertEqual(graph.head_version, receipt.version_id)
        with self.assertRaises(CreativeGraphError):
            graph.node("stale-node")

    def test_locked_node_cannot_be_edited_silently(self):
        graph = CreativeGraph("mission-lock")
        add = graph.add_node(
            expected_version=graph.head_version,
            node_id="approved-shot",
            kind=CreativeNodeKind.SHOT,
            attributes={"approved": True},
        )
        lock = graph.set_lock(
            expected_version=add.version_id,
            node_id="approved-shot",
            locked=True,
        )
        with self.assertRaises(LockedNodeError):
            graph.update_node(
                expected_version=lock.version_id,
                node_id="approved-shot",
                patch={"camera": "lower"},
            )
        self.assertTrue(graph.node("approved-shot").locked)

    def test_minimum_invalidation_stops_at_locked_approved_node(self):
        graph = CreativeGraph("mission-ripple")
        head = graph.head_version
        for node_id, kind in (
            ("concept", CreativeNodeKind.CONCEPT),
            ("shot-open", CreativeNodeKind.SHOT),
            ("asset-open", CreativeNodeKind.ASSET),
            ("shot-locked", CreativeNodeKind.SHOT),
            ("asset-behind-lock", CreativeNodeKind.ASSET),
        ):
            receipt = graph.add_node(
                expected_version=head,
                node_id=node_id,
                kind=kind,
            )
            head = receipt.version_id
        for source, target in (
            ("concept", "shot-open"),
            ("shot-open", "asset-open"),
            ("concept", "shot-locked"),
            ("shot-locked", "asset-behind-lock"),
        ):
            receipt = graph.add_dependency(
                expected_version=head,
                source_id=source,
                target_id=target,
            )
            head = receipt.version_id
        lock = graph.set_lock(
            expected_version=head,
            node_id="shot-locked",
            locked=True,
        )
        impact = graph.impact(("concept",))
        self.assertEqual(impact.invalidated_node_ids, ("asset-open", "shot-open"))
        self.assertEqual(impact.blocked_locked_node_ids, ("shot-locked",))
        self.assertNotIn("asset-behind-lock", impact.invalidated_node_ids)
        update = graph.update_node(
            expected_version=lock.version_id,
            node_id="concept",
            patch={"wardrobe": "darker"},
        )
        self.assertEqual(update.invalidated_node_ids, ("asset-open", "shot-open"))
        self.assertEqual(update.blocked_locked_node_ids, ("shot-locked",))

    def test_owner_correction_is_a_bounded_graph_diff_not_global_regeneration(self):
        graph, head = self.build_linear_graph()
        receipt = graph.update_node(
            expected_version=head,
            node_id="shot-a",
            patch={"camera_height_cm_delta": -18},
        )
        self.assertEqual(receipt.changed_node_ids, ("shot-a",))
        self.assertEqual(receipt.invalidated_node_ids, ("asset-a",))
        self.assertEqual(receipt.blocked_locked_node_ids, ())
        self.assertEqual(graph.node("shot-a").attributes["camera_height_cm_delta"], -18)

    def test_same_operation_sequence_produces_same_graph_receipt(self):
        def build():
            graph = CreativeGraph("mission-replay")
            a = graph.add_node(
                expected_version=graph.head_version,
                node_id="concept",
                kind=CreativeNodeKind.CONCEPT,
                attributes={"mood": "premium"},
            )
            b = graph.add_node(
                expected_version=a.version_id,
                node_id="asset",
                kind=CreativeNodeKind.ASSET,
            )
            c = graph.add_dependency(
                expected_version=b.version_id,
                source_id="concept",
                target_id="asset",
            )
            return graph, c

        graph_a, receipt_a = build()
        graph_b, receipt_b = build()
        self.assertEqual(receipt_a.version_id, receipt_b.version_id)
        self.assertEqual(receipt_a.graph_sha256, receipt_b.graph_sha256)
        self.assertEqual(graph_a.graph_receipt().receipt_sha256, graph_b.graph_receipt().receipt_sha256)

    def test_receipts_never_claim_external_provider_or_destructive_effect(self):
        graph = CreativeGraph("mission-effects")
        receipt = graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
        )
        self.assertFalse(receipt.external_effect_performed)
        self.assertFalse(receipt.provider_effect_performed)
        self.assertFalse(receipt.destructive_mutation_performed)


if __name__ == "__main__":
    unittest.main()
