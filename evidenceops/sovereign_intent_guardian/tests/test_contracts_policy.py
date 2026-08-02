from __future__ import annotations

import unittest

from sovereign_intent_guardian.contracts import (
    AuditRequest, ValidationError, Verdict, parse_json_strict,
)
from sovereign_intent_guardian.policy import evaluate
from tests.helpers import audit_request, request_payload


class ContractTests(unittest.TestCase):
    def test_unknown_top_level_field_is_rejected(self):
        payload = request_payload(extra_authority=True)
        with self.assertRaisesRegex(ValidationError, "unknown_fields"):
            AuditRequest.from_dict(payload)

    def test_unknown_action_field_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unknown_fields"):
            AuditRequest.from_dict(request_payload(proposed_action={"tools": ["email"]}))

    def test_invalid_source_hash_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "hash_invalid"):
            AuditRequest.from_dict(request_payload(source_hashes={"source-1": "bad"}))

    def test_nonfinite_cost_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "estimated_cost_invalid"):
            AuditRequest.from_dict(request_payload(proposed_action={"estimated_cost": float("nan")}))

    def test_caller_supplied_cadence_count_is_rejected(self):
        payload = request_payload()
        payload["user_visible_output_count"] = 4
        with self.assertRaisesRegex(ValidationError, "unknown_fields"):
            AuditRequest.from_dict(payload)

    def test_duplicate_json_key_and_nan_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "duplicate_json_key"):
            parse_json_strict('{"mission_id":"one","mission_id":"two"}')
        with self.assertRaisesRegex(ValidationError, "invalid_json_number"):
            parse_json_strict('{"cost":NaN}')


class PolicyTests(unittest.TestCase):
    def evaluate(self, request, delivered=0, advisory=True):
        return evaluate(
            request,
            delivered_output_count=delivered,
            output_ledger_hash="d" * 64,
            output_ledger_verified=True,
            advisory_available=advisory,
            continuity_attestation_verified=True,
        )

    def test_clean_read_only_action_aligns(self):
        result = self.evaluate(audit_request())
        self.assertEqual(Verdict.ALIGN, result.verdict)
        self.assertFalse(result.to_dict()["authorizes_action"])
        self.assertEqual("NONE", result.to_dict()["release_authority"])

    def test_missing_provider_is_a_condition_not_a_pass(self):
        result = self.evaluate(audit_request(), advisory=False)
        self.assertEqual(Verdict.ALIGN_WITH_CONDITIONS, result.verdict)
        self.assertIn("ADVISORY_PROVIDER_UNAVAILABLE", result.conditions)

    def test_fifth_output_is_computed_from_ledger(self):
        result = self.evaluate(audit_request(), delivered=4)
        self.assertTrue(result.cadence_due)
        self.assertIn("FIFTH_OUTPUT_UPDATE_DUE", result.conditions)

    def test_non_fifth_output_has_no_cadence_condition(self):
        result = self.evaluate(audit_request(), delivered=3)
        self.assertFalse(result.cadence_due)

    def test_every_prohibited_effect_blocks(self):
        effects = (
            "IMPERSONATE_OWNER", "SEND_COMMUNICATION", "CONSENT_OR_WAIVER",
            "LEGAL_SETTLEMENT", "SPEND_OR_BILL", "ACCESS_SECRET", "PUBLISH",
            "DEPLOY", "MERGE", "WORKFLOW_DISPATCH", "CLOUD_MUTATION",
            "WRITE_LOCAL_OR_REMOTE", "DELETE_RESOURCE", "EXECUTE_COMMAND",
        )
        for effect in effects:
            with self.subTest(effect=effect):
                result = self.evaluate(audit_request(proposed_action={"requested_effects": [effect]}))
                self.assertEqual(Verdict.BLOCK, result.verdict)
                self.assertIn(f"PROHIBITED_EFFECT_{effect}", result.reason_codes)

    def test_unknown_action_kind_and_effect_fail_closed_at_contract(self):
        for action in ({"kind": "DELETE_RESOURCE"}, {"requested_effects": ["remove production"]}):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValidationError, "unsupported"):
                    audit_request(proposed_action=action)

    def test_formation_gate_decision_is_a_closed_enum(self):
        with self.assertRaisesRegex(ValidationError, "formation_gate_decision_invalid"):
            audit_request(proposed_action={"formation_gate_decision": "password: hunter2"})

    def test_state_claim_and_proof_keys_are_closed(self):
        with self.assertRaisesRegex(ValidationError, "state_claims_unsupported"):
            audit_request(proposed_action={"state_claims": {"live": True}})
        with self.assertRaisesRegex(ValidationError, "proof_unsupported"):
            audit_request(proposed_action={"proof": {"trust_me": True}})

    def test_stale_continuity_inputs_block(self):
        fields = {
            "local_bible_hash_chain_valid": "LOCAL_BIBLE_HASH_CHAIN_INVALID",
            "mission_current": "STALE_MISSION",
            "source_fingerprints_current": "STALE_SOURCE_FINGERPRINT",
            "requirements_current": "STALE_REQUIREMENTS",
        }
        for field, code in fields.items():
            with self.subTest(field=field):
                result = self.evaluate(audit_request(**{field: False}))
                self.assertEqual(Verdict.BLOCK, result.verdict)
                self.assertIn(code, result.reason_codes)

    def test_stale_policy_fingerprint_blocks(self):
        result = self.evaluate(audit_request(policy_hash="0" * 64))
        self.assertEqual(Verdict.BLOCK, result.verdict)
        self.assertIn("STALE_POLICY", result.reason_codes)

    def test_manual_task_or_cost_blocks(self):
        manual = self.evaluate(audit_request(manual_user_task_count=1))
        cost = self.evaluate(audit_request(proposed_action={"estimated_cost": 1}))
        self.assertIn("AVOIDABLE_MANUAL_USER_TASK", manual.reason_codes)
        self.assertIn("UNAUTHORISED_COST", cost.reason_codes)

    def test_non_a0_is_always_blocked_even_with_formation_permit(self):
        blocked = self.evaluate(audit_request(proposed_action={"authority_class": "A1"}))
        self.assertIn("EFFECT_AUTHORITY_PROHIBITED", blocked.reason_codes)
        still_blocked = self.evaluate(audit_request(proposed_action={
            "authority_class": "A1",
            "formation_gate_decision": "EXECUTE",
            "formation_permit_current": True,
        }))
        self.assertEqual(Verdict.BLOCK, still_blocked.verdict)

    def test_unverified_continuity_cannot_align(self):
        result = evaluate(
            audit_request(), delivered_output_count=0, output_ledger_hash="d" * 64,
            output_ledger_verified=True, advisory_available=True,
            continuity_attestation_verified=False,
        )
        self.assertEqual(Verdict.BLOCK, result.verdict)
        self.assertIn("CONTINUITY_ATTESTATION_UNVERIFIED", result.reason_codes)

    def test_raw_instruction_and_description_fields_are_rejected(self):
        payload = request_payload()
        payload["latest_instruction"] = "password: hunter2"
        with self.assertRaisesRegex(ValidationError, "unknown_fields"):
            AuditRequest.from_dict(payload)
        with self.assertRaisesRegex(ValidationError, "unknown_fields"):
            AuditRequest.from_dict(request_payload(proposed_action={"description": "raw"}))

    def test_state_overclaims_block(self):
        deployed = self.evaluate(audit_request(proposed_action={"state_claims": {"deployed": True}}))
        proven = self.evaluate(audit_request(proposed_action={"state_claims": {"proven": True}}))
        autonomous = self.evaluate(audit_request(proposed_action={"state_claims": {"autonomous": True}}))
        self.assertIn("DEPLOYMENT_OVERCLAIM", deployed.reason_codes)
        self.assertIn("PROOF_OVERCLAIM", proven.reason_codes)
        self.assertIn("AUTONOMY_OVERCLAIM", autonomous.reason_codes)

    def test_owner_only_choice_is_not_decided(self):
        result = self.evaluate(audit_request(proposed_action={"owner_decision_required": True}))
        self.assertEqual(Verdict.SOVEREIGN_DECISION_REQUIRED, result.verdict)
        self.assertTrue(result.to_dict()["owner_action_required"])
        self.assertFalse(result.to_dict()["authorizes_action"])


if __name__ == "__main__":
    unittest.main()
