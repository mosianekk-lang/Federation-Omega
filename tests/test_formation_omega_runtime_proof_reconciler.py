from __future__ import annotations

import unittest

from formation_omega.runtime_proof_reconciler import (
    RuntimeProofReconciler,
    RuntimeProofStage,
)


R = RuntimeProofReconciler()


def source_receipt():
    return {
        "schema": R.SOURCE_SCHEMA,
        "verified": True,
        "commit_sha": "9add7048dc9835f3f20baa3f4301c2071c629ef0",
    }


def live_readback(state="LIVE_ENCRYPTED_SPOOL_RECEIPT_OBSERVED"):
    return {
        "schema": R.READBACK_SCHEMA,
        "state": state,
        "nativeHostRegistered": True,
        "nativeHostManifestValid": True,
        "nativeHostExecutableValid": True,
        "nativeHostSha256": "a" * 64,
        "chatBridgeExtensionId": R.CHATBRIDGE_EXTENSION_ID,
        "befEdgeExtensionId": R.BEF_EXTENSION_ID,
        "chatBridgeProfilePresent": True,
        "befEdgeProfilePresent": True,
        "encryptedSpoolReceiptCount": 1,
        "latestStoredEncrypted": True,
        "latestSpoolReceiptId": "receipt-1",
        "latestEnvelopeSha256": "b" * 64,
    }


def dpf_receipt(provider_native_complete=False):
    return {
        "state": R.DPF_SCHEMA,
        "conversationKey": "conversation-1",
        "evidence": {
            "capture_scope": "RENDERED_DOM",
            "provider_native_complete": provider_native_complete,
            "exact_rendered_transcript_complete": True,
            "missing_ranges": [],
            "unresolved_artifacts": [],
            "stored_encrypted": True,
            "evidence_fingerprint": "b" * 64,
            "spool_receipt_id": "receipt-1",
            "truth_boundary": R.TRUTH_BOUNDARY,
        },
    }


def rollback_receipt():
    return {
        "Schema": R.ROLLBACK_SCHEMA,
        "State": "CANARY_RUNTIME_BINDING_ROLLED_BACK",
        "RegistryBindingRemoved": True,
        "EncryptedSpoolPreserved": True,
    }


def resilience_receipt():
    return {
        "schema": R.RESILIENCE_SCHEMA,
        "successfulRepetitions": 3,
        "rollbackRecoveryPassed": True,
        "freshReadbackPassed": True,
        "truthBoundaryRegression": False,
    }


class RuntimeProofReconcilerTests(unittest.TestCase):
    def test_source_admission_is_first_exposable_stage(self):
        result = R.reconcile([source_receipt()])
        self.assertEqual(result.stage, RuntimeProofStage.SOURCE_ADMITTED)
        self.assertTrue(result.valid)

    def test_live_readback_proves_contiguous_build_register_bind_and_delivery(self):
        result = R.reconcile([source_receipt(), live_readback()])
        self.assertEqual(result.stage, RuntimeProofStage.LIVE_DELIVERY)
        self.assertEqual(
            result.satisfied_stages,
            (
                "SOURCE_ADMITTED",
                "NATIVE_HOST_BUILT",
                "NATIVE_HOST_REGISTERED",
                "BROWSER_BOUND",
                "LIVE_DELIVERY",
            ),
        )

    def test_live_state_without_encrypted_receipt_is_blocked(self):
        receipt = live_readback()
        receipt["latestStoredEncrypted"] = False
        result = R.reconcile([source_receipt(), receipt])
        self.assertEqual(result.stage, RuntimeProofStage.BROWSER_BOUND)
        self.assertIn("LIVE_DELIVERY_STATE_WITHOUT_COMPLETE_READBACK", result.violations)

    def test_gap_free_observable_dpf_advances_only_rendered_scope(self):
        result = R.reconcile([source_receipt(), live_readback(), dpf_receipt()])
        self.assertEqual(result.stage, RuntimeProofStage.OBSERVABLE_DPF_VERIFIED)
        self.assertFalse(result.provider_native_complete)
        self.assertIn("PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED", result.truth_boundary)

    def test_provider_native_scope_escalation_is_rejected(self):
        result = R.reconcile(
            [source_receipt(), live_readback(), dpf_receipt(provider_native_complete=True)]
        )
        self.assertEqual(result.stage, RuntimeProofStage.LIVE_DELIVERY)
        self.assertIn("OBSERVABLE_SCOPE_ESCALATION_FORBIDDEN", result.violations)

    def test_power_shell_schema_casing_is_accepted_for_rollback(self):
        result = R.reconcile(
            [source_receipt(), live_readback(), dpf_receipt(), rollback_receipt()]
        )
        self.assertEqual(result.stage, RuntimeProofStage.ROLLBACK_VERIFIED)

    def test_resilience_requires_three_successful_repetitions_and_recovery(self):
        result = R.reconcile(
            [
                source_receipt(),
                live_readback(),
                dpf_receipt(),
                rollback_receipt(),
                resilience_receipt(),
            ]
        )
        self.assertEqual(result.stage, RuntimeProofStage.RESILIENCE_VERIFIED)
        self.assertTrue(result.valid)

    def test_out_of_order_receipt_cannot_skip_missing_stages(self):
        result = R.reconcile([source_receipt(), dpf_receipt(), rollback_receipt()])
        self.assertEqual(result.stage, RuntimeProofStage.SOURCE_ADMITTED)

    def test_unknown_schema_is_fail_closed(self):
        result = R.reconcile([source_receipt(), {"schema": "UNKNOWN-RUNTIME-CLAIM", "verified": True}])
        self.assertEqual(result.stage, RuntimeProofStage.SOURCE_ADMITTED)
        self.assertFalse(result.valid)
        self.assertIn("UNKNOWN-RUNTIME-CLAIM", result.unsupported_schemas)

    def test_receipt_chain_is_deterministic_and_order_sensitive(self):
        one = source_receipt()
        two = live_readback()
        first = R.reconcile([one, two])
        again = R.reconcile([one, two])
        reversed_result = R.reconcile([two, one])
        self.assertEqual(first.chain_head_sha256, again.chain_head_sha256)
        self.assertNotEqual(first.chain_head_sha256, reversed_result.chain_head_sha256)
        self.assertEqual(len(first.chain_head_sha256), 64)

    def test_extension_identity_drift_invalidates_snapshot(self):
        receipt = live_readback()
        receipt["befEdgeExtensionId"] = "wrong-extension"
        result = R.reconcile([source_receipt(), receipt])
        self.assertIn("BEF_EXTENSION_IDENTITY_MISMATCH", result.violations)
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
