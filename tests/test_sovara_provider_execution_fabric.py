import unittest
from ops.sovara_provider_execution_fabric import (
    CellState, ProviderCell, ProofReceipt, Substrate,
    classify_provider_failure, provider_cell_matrix, select_provider_route,
)

class ProviderExecutionFabricTests(unittest.TestCase):
    def cell(self, provider, substrate=Substrate.APPS_SCRIPT, **overrides):
        base = dict(
            provider=provider, substrate=substrate,
            credential_reference_ready=True, runtime_authorised=True,
            health_ok=True, funding_or_quota_ready=True,
            state=CellState.READY, circuit_open=False,
        )
        base.update(overrides)
        return ProviderCell(**base)

    def test_openrouter_can_proceed_while_google_gemini_is_held(self):
        decision = select_provider_route(
            [self.cell("gemini", credential_reference_ready=False, circuit_open=True), self.cell("openrouter")],
            preferred_order=["openrouter", "gemini"])
        self.assertEqual("openrouter", decision.selected_provider)
        self.assertIn("gemini", decision.held_providers)

    def test_one_provider_failure_never_sets_global_stall(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=False)
        self.assertTrue(failure["circuit_open"])
        self.assertFalse(failure["global_stall"])

    def test_material_dependency_change_reopens_circuit(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=True)
        self.assertFalse(failure["circuit_open"])

    def test_litellm_only_admits_semantically_proven_provider(self):
        receipts = {
            "openrouter": ProofReceipt("openrouter", True, True, True, True, True, True, True),
            "gemini": ProofReceipt("gemini", True, True, False, False, False, False, False),
        }
        decision = select_provider_route([self.cell("openrouter")], receipts=receipts)
        self.assertEqual(("openrouter",), decision.litellm_admission)

    def test_health_failure_holds_only_that_cell(self):
        decision = select_provider_route(
            [self.cell("openrouter", health_ok=False), self.cell("deepseek")],
            preferred_order=["openrouter", "deepseek"])
        self.assertEqual("deepseek", decision.selected_provider)
        self.assertIn("openrouter", decision.held_providers)

    def test_substrates_are_replaceable(self):
        decision = select_provider_route([
            self.cell("openrouter", substrate=Substrate.CLOUD_RUN, health_ok=False),
            self.cell("openrouter", substrate=Substrate.APPS_SCRIPT),
        ], preferred_order=["openrouter"])
        self.assertEqual("apps_script", decision.selected_substrate)

    def test_no_credential_reference_means_no_execution(self):
        decision = select_provider_route([self.cell("openrouter", credential_reference_ready=False)])
        self.assertIsNone(decision.selected_provider)

    def test_no_quota_or_funding_means_cell_held(self):
        decision = select_provider_route(
            [self.cell("openai", funding_or_quota_ready=False), self.cell("openrouter")],
            preferred_order=["openai", "openrouter"])
        self.assertEqual("openrouter", decision.selected_provider)

    def test_receipt_without_cost_readback_is_not_promoted(self):
        receipt = ProofReceipt("openrouter", True, True, True, True, True, False, True)
        self.assertFalse(receipt.promotion_ready)

    def test_matrix_exposes_cell_eligibility_not_secret_values(self):
        matrix = provider_cell_matrix([self.cell("openrouter")])
        self.assertTrue(matrix[0]["eligible"])
        self.assertNotIn("credential_value", matrix[0])

    def test_fingerprint_is_deterministic(self):
        cells = [self.cell("openrouter"), self.cell("deepseek")]
        self.assertEqual(
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
        )

if __name__ == "__main__":
    unittest.main()
