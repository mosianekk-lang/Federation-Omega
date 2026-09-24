from __future__ import annotations

import unittest

from federation.codex_capability_harvest_v1 import (
    CODEX_CAPABILITY_GENES,
    OFFICIAL_SOURCES,
    catalog_summary,
    compile_adoption_manifest,
    select_codex_genes,
    validate_catalog,
)


class FuseCodexCapabilityHarvestTests(unittest.TestCase):
    def test_catalog_is_monotonic_unique_and_bound(self):
        validate_catalog()
        ids = [gene.gene_id for gene in CODEX_CAPABILITY_GENES]
        self.assertEqual(len(ids), 24)
        self.assertEqual(ids[0], "HG-CODEX-001")
        self.assertEqual(ids[-1], "HG-CODEX-024")
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(gene.fuse_binding for gene in CODEX_CAPABILITY_GENES))

    def test_catalog_harvest_is_provider_neutral_and_non_authoritative(self):
        summary = catalog_summary()
        self.assertTrue(summary["provider_neutral_clean_room"])
        self.assertFalse(summary["authority_expansion"])
        self.assertFalse(summary["controller_duplication"])
        self.assertIn("PUBLIC_MECHANISM_HARVEST_NE_SOURCE_IMPLEMENTED", summary["truth_boundary"])

    def test_parallel_repo_work_selects_worktree_and_fanin_mechanisms(self):
        selected = select_codex_genes(
            "parallel coding agents need isolated worktrees and safe merge promotion",
            limit=8,
        )
        ids = {gene.gene_id for gene in selected}
        self.assertIn("HG-CODEX-001", ids)
        self.assertIn("HG-CODEX-023", ids)

    def test_long_running_disconnect_selects_recovery_and_compaction(self):
        selected = select_codex_genes(
            "long-running agent disconnected after context compaction and must resume",
            limit=8,
        )
        ids = {gene.gene_id for gene in selected}
        self.assertTrue({"HG-CODEX-011", "HG-CODEX-024"} & ids)

    def test_security_mechanisms_bind_to_existing_authority_organs(self):
        by_id = {gene.gene_id: gene for gene in CODEX_CAPABILITY_GENES}
        self.assertIn("SECURE_CAPABILITY_BOX", by_id["HG-CODEX-017"].fuse_binding)
        self.assertIn("FDOF", by_id["HG-CODEX-018"].fuse_binding)
        self.assertNotIn("CODEX_AUTHORITY_ROOT", {
            item for gene in CODEX_CAPABILITY_GENES for item in gene.fuse_binding
        })

    def test_manifest_never_turns_harvest_into_execution_authority(self):
        manifest = compile_adoption_manifest(
            "use skills, MCP, self-hosted executor, review queue and remote steering",
            limit=12,
        )
        self.assertFalse(manifest["authority_expansion"])
        self.assertFalse(manifest["new_controller_created"])
        self.assertFalse(manifest["new_truth_root_created"])
        self.assertFalse(manifest["new_scheduler_created"])
        self.assertFalse(manifest["source_code_or_weights_copied"])
        self.assertGreater(len(manifest["selected"]), 0)

    def test_provenance_is_official_openai_surface_only(self):
        self.assertGreaterEqual(len(OFFICIAL_SOURCES), 8)
        self.assertTrue(all(
            url.startswith("https://openai.com/")
            or url.startswith("https://developers.openai.com/")
            for url in OFFICIAL_SOURCES
        ))


if __name__ == "__main__":
    unittest.main()
