import unittest

from ops.sovara_provider_execution_fabric import (
    CellState,
    ProviderCell,
    ProofReceipt,
    Substrate,
    authority_inheritance_allowed,
    can_promote_to_litellm,
    classify_provider_failure,
    independent_ready_cells,
    next_openrouter_gate,
    provider_cell_matrix,
    select_provider_route,
)


class ProviderExecutionFabricTests(unittest.TestCase):
    def legacy_cell(self, provider, state=CellState.SOURCE_READY, **kwargs):
        return ProviderCell(provider, state, f"{provider}-only", **kwargs)

    def execution_cell(self, provider, substrate=Substrate.APPS_SCRIPT, **overrides):
        base = dict(
            provider=provider,
            state=CellState.READY,
            authority_scope=f"{provider}-only",
            substrate=substrate,
            credential_reference_ready=True,
            runtime_authorised=True,
            health_ok=True,
            funding_or_quota_ready=True,
            circuit_open=False,
        )
        base.update(overrides)
        return ProviderCell(**base)

    # Original v1 regressions remain intact.
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
        source_only = self.legacy_cell("openrouter")
        provider_only = ProviderCell(
            "openrouter", CellState.SEMANTIC_VERIFIED, "openrouter-only",
            provider_call_proven=True, semantic_readback_proven=False,
        )
        proven = ProviderCell(
            "openrouter", CellState.SEMANTIC_VERIFIED, "openrouter-only",
            provider_call_proven=True, semantic_readback_proven=True,
        )
        self.assertFalse(can_promote_to_litellm(source_only))
        self.assertFalse(can_promote_to_litellm(provider_only))
        self.assertTrue(can_promote_to_litellm(proven))

    def test_authority_never_inherits_across_cells(self):
        a = ProviderCell("openrouter", CellState.PROVEN, "openrouter-only", True, True, True)
        b = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertFalse(authority_inheritance_allowed(a, b))

    def test_openrouter_gate_progression(self):
        self.assertEqual("SOURCE_INSTALL_AND_EXACT_READBACK", next_openrouter_gate(source_installed=False, metadata_verified=False, semantic_verified=False))
        self.assertEqual("PROVIDER_METADATA_READBACK", next_openrouter_gate(source_installed=True, metadata_verified=False, semantic_verified=False))
        self.assertEqual("EXACT_NONCE_SEMANTIC_READBACK", next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=False))
        self.assertEqual("LITELLM_ADMISSION_AND_FORCED_FALLBACK_PROOF", next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=True))

    # v1.1 additive orchestration regressions.
    def test_openrouter_can_proceed_while_google_gemini_is_held(self):
        decision = select_provider_route(
            [
                self.execution_cell("gemini", state=CellState.HELD, circuit_open=True),
                self.execution_cell("openrouter"),
            ],
            preferred_order=["openrouter", "gemini"],
        )
        self.assertEqual("openrouter", decision.selected_provider)
        self.assertIn("gemini", decision.held_providers)

    def test_one_provider_failure_never_sets_global_stall(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=False)
        self.assertTrue(failure["circuit_open"])
        self.assertFalse(failure["global_stall"])

    def test_material_dependency_change_reopens_circuit(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=True)
        self.assertFalse(failure["circuit_open"])

    def test_receipt_requires_generation_readback_for_new_proof_contract(self):
        receipt = ProofReceipt("openrouter", True, True, True, True, True, True, False)
        self.assertFalse(receipt.promotion_ready)

    def test_litellm_receipt_admission_is_provider_specific(self):
        receipts = {
            "openrouter": ProofReceipt("openrouter", True, True, True, True, True, True, True),
            "gemini": ProofReceipt("gemini", True, True, False, False, False, False, False),
        }
        decision = select_provider_route([self.execution_cell("openrouter")], receipts=receipts)
        self.assertEqual(("openrouter",), decision.litellm_admission)

    def test_health_failure_holds_only_that_provider_when_no_other_substrate_is_ready(self):
        decision = select_provider_route(
            [self.execution_cell("openrouter", health_ok=False), self.execution_cell("deepseek")],
            preferred_order=["openrouter", "deepseek"],
        )
        self.assertEqual("deepseek", decision.selected_provider)
        self.assertIn("openrouter", decision.held_providers)

    def test_replaceable_substrate_keeps_provider_eligible(self):
        decision = select_provider_route(
            [
                self.execution_cell("openrouter", substrate=Substrate.CLOUD_RUN, health_ok=False),
                self.execution_cell("openrouter", substrate=Substrate.APPS_SCRIPT),
            ],
            preferred_order=["openrouter"],
        )
        self.assertEqual("apps_script", decision.selected_substrate)
        self.assertNotIn("openrouter", decision.held_providers)

    def test_no_credential_reference_means_no_execution(self):
        decision = select_provider_route([self.execution_cell("openrouter", credential_reference_ready=False)])
        self.assertIsNone(decision.selected_provider)

    def test_no_quota_or_funding_holds_only_that_provider(self):
        decision = select_provider_route(
            [self.execution_cell("openai", funding_or_quota_ready=False), self.execution_cell("openrouter")],
            preferred_order=["openai", "openrouter"],
        )
        self.assertEqual("openrouter", decision.selected_provider)

    def test_matrix_exposes_no_credential_value(self):
        matrix = provider_cell_matrix([self.execution_cell("openrouter")])
        self.assertTrue(matrix[0]["operational_eligible"])
        self.assertNotIn("credential_value", matrix[0])

    def test_fingerprint_is_deterministic(self):
        cells = [self.execution_cell("openrouter"), self.execution_cell("deepseek")]
        self.assertEqual(
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
        )


if __name__ == "__main__":
    unittest.main()
