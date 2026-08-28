import json
import unittest
from pathlib import Path

from federation.capital_execution.venues.luno_account_observer import LunoCredentialReference, LunoReadOnlyAccountObserver
from federation.capital_execution.venues.luno_observer_runtime import ACCOUNT_READ_ONLY, PUBLIC_ONLY, BindingContext, Handler, LunoObserverRuntime, build_binding_context
from federation.capital_execution.venues.luno_permission_proof import REQUIRED_READ_PERMISSIONS, key_id_fingerprint, parse_permission_proof


class LunoObserverProviderBindingV12Tests(unittest.TestCase):
    KEY_ID = "observer-key-id"

    def proof_json(self, *, permissions=None, key_id=None):
        return json.dumps({
            "schema": "LUNO-OBSERVER-PERMISSION-PROOF-1",
            "key_id_sha256": key_id_fingerprint(key_id or self.KEY_ID),
            "permissions": list(permissions or REQUIRED_READ_PERMISSIONS),
            "source_ref": "luno-api-key-creation-ui:owner-attestation",
            "attested_at": "2026-08-27T19:00:00+00:00",
        })

    def test_valid_permission_proof_is_bound_to_key_fingerprint(self):
        proof = parse_permission_proof(self.proof_json(), key_id=self.KEY_ID)
        self.assertEqual(set(proof.permissions), set(REQUIRED_READ_PERMISSIONS))
        self.assertEqual(len(proof.digest()), 64)

    def test_permission_proof_rejects_different_key(self):
        with self.assertRaises(PermissionError):
            parse_permission_proof(self.proof_json(), key_id="different-key")

    def test_permission_proof_rejects_any_write_authority_or_extra_permission(self):
        permissions = tuple(REQUIRED_READ_PERMISSIONS) + ("Perm_W_Send",)
        with self.assertRaises(PermissionError):
            parse_permission_proof(self.proof_json(permissions=permissions), key_id=self.KEY_ID)

    def test_public_mode_requires_no_account_credentials(self):
        context = build_binding_context({"LUNO_BINDING_MODE": "PUBLIC_ONLY"})
        self.assertEqual(context.mode, PUBLIC_ONLY)
        self.assertFalse(context.observer_bound)
        self.assertIsNone(context.proof_digest)

    def test_account_mode_requires_complete_dedicated_bundle(self):
        with self.assertRaises(PermissionError):
            build_binding_context({"LUNO_BINDING_MODE": "ACCOUNT_READ_ONLY", "LUNO_OBSERVER_KEY_ID": self.KEY_ID})

    def test_account_mode_validates_permission_proof_before_binding(self):
        context = build_binding_context({
            "LUNO_BINDING_MODE": "ACCOUNT_READ_ONLY",
            "LUNO_OBSERVER_KEY_ID": self.KEY_ID,
            "LUNO_OBSERVER_KEY_MATERIAL": "fixture-material",
            "LUNO_OBSERVER_PERMISSION_PROOF": self.proof_json(),
        })
        self.assertEqual(context.mode, ACCOUNT_READ_ONLY)
        self.assertTrue(context.observer_bound)
        self.assertEqual(context.key_id, self.KEY_ID)

    def test_generic_observer_remains_backward_compatible_with_narrow_read_subset(self):
        credential = LunoCredentialReference("runtime-ref://fixture", ("Perm_R_Balance",))
        credential.validate()
        with self.assertRaises(PermissionError):
            LunoCredentialReference("runtime-ref://fixture", ("Perm_W_Orders",)).validate()

    def test_transaction_reader_uses_get_only_dynamic_allowlist(self):
        observed = {}
        def transport(path, params, key_id, material):
            observed["path"] = path
            observed["params"] = dict(params)
            return {"transactions": []}
        observer = LunoReadOnlyAccountObserver(
            LunoCredentialReference("runtime-ref://fixture", ("Perm_R_Transactions",)),
            lambda _ref: (self.KEY_ID, "fixture-material"),
            transport,
        )
        result = observer.account_transactions(12345, min_row=-1, max_row=0)
        self.assertEqual(result["transactions"], [])
        self.assertEqual(observed["path"], "/api/1/accounts/12345/transactions")
        self.assertEqual(observed["params"], {"min_row": -1, "max_row": 0})

    def test_all_known_financial_write_methods_fail_closed(self):
        observer = LunoReadOnlyAccountObserver(
            LunoCredentialReference("runtime-ref://fixture", ("Perm_R_Balance",)),
            lambda _ref: (self.KEY_ID, "fixture-material"),
            lambda *args: {},
        )
        for name in ("create_order", "cancel_order", "convert", "send", "withdraw", "transfer"):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                getattr(observer, name)()

    def test_http_runtime_denies_all_mutating_verbs(self):
        self.assertIs(Handler.do_POST, Handler._deny_write)
        self.assertIs(Handler.do_PUT, Handler._deny_write)
        self.assertIs(Handler.do_PATCH, Handler._deny_write)
        self.assertIs(Handler.do_DELETE, Handler._deny_write)

    def test_semantic_account_canary_returns_structure_not_private_values(self):
        proof = parse_permission_proof(self.proof_json(), key_id=self.KEY_ID)
        runtime = LunoObserverRuntime(BindingContext(ACCOUNT_READ_ONLY, self.KEY_ID, "fixture-material", proof))
        class FakeAccount:
            def balances(self):
                return {"balance": [{"account_id": 123, "asset": "ZAR", "balance": "999.99"}]}
            def list_orders(self, **kwargs):
                return {"orders": [{"order_id": "private-order"}]}
            def fee_info(self, pair):
                return {"maker_fee": "0.001", "taker_fee": "0.002", "thirty_day_volume": "123"}
            def account_transactions(self, *args, **kwargs):
                return {"transactions": [{"row_index": 1, "balance": "999.99"}]}
        runtime.account = FakeAccount()
        result = runtime.account_semantic_summary("XBTZAR")
        self.assertEqual(result["state"], "AUTHENTICATED_READ_ONLY_SEMANTIC_CANARY_VERIFIED")
        self.assertFalse(result["private_values_returned"])
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("999.99", serialized)
        self.assertNotIn("private-order", serialized)

    def test_binding_contract_rejects_legacy_credentials_and_requires_exact_read_set(self):
        contract = json.loads(Path("federation/capital_execution/venues/LUNO_OBSERVER_BINDING_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["credential_binding"]["legacy_secret_names_accepted"])
        self.assertEqual(set(contract["credential_binding"]["exact_permissions"]), set(REQUIRED_READ_PERMISSIONS))
        self.assertFalse(contract["financial_effects"])
        self.assertFalse(contract["provider_write_operations"])
        self.assertIn("SHADOW_MODE_REMAINS_THE_CAPITAL_CEILING", contract["invariants"])

    def test_binding_contract_is_governed_by_exact_jarvis_ao5_realityguard_contract(self):
        contract = json.loads(Path("federation/capital_execution/venues/LUNO_OBSERVER_BINDING_CONTRACT.json").read_text(encoding="utf-8"))
        authority = contract["control_authority"]
        self.assertEqual(authority["engine_id"], "JARVIS-ALPHA-OMEGA-5-SOVEREIGN")
        self.assertEqual(authority["engine_version"], "ΑΩ5.0")
        self.assertEqual(
            authority["canonical_governance_contract"],
            "governance/jarvis_ao5_forensic_decision_intelligence_v1.json",
        )
        self.assertEqual(
            authority["canonical_spec_sha256"],
            "773ee29579605aa3f3b956a27af3e5ac5dd7c3a28e524f61cd8c392451366443",
        )
        self.assertTrue(authority["realityguard_execution_receipt_required"])
        self.assertEqual(
            authority["completion_standard"],
            ["AUTHORISATION", "EXECUTION", "TARGET_READBACK", "RECEIPT"],
        )
        self.assertTrue(authority["consequential_external_action_requires_owner_approval"])
        self.assertTrue(authority["provider_state_must_match_readback"])
        self.assertIn("JARVIS_AO5_REALITYGUARD_CONTROLS_PROVIDER_STATE_CLAIMS", contract["invariants"])


if __name__ == "__main__":
    unittest.main()
