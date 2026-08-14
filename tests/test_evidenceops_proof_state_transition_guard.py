from __future__ import annotations

import unittest

from evidenceops.innovation_engine.algorithm_proof_state_transition_guard import (
    ProofStateTransitionGuard,
)


class EvidenceOpsProofStateTransitionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = ProofStateTransitionGuard()

    def test_label_only_live_readback_jump_fails_closed(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="LIVE_READBACK",
            proof={"execution_receipt": "LABEL_ONLY", "target_readback": "LABEL_ONLY"},
        )
        self.assertEqual("TRANSITION_BLOCKED", result.status)
        self.assertIn("INVALID_PROOF_ENVELOPE:execution_receipt", result.violations)
        self.assertIn("INVALID_PROOF_ENVELOPE:target_readback", result.violations)

    def test_label_only_federation_verified_jump_fails_closed(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="FEDERATION_VERIFIED",
            proof={
                "federation_receipt": "LABEL_ONLY",
                "member_scope_proof": "LABEL_ONLY",
                "no_trust_transfer_test": "LABEL_ONLY",
            },
        )
        self.assertEqual("TRANSITION_BLOCKED", result.status)
        self.assertIn("INVALID_PROOF_ENVELOPE:federation_receipt", result.violations)
        self.assertIn("INVALID_PROOF_ENVELOPE:member_scope_proof", result.violations)
        self.assertIn("INVALID_PROOF_ENVELOPE:no_trust_transfer_test", result.violations)

    def test_label_only_released_jump_fails_closed(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="RELEASED",
            proof={
                "owner_approval": "LABEL_ONLY",
                "release_receipt": "LABEL_ONLY",
                "target_readback": "LABEL_ONLY",
            },
        )
        self.assertEqual("TRANSITION_BLOCKED", result.status)
        self.assertIn("INVALID_PROOF_ENVELOPE:owner_approval", result.violations)
        self.assertIn("INVALID_PROOF_ENVELOPE:release_receipt", result.violations)
        self.assertIn("INVALID_PROOF_ENVELOPE:target_readback", result.violations)

    def test_structured_live_readback_can_pass(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="LIVE_READBACK",
            proof={
                "execution_receipt": {
                    "receipt_id": "RCP-LIVE-001",
                    "target_id": "T1",
                    "executed": True,
                    "semantic_match": True,
                    "verified": True,
                },
                "target_readback": {
                    "target_id": "T1",
                    "state": "EXPECTED",
                    "verified": True,
                },
            },
        )
        self.assertEqual("TRANSITION_PERMITTED", result.status)

    def test_structured_federation_verified_can_pass(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="FEDERATION_VERIFIED",
            proof={
                "federation_receipt": {
                    "receipt_id": "RCP-FED-001",
                    "system_id": "SYS-1",
                    "verified": True,
                },
                "member_scope_proof": {
                    "members": ["SYS-1", "SYS-2"],
                    "scope_ref": "SCOPE-1",
                    "verified": True,
                },
                "no_trust_transfer_test": {
                    "passed": True,
                    "verified": True,
                },
            },
        )
        self.assertEqual("TRANSITION_PERMITTED", result.status)

    def test_structured_release_can_pass(self) -> None:
        result = self.guard.run(
            current_state="NO_EVIDENCE",
            target_state="RELEASED",
            proof={
                "owner_approval": {
                    "approved_by": "OWNER-1",
                    "approved_at": "2026-08-14T00:00:00Z",
                    "scope": "ART-1",
                    "verified": True,
                },
                "release_receipt": {
                    "receipt_id": "RCP-REL-001",
                    "artifact_id": "ART-1",
                    "verified": True,
                },
                "target_readback": {
                    "artifact_id": "ART-1",
                    "state": "RELEASED",
                    "verified": True,
                },
            },
        )
        self.assertEqual("TRANSITION_PERMITTED", result.status)

    def test_existing_prototype_string_proof_contract_is_unchanged(self) -> None:
        result = self.guard.run(
            current_state="SOURCE_SUPPORTED",
            target_state="PROTOTYPE_PASSED",
            proof={
                "prototype_receipt": "cycle:ROOT-CANARY",
                "rollback_test": "read-only no-mutation rollback",
            },
        )
        self.assertEqual("TRANSITION_PERMITTED", result.status)
        self.assertFalse(result.output["semantic_envelope_required"])


if __name__ == "__main__":
    unittest.main()
