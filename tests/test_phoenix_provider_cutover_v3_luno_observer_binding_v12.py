import json
import unittest
from pathlib import Path

from federation.capital_execution.venues.luno_observer_runtime import Handler, build_binding_context
from federation.capital_execution.venues.luno_permission_proof import REQUIRED_READ_PERMISSIONS, key_id_fingerprint, parse_permission_proof


class LunoObserverBindingAirlockBridgeTests(unittest.TestCase):
    def test_public_provider_success_cannot_imply_account_binding(self):
        context = build_binding_context({"LUNO_BINDING_MODE": "PUBLIC_ONLY"})
        self.assertFalse(context.observer_bound)
        self.assertEqual(context.mode, "PUBLIC_ONLY")

    def test_account_binding_requires_exact_read_set_and_key_identity(self):
        key_id = "fixture-key-id"
        raw = json.dumps({
            "schema": "LUNO-OBSERVER-PERMISSION-PROOF-1",
            "key_id_sha256": key_id_fingerprint(key_id),
            "permissions": list(REQUIRED_READ_PERMISSIONS),
            "source_ref": "provider-ui:attested-key-creation",
            "attested_at": "2026-08-27T19:00:00+00:00",
        })
        proof = parse_permission_proof(raw, key_id=key_id)
        self.assertEqual(set(proof.permissions), set(REQUIRED_READ_PERMISSIONS))

    def test_provider_runtime_has_no_mutating_http_verb(self):
        for verb in ("do_POST", "do_PUT", "do_PATCH", "do_DELETE"):
            self.assertIs(getattr(Handler, verb), Handler._deny_write)

    def test_contract_hard_disables_legacy_credentials_and_financial_effects(self):
        contract = json.loads(Path("federation/capital_execution/venues/LUNO_OBSERVER_BINDING_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertFalse(contract["financial_effects"])
        self.assertFalse(contract["provider_write_operations"])
        self.assertFalse(contract["credential_binding"]["legacy_secret_names_accepted"])
        self.assertIn("SHADOW_MODE_REMAINS_THE_CAPITAL_CEILING", contract["invariants"])

    def test_provider_workflow_remains_read_only_zero_traffic_and_no_legacy_secret_import(self):
        workflow = Path(".github/workflows/luno-observer-provider-binding.yml").read_text(encoding="utf-8")
        self.assertIn("github.event_name == 'push' || github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("CREDENTIAL_PERMISSION_PROOF_REQUIRED", workflow)
        self.assertIn("PUBLIC_MARKET_PROVIDER_VERIFIED", workflow)
        self.assertIn("OBSERVER_BOUND", workflow)
        self.assertIn("--no-traffic", workflow)
        self.assertNotIn("luno-api-key", workflow)
        self.assertNotIn("luno-api-secret", workflow)
        self.assertNotIn("scheduler jobs create", workflow.lower())

    def test_container_is_non_root_and_public_only_by_default(self):
        dockerfile = Path("federation/capital_execution/venues/Dockerfile.luno_observer").read_text(encoding="utf-8")
        self.assertIn("USER observer", dockerfile)
        self.assertIn("LUNO_BINDING_MODE=PUBLIC_ONLY", dockerfile)

    def test_legacy_crosswalk_quarantines_execution_heartbeat_and_order_methods(self):
        text = Path("federation/capital_execution/venues/LEGACY_OMEGA_MAX_CROSSWALK.md").read_text(encoding="utf-8")
        self.assertIn("Quarantined legacy behavior", text)
        self.assertIn("Any 24/7 autonomous execution loop", text)
        self.assertIn("post_limit_order", text)
        self.assertIn("Legacy EXE", text)


if __name__ == "__main__":
    unittest.main()
