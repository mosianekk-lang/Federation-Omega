from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FederationAutomationAuthorityFabricTests(unittest.TestCase):
    def test_python_sources_parse(self):
        for relative in (
            "federation_automation_gateway/contracts.py",
            "federation_automation_gateway/policy.py",
            "federation_automation_gateway/google_executor.py",
            "federation_automation_gateway/sheets_bus.py",
            "federation_automation_gateway/app.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            ast.parse(source, filename=relative)

    def test_governance_contract_is_dual_executor_and_fail_closed(self):
        contract = json.loads(
            (ROOT / "governance/federation_automation_authority_fabric_v1.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(
            contract["control_plane"]["executors"]["google_cloud"],
            "private Cloud Run federation-automation-gateway",
        )
        self.assertEqual(
            contract["control_plane"]["executors"]["apps_script"],
            "owner-OAuth federation Apps Script broker",
        )
        activation = contract["activation_model"]
        self.assertEqual(
            activation["deployment_identity"],
            "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
        )
        self.assertEqual(
            activation["runtime_identity"],
            "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
        )
        self.assertEqual(activation["wif_provider"], "luna-automation-gateway")
        self.assertFalse(activation["legacy_bootstrap_identity_required"])
        self.assertEqual(
            activation["provider_admin_runtime_lane"],
            "UNBOUND_FAIL_CLOSED_UNTIL_SEPARATELY_ADMITTED",
        )
        invariants = set(contract["security_invariants"])
        self.assertIn("NO_SERVICE_ACCOUNT_PRIVATE_KEYS", invariants)
        self.assertIn("WORKFLOW_SCOPED_WIF_PROVIDER", invariants)
        self.assertIn("DEPLOYER_AND_RUNTIME_IDENTITIES_SEPARATE", invariants)
        self.assertIn("PROVIDER_ADMIN_RUNTIME_LANE_FAILS_CLOSED_WHEN_UNBOUND", invariants)
        self.assertIn("OWNER_OAUTH_NEVER_EXPORTED_TO_CHAT_OR_CLOUD_RUN", invariants)
        self.assertIn("OUTBOUND_COMMUNICATION_EXCLUDED_FROM_REUSABLE_LEASES", invariants)
        self.assertIn("DESTRUCTIVE_ACTIONS_EXCLUDED_FROM_REUSABLE_LEASES", invariants)

    def test_cloud_executor_does_not_call_apps_script_api(self):
        source = (ROOT / "federation_automation_gateway/google_executor.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("script.googleapis.com", source)
        self.assertNotIn('"APPS_SCRIPT_RUN"', source)
        self.assertIn('SUPPORTED_ADAPTERS = frozenset({"google_cloud"})', source)

    def test_cloud_worker_leaves_apps_script_rows_for_owner_broker(self):
        source = (ROOT / "federation_automation_gateway/app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("if command.adapter_id not in executor.SUPPORTED_ADAPTERS", source)
        self.assertIn('"apps_script_route": "OWNER_OAUTH_BROKER"', source)

    def test_owner_broker_uses_user_oauth_and_canonical_target_registry(self):
        source = (ROOT / "apps_script_owner_broker/FED_Automation_Broker.gs").read_text(
            encoding="utf-8"
        )
        self.assertIn("ScriptApp.getOAuthToken()", source)
        self.assertIn("LAB_REGISTRY", source)
        self.assertIn("FED_asCanonicalTargetSet_", source)
        self.assertIn("FED_asBackup_", source)
        self.assertIn("FED_asRestoreBackup_", source)
        self.assertNotIn("private_key", source.lower())
        self.assertNotIn("client_secret", source.lower())

    def test_reanchored_activation_does_not_recreate_legacy_bootstrap(self):
        workflow = (
            ROOT / ".github/workflows/federation-automation-gateway-activate.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("federation-bootstrap-admin", workflow)
        self.assertNotIn("BOOTSTRAP_AUTHORITY_EXPIRED", workflow)
        self.assertNotIn("service-accounts create", workflow)
        self.assertNotIn("gcloud services enable", workflow)
        self.assertIn("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com", workflow)
        self.assertIn("superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", workflow)
        self.assertIn("providers/luna-automation-gateway", workflow)

    def test_apps_script_broker_javascript_parses_when_node_is_available(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        source = (ROOT / "apps_script_owner_broker/FED_Automation_Broker.gs").read_text(
            encoding="utf-8"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(source)
            handle.flush()
            result = __import__("subprocess").run(
                [node, "--check", handle.name],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
