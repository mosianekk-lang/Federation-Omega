from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLANE = ROOT / "windows_federation_plane"
WORKFLOW = ROOT / ".github/workflows/fuse-windows-execution-plane-v1.yml"
RELAY_WORKFLOW = ROOT / ".github/workflows/fuse-windows-relay-cloud-run-v1.yml"

class FederationWindowsPlaneSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PLANE.is_dir() or not WORKFLOW.is_file(): raise unittest.SkipTest("workflow-free export excludes Windows execution surfaces")

    def test_complete_project_contract_exists(self):
        for name in ("README.md", "FORMATION_SPEC.md", "PROJECT_MEMORY.md", "AI_HANDOFF.md", "THREAT_MODEL.md", "BUILD_CONTRACT.json"):
            self.assertTrue((PLANE / name).is_file(), name)

    def test_workflow_is_windows_and_least_privilege(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: windows-latest", source); self.assertIn("contents: read", source); self.assertNotIn("id-token: write", source)
        self.assertIn("persist-credentials: false", source); self.assertIn("timeout-minutes: 15", source); self.assertIn("github.event.pull_request.head.sha || github.sha", source); self.assertIn("verify_receipt_mapping", source)
        self.assertNotIn("actions/checkout@v", source); self.assertNotIn("actions/setup-python@v", source); self.assertNotIn("actions/upload-artifact@v", source)

    def test_relay_provider_route_is_asymmetric_and_secret_manager_independent(self):
        if not RELAY_WORKFLOW.is_file(): self.skipTest("workflow-free export excludes relay provider surface")
        source = RELAY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("FUSE Windows Relay Cloud Run v2.4", source)
        self.assertIn("github.event.issue.title == '[FO-DISPATCH] FUSE_WINDOWS_RELAY_CLOUD_RUN_V2'", source)
        self.assertIn("github.event.issue.author_association == 'OWNER'", source)
        self.assertIn("DEVICE_AUTH_MODE=ECDSA_P256_PUBLIC_KEY", source)
        self.assertIn("Qualify provider prerequisites without secret-manager dependency", source)
        for required in ("gcloud artifacts repositories describe","gcloud firestore databases describe","gcloud builds list","gcloud run services list","MCP_FAIL_CLOSED_CHECKED=true","BROWSER_ENTRYPOINT_CHECKED=true","ZERO_TRAFFIC_CHECKED=true"):
            self.assertIn(required, source)
        for forbidden in ("gcloud services enable","add-iam-policy-binding","firestore databases create","fields ttls update","gcloud secrets","--set-secrets="):
            self.assertNotIn(forbidden, source)
        self.assertIn('"secret_manager_required": False', source)
        self.assertIn('"secret_value_recorded": False', source)

    def test_agent_and_browser_source_bind_public_key_auth(self):
        mcp = (PLANE / "src/federation_windows_plane/mcp_service.py").read_text(encoding="utf-8")
        relay = (PLANE / "src/federation_windows_plane/firestore_relay.py").read_text(encoding="utf-8")
        agent = (PLANE / "src/federation_windows_plane/relay_agent.py").read_text(encoding="utf-8")
        self.assertIn("public_key_spki_b64", mcp); self.assertIn("ECDSA_P256", mcp); self.assertIn("crypto.subtle.sign", mcp)
        self.assertIn("auth_mode\": \"ECDSA_P256", relay); self.assertIn("ECDSASigner.verify_spki_b64", relay); self.assertIn("DEVICE_PUBLIC_KEY_REQUIRED", relay)
        self.assertIn("SOFTWARE_DPAPI_LOWER_ASSURANCE", agent); self.assertIn("ec.generate_private_key", agent); self.assertIn("LEGACY_HMAC_CREDENTIAL_REENROLL_REQUIRED", agent); self.assertNotIn('"device_secret":', agent)

    def test_no_arbitrary_command_surface(self):
        source = (PLANE / "src/federation_windows_plane/executor.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "shell=True", "Invoke-Expression"): self.assertNotIn(forbidden, source)
        cli = (PLANE / "src/federation_windows_plane/cli.py").read_text(encoding="utf-8"); self.assertNotIn('"--envelope"', cli)

    def test_governance_is_additive(self):
        data = json.loads((ROOT / "governance/fuse_windows_execution_plane_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(data["parent_controller"], "FUSE-OMEGA-INFINITY"); self.assertFalse(data["creates_new_sovereign_plane"]); self.assertEqual(data["provider_effect"], "NONE_UNTIL_SEPARATELY_AUTHORIZED")

    def test_airlock_admits_only_the_bounded_workflow_events(self):
        workflow = ".github/workflows/fuse-windows-execution-plane-v1.yml"; policy = json.loads((ROOT / "governance/github_airlock_policy.json").read_text(encoding="utf-8"))
        self.assertIn(workflow, policy["active_workflow_allowlist"]); self.assertIn(workflow, policy["execution_quarantine"]["keep_active"]); self.assertEqual(policy["allowed_events"][workflow], ["pull_request", "workflow_dispatch"]); self.assertNotIn(workflow, policy["oidc_workflow_allowlist"]); self.assertNotIn(workflow, policy["provider_mutation_workflow_allowlist"])

if __name__ == "__main__": unittest.main()
