from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarking.cfbe_omega.h100_current_maturity_reconciler_v1 import (
    CLOSURE_PATH,
    EmpiricalState,
    ProgrammeMaturity,
    maturity_counts,
    reconcile_current_h100,
)

SAMPLE_SOURCE_SHA = "a" * 40


class H100CurrentMaturityReconcilerV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = reconcile_current_h100(SAMPLE_SOURCE_SHA)

    def test_exact_100_and_all_have_executable_bindings(self) -> None:
        self.assertEqual(self.result.gene_count, 100)
        self.assertEqual(self.result.executable_binding_count, 100)
        self.assertTrue(self.result.source_control_complete)
        self.assertTrue(all(row.executable_binding for row in self.result.genes))

    def test_canonical_36_62_2_accounting_is_preserved(self) -> None:
        self.assertEqual(self.result.reuse_count, 36)
        self.assertEqual(self.result.composed_count, 62)
        self.assertEqual(self.result.provider_verified_count, 2)
        self.assertEqual(maturity_counts(self.result.genes), {
            ProgrammeMaturity.SOURCE_REUSE_BOUND.value: 36,
            ProgrammeMaturity.SOURCE_COMPOSITION_BOUND.value: 62,
            ProgrammeMaturity.PROVIDER_VERIFIED.value: 2,
        })

    def test_provider_verified_genes_are_exactly_42_and_47(self) -> None:
        verified = {row.gene_id for row in self.result.genes if row.provider_verified}
        self.assertEqual(verified, {"FHU-042", "FHU-047"})
        self.assertEqual(self.result.provider_gate_count, 2)
        self.assertEqual(self.result.provider_gate_open_count, 0)

    def test_provider_maturity_is_derived_from_machine_closure_receipt(self) -> None:
        payload = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
        payload["FHU-047"]["state"] = "SOURCE_READY"
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "closure.json"
            bad.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "H100_CURRENT_PROVIDER_CLOSURE_EVIDENCE_INVALID"):
                reconcile_current_h100(SAMPLE_SOURCE_SHA, closure_path=bad)

    def test_v2_frontier_strengthens_exactly_25_existing_genes(self) -> None:
        strengthened = {row.gene_id for row in self.result.genes if row.frontier_strengthened_v2}
        self.assertEqual(len(strengthened), 25)
        self.assertIn("FHU-100", strengthened)
        self.assertIn("FHU-042", strengthened)

    def test_programme_completion_does_not_grant_effect_or_stable_authority(self) -> None:
        self.assertFalse(self.result.provider_effect_authorized)
        self.assertFalse(self.result.stable_promotion_authorized)
        self.assertFalse(any(row.provider_effect_authorized for row in self.result.genes))
        self.assertFalse(any(row.stable_promotion_authorized for row in self.result.genes))

    def test_nine_empirical_frontiers_remain_separate_from_gene_completion(self) -> None:
        frontiers = {row.lane_id: row for row in self.result.empirical_frontiers}
        self.assertEqual(len(frontiers), 9)
        self.assertEqual(frontiers["SLSA_ATTESTATION"].state, EmpiricalState.PROVIDER_VERIFIED)
        self.assertEqual(frontiers["WORKLOAD_IDENTITY"].state, EmpiricalState.PROVIDER_VERIFIED)
        self.assertEqual(frontiers["DURABLE_RUNTIME"].state, EmpiricalState.HOSTED_VERIFIED)
        self.assertEqual(frontiers["LIVE_AGENT_TELEMETRY"].state, EmpiricalState.OBSERVED_PARTIAL)
        self.assertEqual(frontiers["MULTI_PROVIDER_ROUTING"].state, EmpiricalState.HOLD_CREDENTIAL_BINDING)
        self.assertEqual(frontiers["OWNER_VALUE"].state, EmpiricalState.HOLD_REAL_OBSERVATIONS)

    def test_invalid_source_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "H100_CURRENT_SOURCE_SHA_INVALID"):
            reconcile_current_h100("main")


if __name__ == "__main__":
    unittest.main()
