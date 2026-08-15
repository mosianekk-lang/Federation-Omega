from __future__ import annotations

import unittest

from evidenceops.caseforge.completion_witness_aaa_canary import (
    run_default_completion_witness_aaa_canary,
)


class CompletionWitnessAAAAdmissionTests(unittest.TestCase):
    """Airlock admission bridge for the first AAA Intelligence Density canary.

    This deliberately executes the actual synthetic cross-home canary inside the
    existing provider-cutover-v3 Airlock discovery path. Passing this suite proves
    deterministic shadow conformance only; it does not prove provider runtime,
    autonomous recurrence, live owner-burden reduction, or external effect.
    """

    def test_shadow_canary_executes_and_meets_acceptance_contract(self) -> None:
        receipt = run_default_completion_witness_aaa_canary()
        self.assertEqual("SHADOW_VALIDATED", receipt.status)
        self.assertEqual(
            "DETERMINISTIC_SYNTHETIC_WORKLOAD_ONLY_NOT_PROVIDER_RUNTIME",
            receipt.proof_scope,
        )
        self.assertFalse(receipt.external_effect)
        self.assertEqual(
            {"CHATGOV", "EVIDENCEOPS", "TRUTHGRID"},
            set(receipt.candidate_homes),
        )
        self.assertEqual(receipt.candidate_homes, receipt.redistributed_to)
        self.assertEqual("CLAIM_CLASS_SEPARATION", receipt.feedback_improvement)

        for result in receipt.home_results:
            self.assertTrue(result.no_material_regression, result.system_id)
            self.assertGreater(result.intelligence_density.delta, 0.0, result.system_id)
            self.assertEqual(0, result.metrics.unsafe_continuations, result.system_id)
            self.assertEqual(0, result.metrics.false_terminal_provider_claims, result.system_id)
            self.assertEqual(0, result.metrics.blocked_safe_continuations, result.system_id)
            self.assertGreater(
                result.metrics.redundant_owner_prompts_baseline,
                result.metrics.redundant_owner_prompts_candidate,
                result.system_id,
            )
            self.assertGreater(result.metrics.alpha2_scope_blocks, 0, result.system_id)


if __name__ == "__main__":
    unittest.main()
