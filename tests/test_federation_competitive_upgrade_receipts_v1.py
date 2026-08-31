from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.federation_competitive_upgrade_receipts_v1 import compile_implementation_receipt


class CompetitiveUpgradeReceiptTests(unittest.TestCase):
    def test_all_100_genes_are_routed(self) -> None:
        receipt = compile_implementation_receipt()
        self.assertEqual(receipt.gene_count, 100)
        self.assertEqual(receipt.routed_count, 100)
        self.assertEqual(receipt.unrouted_gene_ids, ())
        self.assertEqual(receipt.reuse_count + receipt.composed_source_count + receipt.provider_gated_count, 100)

    def test_provider_gated_genes_do_not_claim_runtime(self) -> None:
        receipt = compile_implementation_receipt()
        gated = [item for item in receipt.receipts if item.state == "IMPLEMENTED_PROVIDER_GATE_CONTRACT_RUNTIME_OPEN"]
        self.assertTrue(gated)
        self.assertTrue(all(item.provider_runtime_proven is False for item in gated))
        self.assertFalse(receipt.stable_promotion_allowed)
        self.assertFalse(receipt.provider_effect_authorized)


if __name__ == "__main__":
    unittest.main()
