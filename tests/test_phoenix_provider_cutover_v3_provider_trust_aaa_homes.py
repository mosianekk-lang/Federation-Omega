from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.provider_trust import ChatGovProviderTrustInterlock
from bubbles.chat_governor_omega3.state import DurableState
from evidenceops.innovation_engine.algorithm_proof_state_transition_guard import ProofStateTransitionGuard
from evidenceops.provider_trust_adapter import EvidenceOpsProviderTrustAdapter
from evidenceops.truthgrid import MutationIntent, TruthGridViolation, TruthGridWriterAdapter
from evidenceops.truthgrid.provider_trust import TruthGridProviderTrustAdapter
from federation_consolidation.provider_trust_policy import validate_provider_trust_resolution
from federation_consolidation.provider_trust_resolver import (
    EVIDENCE_SCHEMA,
    ProviderTrustError,
    resolve_provider_trust,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "governance/provider_trust_contract_v1.json").read_text())
AAA_HOMES = json.loads((ROOT / "governance/provider_trust_aaa_receiving_homes_v1.json").read_text())
BINDING_ID = "FEDOMEGA_GITHUB_ACTIONS_OPENAI_PRIMARY"
ALIAS = "OPENAI_PRIMARY_RUNTIME"


def resolution(
    *,
    reference_found: bool = True,
    runtime_bound: bool = True,
    authenticated: bool = True,
    live: bool = False,
    error_code: str | None = None,
):
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "capability_alias": ALIAS,
        "binding_id": BINDING_ID if reference_found else None,
        "credential_reference_found": reference_found,
        "runtime_bound": runtime_bound,
        "provider_authenticated": authenticated,
        "provider_live_verified": live,
        "provider_error_code": error_code,
        "semantic_receipt_sha256": ("a" * 64) if live else None,
        "archive_readback_verified": False,
        "archive_sha256": None,
        "outer_workflow_success": True,
        "secret_value_recorded": False,
    }
    return resolve_provider_trust(CONTRACT, evidence)


class ProviderTrustAAAReceivingHomesTests(unittest.TestCase):
    def test_receiving_home_contract_preserves_local_authority(self):
        self.assertEqual(AAA_HOMES["source_capability"], ALIAS)
        self.assertEqual(set(AAA_HOMES["homes"]), {"EVIDENCEOPS", "TRUTHGRID", "CHATGOV"})
        for spec in AAA_HOMES["homes"].values():
            self.assertFalse(spec["consequential_authority_inherited"])

    def test_shared_resolution_receipt_is_hash_bound(self):
        live = resolution(live=True)
        validated = validate_provider_trust_resolution(live)
        self.assertEqual(validated["state"], "PROVIDER_LIVE_VERIFIED")
        tampered = dict(live)
        tampered["next_action"] = "OWNER_BOOTSTRAP_CREDENTIAL_REFERENCE"
        with self.assertRaises(ProviderTrustError):
            validate_provider_trust_resolution(tampered)

    def test_evidenceops_reuses_runtime_without_promoting_evidence(self):
        adapter = EvidenceOpsProviderTrustAdapter()
        live = resolution(live=True)
        decision = adapter.assess(live)
        self.assertTrue(decision.provider_runtime_ready)
        self.assertTrue(decision.may_invoke_provider)
        self.assertFalse(decision.may_promote_evidence)
        self.assertFalse(decision.may_promote_legal_claim)
        self.assertFalse(decision.consequential_authority_granted)

        provider_component = adapter.proof_component(live)
        result = ProofStateTransitionGuard().run(
            current_state="SOURCE_SUPPORTED",
            target_state="LIVE_READBACK",
            proof={
                "execution_receipt": provider_component,
                "target_readback": {"verified": True, "target_id": "target-1"},
            },
        )
        self.assertFalse(result.output["transition_permitted"])
        self.assertIn("EXECUTION_NOT_PROVEN:execution_receipt", result.violations)

    def test_evidenceops_accepts_provider_trust_only_as_additive_component(self):
        component = EvidenceOpsProviderTrustAdapter().proof_component(resolution(live=True))
        result = ProofStateTransitionGuard().run(
            current_state="SOURCE_SUPPORTED",
            target_state="LIVE_READBACK",
            proof={
                "provider_trust": component,
                "execution_receipt": {
                    "verified": True,
                    "receipt_id": "execution-receipt-1",
                    "target_id": "target-1",
                    "executed": True,
                    "semantic_match": True,
                },
                "target_readback": {"verified": True, "target_id": "target-1"},
            },
        )
        self.assertTrue(result.output["transition_permitted"])

    def test_truthgrid_provider_trust_never_bypasses_mutation_guard(self):
        calls: list[MutationIntent] = []
        observed: dict[str, object] = {}

        def writer(intent: MutationIntent):
            calls.append(intent)
            observed.clear()
            observed.update(intent.values)

        writer_adapter = TruthGridWriterAdapter(
            writer=writer,
            readback=lambda sheet, key: dict(observed),
        )
        adapter = TruthGridProviderTrustAdapter()
        live = resolution(live=True)

        safe = MutationIntent(
            sheet="CLAIMS",
            operation="UPDATE",
            target_key="claim-1",
            row_identity_resolved_by_key=True,
            values={"Status": "PENDING"},
        )
        receipt = adapter.execute_ai_assisted_mutation(
            resolution=live,
            writer_adapter=writer_adapter,
            intent=safe,
        )
        self.assertTrue(receipt.writer_receipt.provider_readback_verified)
        self.assertEqual(len(calls), 1)

        unsafe = MutationIntent(
            sheet="CLAIMS",
            operation="UPDATE",
            target_key="claim-2",
            row_identity_resolved_by_key=True,
            values={"Status": "VERIFIED"},
        )
        with self.assertRaisesRegex(TruthGridViolation, "RELEASE_PROMOTION_REQUIRES_RECEIPTS"):
            adapter.execute_ai_assisted_mutation(
                resolution=live,
                writer_adapter=writer_adapter,
                intent=unsafe,
            )
        self.assertEqual(len(calls), 1, "writer must not run when TruthGrid guard rejects mutation")

    def test_truthgrid_blocks_provider_stage_before_writer_when_not_live(self):
        calls: list[MutationIntent] = []
        writer_adapter = TruthGridWriterAdapter(
            writer=lambda intent: calls.append(intent),
            readback=lambda sheet, key: {},
        )
        intent = MutationIntent(
            sheet="CLAIMS",
            operation="UPDATE",
            target_key="claim-1",
            row_identity_resolved_by_key=True,
            values={"Status": "PENDING"},
        )
        billing = resolution(live=False, error_code="credit_balance_exhausted")
        with self.assertRaisesRegex(TruthGridViolation, "OPENAI_PROVIDER_TRUST_NOT_READY:BLOCKED_PROVIDER_BILLING"):
            TruthGridProviderTrustAdapter().execute_ai_assisted_mutation(
                resolution=billing,
                writer_adapter=writer_adapter,
                intent=intent,
            )
        self.assertEqual(calls, [])

    def test_chatgov_avoids_owner_prompt_when_system_can_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DurableState(str(Path(tmp) / "chatgov.sqlite3"))
            interlock = ChatGovProviderTrustInterlock(state)

            live = interlock.before_user_prompt("mission-live", resolution(live=True))
            self.assertTrue(live.provider_runtime_ready)
            self.assertFalse(live.should_prompt_owner)
            self.assertTrue(live.proof_bearing)
            self.assertFalse(live.consequential_authority_granted)

            transient = interlock.before_user_prompt(
                "mission-transient",
                resolution(live=False, error_code="rate_limit_exceeded"),
            )
            self.assertFalse(transient.should_prompt_owner)
            self.assertTrue(transient.system_action_available)
            self.assertEqual(transient.next_action, "RETRY_PROVIDER_PROBE")

    def test_chatgov_prompts_only_for_genuine_owner_provider_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DurableState(str(Path(tmp) / "chatgov.sqlite3"))
            interlock = ChatGovProviderTrustInterlock(state)

            billing = interlock.before_user_prompt(
                "mission-billing",
                resolution(live=False, error_code="credit_balance_exhausted"),
            )
            self.assertTrue(billing.should_prompt_owner)
            self.assertFalse(billing.credential_rotation_recommended)
            self.assertEqual(billing.next_action, "RESTORE_PROVIDER_BILLING")

            auth = interlock.before_user_prompt(
                "mission-auth",
                resolution(authenticated=False, live=False, error_code="invalid_api_key"),
            )
            self.assertTrue(auth.should_prompt_owner)
            self.assertTrue(auth.credential_rotation_recommended)
            self.assertEqual(auth.next_action, "ROTATE_OR_REBIND_CREDENTIAL")

            checkpoint = state.latest_checkpoint("mission-auth")
            self.assertIsNotNone(checkpoint)
            self.assertFalse(checkpoint["payload"]["consequential_authority_granted"])


if __name__ == "__main__":
    unittest.main()
