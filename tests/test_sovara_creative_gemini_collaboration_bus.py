import unittest

from sovara.creative.gemini_collaboration_bus import (
    CollaborationBusError,
    CollaborationDecision,
    DispatchState,
    ProposalDecision,
    ProviderBudgetEnvelope,
    build_delta,
    build_feedback,
    compile_cycle,
    g2_spec_payload,
    ingest_verified_gemini_output,
)


class SovaraGeminiCollaborationBusTests(unittest.TestCase):
    def base_delta(self):
        return build_delta(
            source_head="abc123",
            summary="SC-GRAPH admitted and owner correction path needs challenger review",
            changed_capabilities=["SC-GRAPH", "SC-VERSION-TREE"],
            evidence_pointers=["github:main@abc123", "kdv:mesh"],
            context={"mission": "promptless creative kernel", "commercial_value": "unmeasured"},
        )

    def test_cycle_is_deterministic_for_same_delta_and_feedback(self):
        delta = self.base_delta()
        a = compile_cycle(delta=delta)
        b = compile_cycle(delta=delta)
        self.assertEqual(a.cycle_id, b.cycle_id)
        self.assertEqual(a.challenge_id, b.challenge_id)
        self.assertEqual(a.receipt_sha256, b.receipt_sha256)

    def test_default_dispatch_holds_without_explicit_finite_spend_authority(self):
        cycle = compile_cycle(delta=self.base_delta())
        self.assertEqual(cycle.dispatch_state, DispatchState.HOLD_SPEND_AUTHORITY)

    def test_dispatch_requires_authority_id_and_positive_finite_cap(self):
        delta = self.base_delta()
        held = compile_cycle(
            delta=delta,
            budget=ProviderBudgetEnvelope(authorized=True, max_usd=0.25, authority_id=None),
        )
        self.assertEqual(held.dispatch_state, DispatchState.HOLD_SPEND_AUTHORITY)
        ready = compile_cycle(
            delta=delta,
            budget=ProviderBudgetEnvelope(
                authorized=True,
                max_usd=0.25,
                authority_id="OWNER-GEMINI-COLLAB-001",
            ),
        )
        self.assertEqual(ready.dispatch_state, DispatchState.READY)

    def test_credential_like_context_keys_are_rejected(self):
        with self.assertRaises(CollaborationBusError):
            build_delta(
                source_head="abc123",
                summary="unsafe",
                changed_capabilities=["SC-GRAPH"],
                evidence_pointers=[],
                context={"api_key": "forbidden"},
            )

    def test_feedback_roundtrip_preserves_accept_experiment_hold_reject(self):
        feedback = build_feedback(
            "cycle-1",
            [
                ProposalDecision("P1", CollaborationDecision.ACCEPT, "reuse", "SC-GRAPH", "CI"),
                ProposalDecision("P2", CollaborationDecision.EXPERIMENT, "measure", "SC-PULSE", "CANARY"),
                ProposalDecision("P3", CollaborationDecision.HOLD, "no baseline", "SC-ECONOMICS", "BASELINE"),
                ProposalDecision("P4", CollaborationDecision.REJECT, "duplicate", "SC-GRAPH", "NONE"),
            ],
        )
        self.assertEqual(feedback.accepted, ("P1",))
        self.assertEqual(feedback.experiments, ("P2",))
        self.assertEqual(feedback.held, ("P3",))
        self.assertEqual(feedback.rejected, ("P4",))

    def test_next_cycle_prompt_contains_prior_federation_feedback(self):
        feedback = build_feedback(
            "cycle-1",
            [ProposalDecision("P1", CollaborationDecision.REJECT, "feature sprawl", "SC-GRAPH", "NONE")],
        )
        cycle = compile_cycle(delta=self.base_delta(), parent_cycle_id="cycle-1", feedback=feedback)
        prompt = cycle.challenge_spec.user_prompt
        self.assertIn("authoritative feedback", prompt)
        self.assertIn("feature sprawl", prompt)
        self.assertIn("REJECT", prompt)
        self.assertEqual(cycle.feedback_sha256, feedback.feedback_sha256)

    def test_g2_payload_remains_compatible_sanitized_and_proposal_only(self):
        cycle = compile_cycle(delta=self.base_delta())
        payload = g2_spec_payload(cycle)
        self.assertEqual(payload["schema"], "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_V1")
        self.assertTrue(payload["sanitized"])
        self.assertFalse(payload["case_data_allowed"])
        self.assertFalse(payload["external_effect_allowed"])
        self.assertEqual(payload["model"], "google/gemini-3.1-pro-preview")
        self.assertEqual(payload["proposal_count"], 12)

    def test_duplicate_decision_is_rejected(self):
        with self.assertRaises(CollaborationBusError):
            build_feedback(
                "cycle-1",
                [
                    ProposalDecision("P1", CollaborationDecision.HOLD, "a", "SC-GRAPH", "X"),
                    ProposalDecision("P1", CollaborationDecision.REJECT, "b", "SC-GRAPH", "Y"),
                ],
            )

    def test_verified_provider_output_ingests_without_canonical_promotion(self):
        cycle = compile_cycle(delta=self.base_delta())
        proposals = []
        for i in range(12):
            proposals.append(
                {
                    "proposal_id": f"P{i+1:02d}",
                    "name": f"Proposal {i+1}",
                    "problem": "x",
                    "functionality": "y",
                    "why_existing_architecture_is_insufficient": "z",
                    "reuse_strategy": "EXTEND",
                    "dependencies": [],
                    "owner_burden_reduction": "measure",
                    "operational_value": "measure",
                    "commercial_value": "unverified",
                    "proof_gate": "CI",
                    "risks": [],
                    "priority": "P1",
                }
            )
        output = {
            "challenge_id": cycle.challenge_id,
            "system_level_thesis": "thesis",
            "elite_studio_gaps": ["gap"],
            "proposals": proposals,
            "top_three": ["P01", "P02", "P03"],
            "anti_bloat_warning": "reuse first",
        }
        receipt = {
            "status": "VERIFIED",
            "semantic_verified": True,
            "proposal_authority_only": True,
            "provider_native_readback": True,
            "provider_request_id": "req-1",
            "model_returned": "gemini-3.1-pro-preview",
            "receipt_sha256": "receipt-sha",
        }
        envelope = ingest_verified_gemini_output(
            cycle=cycle,
            output=output,
            provider_receipt=receipt,
        )
        self.assertTrue(envelope["proposal_authority_only"])
        self.assertFalse(envelope["canonical_mutation_performed"])
        self.assertFalse(envelope["external_effect_performed"])
        self.assertEqual(envelope["proposal_count"], 12)

    def test_unverified_provider_receipt_fails_closed(self):
        cycle = compile_cycle(delta=self.base_delta())
        with self.assertRaises(CollaborationBusError):
            ingest_verified_gemini_output(
                cycle=cycle,
                output={"challenge_id": cycle.challenge_id, "proposals": []},
                provider_receipt={"status": "FAILED", "semantic_verified": False},
            )


if __name__ == "__main__":
    unittest.main()
