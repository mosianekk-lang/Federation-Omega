from __future__ import annotations

import unittest

from federation_sovereign_runtime import (
    DeterministicDataRuntime,
    ReasoningCapsule,
    WORK_CAPABILITY_GENES,
)


class ReasoningCapsuleTests(unittest.TestCase):
    def test_successor_preserves_lineage_and_evidence(self) -> None:
        first = ReasoningCapsule(
            capsule_id="CAP-1",
            mission_id="M-1",
            objective="Preserve mission reasoning continuity without private chain-of-thought.",
            conclusions=("Use provider-neutral state",),
            evidence_refs=("proof:1",),
            next_action="run canary",
        )
        second = first.successor(
            conclusions=("Processor market is replaceable",),
            evidence_refs=("proof:2",),
            unresolved_questions=("Which processor wins blind cohort?",),
            processor_ref="OPENAI::GPT-6-ASTRA",
        )
        self.assertEqual(first.sha256, second.predecessor_sha256)
        self.assertEqual(("proof:1", "proof:2"), second.evidence_refs)
        self.assertEqual(2, second.version)

    def test_compaction_never_drops_evidence_refs(self) -> None:
        capsule = ReasoningCapsule(
            capsule_id="CAP-2",
            mission_id="M-2",
            objective="Keep proof through compaction",
            conclusions=tuple(f"c{i}" for i in range(20)),
            assumptions=tuple(f"a{i}" for i in range(20)),
            evidence_refs=tuple(f"proof:{i}" for i in range(20)),
        )
        compact = capsule.compact(max_items_per_field=5)
        self.assertEqual(capsule.evidence_refs, compact.evidence_refs)
        self.assertEqual(5, len(compact.conclusions))
        self.assertEqual(capsule.sha256, compact.predecessor_sha256)


class DeterministicMicroRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = DeterministicDataRuntime()
        self.rows = (
            {"id": 1, "type": "a", "value": 10},
            {"id": 2, "type": "b", "value": 20},
            {"id": 3, "type": "a", "value": 30},
            {"id": 3, "type": "a", "value": 30},
        )

    def test_filter_project_dedup_and_count_emit_stable_receipts(self) -> None:
        filtered, filter_receipt = self.runtime.filter_equal(self.rows, field="type", value="a")
        self.assertEqual(3, len(filtered))
        self.assertFalse(filter_receipt.external_effect)

        projected, _ = self.runtime.project(filtered, fields=("id", "value"))
        self.assertEqual({"id": 1, "value": 10}, projected[0])

        deduped, dedup_receipt = self.runtime.deduplicate(projected, key_fields=("id",))
        self.assertEqual(2, len(deduped))
        self.assertEqual(2, dedup_receipt.output_count)

        counted, count_receipt = self.runtime.aggregate_count(self.rows, group_by="type")
        self.assertEqual(2, len(counted))
        self.assertEqual(count_receipt.result_sha256, self.runtime.aggregate_count(self.rows, group_by="type")[1].result_sha256)


class WorkHarnessHarvestTests(unittest.TestCase):
    def test_work_public_genes_map_to_federation_targets_without_runtime_claim(self) -> None:
        genes = {gene.gene_id: gene for gene in WORK_CAPABILITY_GENES}
        self.assertIn("WORK-G02", genes)
        self.assertIn("Remote Execution Cell", genes["WORK-G02"].federation_target)
        self.assertIn("WORK-G03", genes)
        self.assertIn("Durable external scheduler", genes["WORK-G03"].federation_target)
        self.assertIn("WORK-G08", genes)
        self.assertIn("Mission Steering Bus", genes["WORK-G08"].federation_target)


if __name__ == "__main__":
    unittest.main()
