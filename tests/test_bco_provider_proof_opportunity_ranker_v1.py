import unittest

from benchmarking.cfbe_omega.bco_provider_identity_gap_compiler_v1 import (
    GapFinding,
    ProviderIdentityGapReport,
)
from benchmarking.cfbe_omega.bco_provider_proof_opportunity_ranker_v1 import (
    OpportunityClass,
    rank_provider_proof_opportunities,
)


class BCOProviderProofOpportunityRankerTests(unittest.TestCase):
    def _report(self):
        return ProviderIdentityGapReport(
            schema="BCO-PROVIDER-IDENTITY-GAP-REPORT-V1",
            state="HOLD_PROVIDER_IDENTITY_GAPS",
            historical_wif_verified=True,
            current_wif_freshness="CURRENT_HEAD_NOT_REFRESHED",
            canonical_wif_workflow_ref="canonical",
            requesting_workflow_eligibility=(("canonical", True), ("bubbles", False), ("bco", False)),
            direct_operator_token_present=False,
            google_machine_authenticated=False,
            runtime_adc_verified=False,
            action_specific_authenticated_read_proven=False,
            routes=(),
            gaps=(
                GapFinding(
                    "CANONICAL_WIF_FRESHNESS_UNPROVEN",
                    "OPEN",
                    "Canonical WIF proof is historical; current-head freshness is open.",
                ),
                GapFinding(
                    "REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION",
                    "OPEN",
                    "Bubbles and BCΩ are not authorized by the canonical workflow-identity condition.",
                    missing_controls=("bubbles", "bco"),
                    authority_required_to_change=True,
                ),
                GapFinding(
                    "DIRECT_OPERATOR_TOKEN_UNAVAILABLE",
                    "OPEN",
                    "No direct operator token is present.",
                    authority_required_to_change=True,
                ),
                GapFinding(
                    "STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE",
                    "OPEN",
                    "No static Google machine credential is present.",
                    authority_required_to_change=True,
                ),
                GapFinding(
                    "SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN",
                    "OPEN",
                    "Secret Manager token recovery is not proven.",
                ),
                GapFinding(
                    "RUNTIME_GOOGLE_ADC_UNVERIFIED",
                    "OPEN",
                    "Gemini runtime ADC is not verified.",
                    missing_controls=("gemini_runtime_service_account", "aiplatform_user_binding"),
                    authority_required_to_change=True,
                ),
                GapFinding(
                    "ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN",
                    "OPEN",
                    "Only public provider reachability is proven.",
                ),
            ),
            next_safe_proof_actions=(),
            evidence_digest="e" * 64,
        )

    def test_only_derived_evidence_recompile_is_auto_executable(self):
        plan = rank_provider_proof_opportunities(self._report())
        auto = [row.opportunity for row in plan.ranked if row.opportunity.auto_execute]
        self.assertEqual(1, len(auto))
        self.assertEqual("BCO-SAFE-RECOMPILE-EVIDENCE", auto[0].opportunity_id)
        self.assertEqual(OpportunityClass.SAFE_READ_ONLY_PROOF, auto[0].opportunity_class)
        self.assertEqual("BCO-SAFE-RECOMPILE-EVIDENCE", plan.next_safe_action)
        self.assertFalse(plan.provider_effect_authorized)
        self.assertFalse(plan.credential_change_authorized)
        self.assertFalse(plan.iam_change_authorized)
        self.assertFalse(plan.workflow_identity_change_authorized)

    def test_identity_iam_and_token_changes_are_authority_gated(self):
        plan = rank_provider_proof_opportunities(self._report())
        classes = {row.opportunity.gap_id: row.opportunity.opportunity_class for row in plan.ranked}
        self.assertEqual(
            OpportunityClass.AUTHORITY_GATED_CHANGE,
            classes["REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION"],
        )
        self.assertEqual(OpportunityClass.AUTHORITY_GATED_CHANGE, classes["DIRECT_OPERATOR_TOKEN_UNAVAILABLE"])
        self.assertEqual(
            OpportunityClass.AUTHORITY_GATED_CHANGE,
            classes["STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE"],
        )
        self.assertEqual(OpportunityClass.AUTHORITY_GATED_CHANGE, classes["RUNTIME_GOOGLE_ADC_UNVERIFIED"])

    def test_provider_evidence_gaps_wait_for_natural_proof(self):
        plan = rank_provider_proof_opportunities(self._report())
        classes = {row.opportunity.gap_id: row.opportunity.opportunity_class for row in plan.ranked}
        self.assertEqual(
            OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            classes["CANONICAL_WIF_FRESHNESS_UNPROVEN"],
        )
        self.assertEqual(
            OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            classes["ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN"],
        )
        self.assertEqual(
            OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            classes["SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN"],
        )

    def test_proof_floor_weakening_is_explicitly_prohibited(self):
        plan = rank_provider_proof_opportunities(self._report())
        prohibited = [row.opportunity for row in plan.ranked if row.opportunity.opportunity_class == OpportunityClass.PROHIBITED_AUTOFIX]
        self.assertEqual(1, len(prohibited))
        self.assertEqual("BCO-PROHIBIT-PROOF-FLOOR-WEAKENING", prohibited[0].opportunity_id)
        self.assertFalse(prohibited[0].auto_execute)

    def test_safe_action_ranks_before_waiting_or_authority_gated_actions(self):
        plan = rank_provider_proof_opportunities(self._report())
        self.assertEqual(OpportunityClass.SAFE_READ_ONLY_PROOF, plan.ranked[0].opportunity.opportunity_class)
        self.assertTrue(all(row.rank == index for index, row in enumerate(plan.ranked, start=1)))


if __name__ == "__main__":
    unittest.main()
