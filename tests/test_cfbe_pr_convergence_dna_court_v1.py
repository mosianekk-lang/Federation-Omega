from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.pr_convergence_dna_court_v1 import (
    BranchDisposition,
    CapabilityDisposition,
    SOURCE_EPOCH,
    court_summary,
    run_court,
)


class PRConvergenceDNACourtV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.capabilities, self.branches = run_court()
        self.by_capability = {row.capability_id: row for row in self.capabilities}
        self.by_pr = {row.pr_number: row for row in self.branches}

    def test_court_is_bound_to_a_real_source_epoch_and_exact_three_heads(self) -> None:
        self.assertEqual(SOURCE_EPOCH, "62b6bccec96e39472997cf8620f7f151f2d91c75")
        self.assertEqual(len(self.branches), 3)
        self.assertEqual(len(self.capabilities), 25)
        self.assertEqual(set(self.by_pr), {1021, 1025, 1022})
        for row in self.branches:
            self.assertEqual(len(row.head_sha), 40)
            self.assertEqual(len(row.receipt_sha256), 64)

    def test_already_admitted_slos_primitives_are_reused_not_rebuilt(self) -> None:
        for capability_id in (
            "P1021-EVIDENCE-DISTILLATION",
            "P1025-MISSIONIR",
            "P1025-DIGITAL-TWIN",
            "P1025-TOKEN-BUCKET-FANOUT",
            "P1025-SHADOW-EVOLUTION",
            "P1022-OBJECTIVE-ECOLOGY-RESOURCE-ECONOMY",
            "P1022-CAPABILITY-MARKET",
        ):
            self.assertIs(self.by_capability[capability_id].disposition, CapabilityDisposition.REUSE)
            self.assertEqual(self.by_capability[capability_id].missing_primitives, ())

    def test_1025_keeps_only_missing_runtime_primitives_for_harvest(self) -> None:
        self.assertIs(
            self.by_capability["P1025-WORK-STEALING"].disposition,
            CapabilityDisposition.UNIQUE_RESTACK,
        )
        self.assertIn("work_stealing", self.by_capability["P1025-WORK-STEALING"].missing_primitives)
        self.assertIs(
            self.by_capability["P1025-ASYNC-PARALLEL-EXECUTOR"].disposition,
            CapabilityDisposition.SELECTIVE_HARVEST,
        )
        self.assertIs(
            self.by_capability["P1025-SPECULATIVE-READ-RACE-HEDGE"].disposition,
            CapabilityDisposition.UNIQUE_RESTACK,
        )

    def test_1021_wif_change_remains_provider_held(self) -> None:
        row = self.by_capability["P1021-WIF-SUCCESS-CONSUMPTION-LEASE"]
        self.assertIs(row.disposition, CapabilityDisposition.PROVIDER_GATED_HOLD)
        self.assertFalse(row.provider_effect_authorized)
        self.assertFalse(row.stable_promotion_authorized)

    def test_branch_dispositions_block_wholesale_restack(self) -> None:
        self.assertIs(
            self.by_pr[1021].branch_disposition,
            BranchDisposition.SPLIT_HARVEST_AND_REPAIR,
        )
        self.assertIs(
            self.by_pr[1025].branch_disposition,
            BranchDisposition.SELECTIVE_HARVEST,
        )
        self.assertIs(
            self.by_pr[1022].branch_disposition,
            BranchDisposition.SUPERSEDE_AFTER_SELECTIVE_HARVEST,
        )

        self.assertEqual(
            (
                self.by_pr[1021].reuse_count,
                self.by_pr[1021].extend_count,
                self.by_pr[1021].selective_harvest_count,
                self.by_pr[1021].unique_restack_count,
                self.by_pr[1021].provider_hold_count,
            ),
            (1, 2, 0, 4, 1),
        )
        self.assertEqual(
            (
                self.by_pr[1025].reuse_count,
                self.by_pr[1025].extend_count,
                self.by_pr[1025].selective_harvest_count,
                self.by_pr[1025].unique_restack_count,
                self.by_pr[1025].provider_hold_count,
            ),
            (4, 0, 3, 2, 0),
        )
        self.assertEqual(
            (
                self.by_pr[1022].reuse_count,
                self.by_pr[1022].extend_count,
                self.by_pr[1022].selective_harvest_count,
                self.by_pr[1022].unique_restack_count,
                self.by_pr[1022].provider_hold_count,
            ),
            (2, 4, 2, 0, 0),
        )

    def test_court_grants_no_effect_merge_or_promotion_authority(self) -> None:
        summary = court_summary()
        self.assertFalse(summary["provider_effect_authorized"])
        self.assertFalse(summary["stable_promotion_authorized"])
        self.assertFalse(summary["merge_or_close_authorized"])
        for row in self.capabilities:
            self.assertFalse(row.provider_effect_authorized)
            self.assertFalse(row.stable_promotion_authorized)
            self.assertEqual(len(row.receipt_sha256), 64)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
