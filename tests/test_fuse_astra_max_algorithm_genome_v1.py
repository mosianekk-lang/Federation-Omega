from __future__ import annotations

import unittest

from federation.astra_max_algorithm_genome_v1 import (
    ASTRA_GENES,
    OFFICIAL_PUBLIC_SOURCES,
    genome_summary,
    select_astra_genes,
    validate_genome,
)


class FuseAstraMaxAlgorithmGenomeTests(unittest.TestCase):
    def test_exactly_48_unique_monotonic_genes(self):
        validate_genome()
        ids = [gene.gene_id for gene in ASTRA_GENES]
        self.assertEqual(len(ids), 48)
        self.assertEqual(ids[0], "HG-ASTRA-001")
        self.assertEqual(ids[-1], "HG-ASTRA-048")
        self.assertEqual(len(ids), len(set(ids)))

    def test_public_provenance_is_official_openai_only(self):
        self.assertGreaterEqual(len(OFFICIAL_PUBLIC_SOURCES), 6)
        for url in OFFICIAL_PUBLIC_SOURCES:
            self.assertTrue(
                url.startswith("https://openai.com/")
                or url.startswith("https://help.openai.com/")
                or url.startswith("https://developers.openai.com/")
            )

    def test_genome_is_provider_neutral_and_cannot_bypass_hard_boundaries(self):
        summary = genome_summary()
        self.assertTrue(summary["provider_neutral_clean_room"])
        self.assertFalse(summary["authority_expansion"])
        self.assertFalse(summary["safety_bypass"])
        self.assertIn("PUBLIC_CAPABILITY_HARVEST_NE_MODEL_BOUND", summary["truth_boundary"])

    def test_computer_use_objective_selects_computer_mechanisms(self):
        selected = select_astra_genes(
            "use Astra-style code-first computer browser control to test a frontend",
            limit=12,
        )
        names = {gene.name for gene in selected}
        self.assertTrue(
            {
                "Code-First Computer Use",
                "Frontend QA Computer Court",
                "Visual-Semantic UI Fusion",
            }
            & names
        )

    def test_professional_artifact_objective_selects_template_and_quality_mechanisms(self):
        selected = select_astra_genes(
            "create a professional presentation spreadsheet and document that follows our template",
            limit=16,
        )
        names = {gene.name for gene in selected}
        self.assertIn("Professional Presentation Compiler", names)
        self.assertTrue(
            {
                "Professional Spreadsheet Compiler",
                "Professional Document Compiler",
                "Artifact Style Matcher",
            }
            & names
        )

    def test_aggressive_request_selects_maximum_authorized_mode_not_safety_bypass(self):
        selected = select_astra_genes(
            "maximum aggressive capability with no artificial throttles while preserving authority",
            limit=12,
        )
        names = {gene.name for gene in selected}
        self.assertIn("Maximum Authorized Capability Mode", names)
        self.assertTrue(all(gene.maturity == "CANDIDATE_RESIDUAL" for gene in selected))


if __name__ == "__main__":
    unittest.main()
