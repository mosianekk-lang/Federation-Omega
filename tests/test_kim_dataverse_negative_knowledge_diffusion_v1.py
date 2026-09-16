from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_negative_knowledge_diffusion_v1 import FailureGene, diffuse_failure_gene


class KimDataverseNegativeKnowledgeDiffusionTests(unittest.TestCase):
    def test_verified_failure_gene_diffuses_only_to_semantically_compatible_scoped_receivers(self) -> None:
        gene = FailureGene(
            "g1",
            "EXPORT_TEST_LEAK",
            "fp",
            "skip workflow-only assertion in workflow-free export",
            ("proof:regression",),
            ("phoenix", "core-export"),
        )
        decision = diffuse_failure_gene(
            gene,
            ("phoenix", "core-export", "google-provider"),
            receiver_semantic_compatibility={"phoenix": True, "core-export": True, "google-provider": False},
        )
        self.assertEqual(("core-export", "phoenix"), decision.eligible_receivers)
        self.assertEqual(("google-provider",), decision.blocked_receivers)
        self.assertFalse(decision.external_effect_authorized)

    def test_failure_gene_without_regression_proof_fails_closed(self) -> None:
        gene = FailureGene("g", "f", "fp", "repair", (), ("receiver",))
        with self.assertRaises(ValueError):
            diffuse_failure_gene(gene, ("receiver",), receiver_semantic_compatibility={"receiver": True})

    def test_failure_gene_cannot_inherit_authority(self) -> None:
        gene = FailureGene("g", "f", "fp", "repair", ("proof",), ("receiver",), authority_inherited=True)
        with self.assertRaises(ValueError):
            diffuse_failure_gene(gene, ("receiver",), receiver_semantic_compatibility={"receiver": True})


if __name__ == "__main__":
    unittest.main()
