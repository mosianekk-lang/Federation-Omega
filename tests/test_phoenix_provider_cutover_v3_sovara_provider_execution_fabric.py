import unittest

from ops.sovara_provider_execution_fabric import (
    CellState,
    ProviderCell,
    authority_inheritance_allowed,
    can_promote_to_litellm,
    independent_ready_cells,
)


class SovaraProviderExecutionFabricAirlockBridgeTests(unittest.TestCase):
    def test_held_provider_does_not_stall_independent_verified_cell(self):
        openrouter = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        gemini = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertEqual((openrouter,), independent_ready_cells([gemini, openrouter]))

    def test_litellm_admission_requires_native_semantic_proof(self):
        unverified = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=False,
        )
        verified = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        self.assertFalse(can_promote_to_litellm(unverified))
        self.assertTrue(can_promote_to_litellm(verified))

    def test_provider_authority_never_inherits_between_cells(self):
        source = ProviderCell("openrouter", CellState.PROVEN, "openrouter-only", False, True, True)
        target = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertFalse(authority_inheritance_allowed(source, target))


if __name__ == "__main__":
    unittest.main()
