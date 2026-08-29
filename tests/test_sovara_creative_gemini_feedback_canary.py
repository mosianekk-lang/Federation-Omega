import json
from pathlib import Path
import unittest

from sovara.creative.gemini_collaboration_bus import (
    CollaborationDecision,
    DispatchState,
    ProposalDecision,
    build_delta,
    build_feedback,
    compile_cycle,
)


PACKET = Path("governance/sovara_gemini_feedback_consumption_canary_v1.json")


class SovaraGeminiFeedbackCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(PACKET.read_text(encoding="utf-8"))

    def test_packet_is_explicitly_non_dispatching_without_spend_authority(self):
        dispatch = self.payload["dispatch"]
        self.assertEqual(dispatch["state"], "HOLD_SPEND_AUTHORITY")
        self.assertFalse(dispatch["provider_call_authorized"])
        self.assertIsNone(dispatch["max_usd"])
        self.assertIsNone(dispatch["authority_id"])
        self.assertFalse(dispatch["automatic_recurring_inference_authorized"])

    def test_feedback_distribution_and_hash_are_exact(self):
        decisions = tuple(
            ProposalDecision(
                proposal_id=item["proposal_id"],
                decision=CollaborationDecision(item["decision"]),
                reason=item["reason"],
                target_capability=item["target_capability"],
                proof_gate=item["proof_gate"],
            )
            for item in self.payload["federation_feedback"]
        )
        feedback = build_feedback(self.payload["parent_cycle_id"], decisions)
        self.assertEqual(feedback.feedback_sha256, self.payload["feedback_sha256"])
        self.assertEqual(len(feedback.accepted), 6)
        self.assertEqual(len(feedback.experiments), 4)
        self.assertEqual(len(feedback.held), 2)
        self.assertEqual(len(feedback.rejected), 0)

    def test_cycle_recompiles_to_exact_id_and_holds(self):
        source = self.payload["delta"]
        delta = build_delta(
            source_head=self.payload["source_head"],
            summary=source["summary"],
            changed_capabilities=source["changed_capabilities"],
            evidence_pointers=source["evidence_pointers"],
            context=source["context"],
        )
        decisions = tuple(
            ProposalDecision(
                proposal_id=item["proposal_id"],
                decision=CollaborationDecision(item["decision"]),
                reason=item["reason"],
                target_capability=item["target_capability"],
                proof_gate=item["proof_gate"],
            )
            for item in self.payload["federation_feedback"]
        )
        feedback = build_feedback(self.payload["parent_cycle_id"], decisions)
        cycle = compile_cycle(
            delta=delta,
            parent_cycle_id=self.payload["parent_cycle_id"],
            feedback=feedback,
            budget=None,
        )
        self.assertEqual(cycle.delta_sha256, self.payload["delta_sha256"])
        self.assertEqual(cycle.feedback_sha256, self.payload["feedback_sha256"])
        self.assertEqual(cycle.cycle_id, self.payload["cycle_id"])
        self.assertEqual(cycle.challenge_id, self.payload["challenge_id"])
        self.assertIs(cycle.dispatch_state, DispatchState.HOLD_SPEND_AUTHORITY)
        self.assertIn("Prior Federation decisions (authoritative feedback):", cycle.challenge_spec.user_prompt)
        self.assertIn("PROP-08: ACCEPT", cycle.challenge_spec.user_prompt)
        self.assertIn("PROP-10: HOLD", cycle.challenge_spec.user_prompt)

    def test_success_contract_requires_second_leg_provider_native_readback(self):
        contract = self.payload["success_contract"]
        self.assertTrue(contract["must_return_exact_challenge_id"])
        self.assertTrue(contract["must_include_prior_feedback_response"])
        self.assertTrue(contract["provider_native_response_id_required"])
        self.assertTrue(contract["provider_model_version_required"])
        self.assertTrue(contract["semantic_verified_required"])
        self.assertTrue(contract["proposal_authority_only_required"])
        self.assertFalse(contract["case_data_processed"])
        self.assertFalse(contract["provider_mutation_allowed"])
        self.assertFalse(contract["external_effect_allowed"])
        self.assertFalse(contract["canonical_auto_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
