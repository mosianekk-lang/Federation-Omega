import unittest

from ops.sovara_provider_execution_fabric import (
    CellState,
    ProviderCell,
    authority_inheritance_allowed,
    can_promote_to_litellm,
    independent_ready_cells,
    next_openrouter_gate,
)


class ProviderExecutionFabricTests(unittest.TestCase):
    def test_held_provider_does_not_block_verified_cell(self):
        good = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        held = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertEqual((good,), independent_ready_cells([held, good]))

    def test_litellm_requires_provider_and_semantic_proof(self):
        source_only = ProviderCell("openrouter", CellState.SOURCE_READY, "openrouter-only")
        provider_only = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=False,
        )
        proven = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        self.assertFalse(can_promote_to_litellm(source_only))
        self.assertFalse(can_promote_to_litellm(provider_only))
        self.assertTrue(can_promote_to_litellm(proven))

    def test_authority_never_inherits_across_cells(self):
        a = ProviderCell("openrouter", CellState.PROVEN, "openrouter-only", True, True, True)
        b = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertFalse(authority_inheritance_allowed(a, b))

    def test_openrouter_gate_progression(self):
        self.assertEqual(
            "SOURCE_INSTALL_AND_EXACT_READBACK",
            next_openrouter_gate(source_installed=False, metadata_verified=False, semantic_verified=False),
        )
        self.assertEqual(
            "PROVIDER_METADATA_READBACK",
            next_openrouter_gate(source_installed=True, metadata_verified=False, semantic_verified=False),
        )
        self.assertEqual(
            "EXACT_NONCE_SEMANTIC_READBACK",
            next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=False),
        )
        self.assertEqual(
            "LITELLM_ADMISSION_AND_FORCED_FALLBACK_PROOF",
            next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=True),
        )


if __name__ == "__main__":
    unittest.main()
