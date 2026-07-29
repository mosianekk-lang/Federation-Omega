import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from superior_logic.oops_acme import (
    ActionClass,
    ContinuationContext,
    ContinuationDecision,
    ExternalActionAuthorization,
    ExternalActionDecision,
    ExternalActionPayload,
    evaluate_continuation,
    evaluate_external_action,
)
from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.service import create_app


def send_payload(**overrides):
    values = dict(
        action="send email",
        account="kim@example.com",
        targets=("recipient@example.com",),
        subject="Approved subject",
        body_hash="body123",
        attachment_hashes=("attachment123",),
        consequences=("external transmission",),
        action_class=ActionClass.EXTERNAL_CONSEQUENTIAL,
    )
    values.update(overrides)
    return ExternalActionPayload(**values)


def send_approval(**overrides):
    values = dict(
        approval_reference="APPROVAL-1",
        authorized=True,
        action="send email",
        account="kim@example.com",
        targets=("recipient@example.com",),
        subject="Approved subject",
        body_hash="body123",
        attachment_hashes=("attachment123",),
        consequences=("external transmission",),
        prohibitions=(),
    )
    values.update(overrides)
    return ExternalActionAuthorization(**values)


class OopsAcmeGuardTests(unittest.TestCase):
    def test_n_produce_and_stop_before_send_blocks_send(self):
        result = evaluate_external_action(
            send_payload(),
            send_approval(
                authorized=False,
                prohibitions=("external_send_authorized:false", "stop before sending"),
            ),
            connector_available=True,
        )
        self.assertEqual(ExternalActionDecision.BLOCK, result.decision)
        self.assertIn("conflicting_prohibition", result.missing_conditions)
        self.assertTrue(result.connector_is_not_authority)

    def test_production_approval_cannot_authorize_send(self):
        result = evaluate_external_action(
            send_payload(), send_approval(action="produce final document")
        )
        self.assertFalse(result.allowed)
        self.assertIn("action", result.mismatched_fields)

    def test_payload_change_invalidates_approval(self):
        result = evaluate_external_action(
            send_payload(subject="Changed subject"), send_approval()
        )
        self.assertFalse(result.allowed)
        self.assertIn("subject", result.mismatched_fields)

    def test_connector_availability_is_not_authority(self):
        result = evaluate_external_action(
            send_payload(), None, connector_available=True
        )
        self.assertFalse(result.allowed)
        self.assertTrue(result.connector_is_not_authority)

    def test_exact_authorization_allows_external_action(self):
        result = evaluate_external_action(send_payload(), send_approval())
        self.assertTrue(result.allowed)
        self.assertEqual(ExternalActionDecision.ALLOW, result.decision)

    def test_internal_reversible_work_continues_without_new_n(self):
        result = evaluate_continuation(
            ContinuationContext(work_authorized=True, material_work_available=True)
        )
        self.assertEqual(ContinuationDecision.CONTINUE_ACTIVE_TURN, result.decision)
        self.assertFalse(result.ask_owner)

    def test_only_material_a_to_e_input_is_requested(self):
        result = evaluate_continuation(
            ContinuationContext(
                work_authorized=True,
                material_work_available=True,
                outcome_choice_needed=True,
            )
        )
        self.assertTrue(result.ask_owner)
        self.assertEqual(("OUTCOME_CHOICE",), result.material_input_reasons)

    def test_background_claim_blocked_without_carrier(self):
        result = evaluate_continuation(
            ContinuationContext(
                work_authorized=True,
                material_work_available=False,
                current_turn_active=False,
                persistent_runtime_proven=False,
            )
        )
        self.assertEqual(ContinuationDecision.PARTIAL_PRESERVED, result.decision)
        self.assertFalse(result.background_execution_allowed)

    def test_non_delegable_act_requires_owner(self):
        result = evaluate_external_action(
            send_payload(
                action="sign legal agreement",
                action_class=ActionClass.NON_DELEGABLE_PERSONAL,
            ),
            None,
        )
        self.assertEqual(
            ExternalActionDecision.OWNER_DECISION_REQUIRED, result.decision
        )


class OopsAcmeAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "oops-acme.db")
        self.client = TestClient(create_app(self.runtime))

    def tearDown(self):
        self.client.close()
        self.runtime.close()
        self.tmp.cleanup()

    def test_external_authorization_endpoint_blocks_dhet_pattern(self):
        response = self.client.post(
            "/actions/evaluate-authorization",
            json={
                "payload": {
                    "action": "send email",
                    "account": "kim@example.com",
                    "targets": ["recipient@example.com"],
                    "subject": "Approved subject",
                    "body_hash": "body123",
                    "attachment_hashes": ["attachment123"],
                    "consequences": ["external transmission"],
                    "action_class": "EXTERNAL_CONSEQUENTIAL",
                },
                "authorization": {
                    "approval_reference": "DHET-APPROVAL-RECORD",
                    "authorized": False,
                    "action": "produce final document",
                    "account": "kim@example.com",
                    "targets": [],
                    "subject": "",
                    "body_hash": "body123",
                    "attachment_hashes": ["attachment123"],
                    "consequences": [],
                    "prohibitions": [
                        "external_send_authorized:false",
                        "stop before sending",
                    ],
                },
                "connector_available": True,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("BLOCK", payload["decision"])
        self.assertIn("conflicting_prohibition", payload["missing_conditions"])
        self.assertIn("action", payload["mismatched_fields"])
        self.assertTrue(self.runtime.verify_event_chain())

    def test_continuation_endpoint_only_asks_for_material_choice(self):
        response = self.client.post(
            "/continuation/evaluate",
            json={
                "work_authorized": True,
                "material_work_available": True,
                "outcome_choice_needed": True,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("ASK_OWNER", payload["decision"])
        self.assertEqual(["OUTCOME_CHOICE"], payload["material_input_reasons"])
        self.assertTrue(self.runtime.verify_event_chain())

    def test_health_exposes_oops_and_acme_controls(self):
        payload = self.client.get("/health").json()
        self.assertIn("OOPS_EXTERNAL_ACTION_GATE", payload["slrk_controls"])
        self.assertIn("ACME_CONTINUATION_GATE", payload["slrk_controls"])


if __name__ == "__main__":
    unittest.main()
