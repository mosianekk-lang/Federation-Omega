import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-windows-h1-machine-dispatch-adapter-v1.yml"
TARGET_WORKFLOW = "fuse-windows-h1-provider-relay-v2.yml"
PHOENIX_PATH = ".github/workflows/phoenix-emergency-freeze.yml"
RUNS_PATH = Path("/tmp/windows-h1-workflow-runs.json")


class WindowsH1MachineDispatchAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow_path = ROOT / WORKFLOW_PATH
        if not workflow_path.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.policy = json.loads(
            (ROOT / "governance/github_airlock_policy.json").read_text(encoding="utf-8")
        )
        cls.workflow = workflow_path.read_text(encoding="utf-8")
        cls.phoenix = (ROOT / PHOENIX_PATH).read_text(encoding="utf-8")

    def rules(self, text=None):
        return {
            row.rule
            for row in analyse_workflow(
                WORKFLOW_PATH,
                self.workflow if text is None else text,
                self.policy,
            )
        }

    def _selector_code(self):
        marker = "            if python3 - <<'PY' > /tmp/windows-h1-run-match.tsv\n"
        start = self.workflow.index(marker) + len(marker)
        end = self.workflow.index("\n          PY\n", start)
        return textwrap.dedent(self.workflow[start:end])

    def _run_selector(self, runs):
        RUNS_PATH.write_text(json.dumps({"workflow_runs": runs}), encoding="utf-8")
        env = os.environ.copy()
        env["DISPATCHED_AT"] = "2026-09-15T02:53:08Z"
        env["EXPECTED_CONTROL_SHA"] = "a" * 40
        try:
            return subprocess.run(
                [sys.executable, "-c", self._selector_code()],
                text=True,
                capture_output=True,
                env=env,
                timeout=10,
            )
        finally:
            RUNS_PATH.unlink(missing_ok=True)

    def test_adapter_is_distinct_dispatch_only_actions_writer(self):
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, self.policy["actions_dispatch_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["actions_write_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["provider_mutation_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertEqual(self.rules(), set())

    def test_adapter_is_owner_gated_and_target_is_hard_coded(self):
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.workflow)
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_SCSF_RENDEZVOUS_PROVIDER_V1", self.workflow)
        self.assertIn(f"TARGET_WORKFLOW: {TARGET_WORKFLOW}", self.workflow)
        self.assertIn("/actions/workflows/${TARGET_WORKFLOW}/dispatches", self.workflow)
        self.assertIn("EXPECTED_PACKET_ID: PKT-V5-WINDOWS-SCSF-RENDEZVOUS-PROVIDER-001", self.workflow)
        self.assertIn("EXPECTED_SOURCE_SHA: f22a627a841dd7297a137a56eb29d2b5de9acf9c", self.workflow)
        self.assertNotIn("workflow_dispatch:", self.workflow)

    def test_adapter_has_no_provider_identity_or_provider_mutation_power(self):
        self.assertIn("actions: write", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("issues: read", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)
        self.assertNotIn("gcloud ", self.workflow)
        self.assertNotIn("google-github-actions/auth", self.workflow)
        self.assertNotIn("--allow-unauthenticated", self.workflow)
        self.assertNotIn("run deploy", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_adapter_preserves_exact_passport_contract(self):
        required = (
            "FUSE-SURFACE-CAPABILITY-PASSPORT-V1",
            "FUSE_WINDOWS_H1_PROVIDER_RELAY_V2",
            "A2_REVERSIBLE_ISOLATED_CANARY",
            "provider_effect_authorized",
            "rollback_required",
            "public_ingress",
            "iam_mutation",
            "customer_traffic",
            "gcp_heavy_compute",
            "max_cpu",
            "max_memory_mib",
            "max_instances",
            "PASSPORT_FIELDS_NOT_EXACT",
            "PASSPORT_FIELD_MISMATCH",
            "PASSPORT_TIME_WINDOW_INVALID",
            "PROVIDER_PASSPORT_JSON_B64",
            "PROVIDER_PASSPORT_SHA256",
        )
        for marker in required:
            self.assertIn(marker, self.workflow)

    def test_run_attribution_uses_deterministic_json_parsing_and_fails_on_ambiguity(self):
        required = (
            "/tmp/windows-h1-workflow-runs.json",
            "json.load(handle)",
            "created >= os.environ['DISPATCHED_AT']",
            "head_sha == os.environ['EXPECTED_CONTROL_SHA']",
            "event == 'workflow_dispatch'",
            "RUN_IDENTITY_AMBIGUOUS",
            "len(candidates) != 1",
            "TARGET_RUN_CREATED_AT",
            "EXACT_CREATED_AT_PLUS_CONTROL_SHA_UNIQUE_MATCH",
            "FUSE-WINDOWS-SCSF-MACHINE-DISPATCH-RECEIPT-V2",
        )
        for marker in required:
            self.assertIn(marker, self.workflow)
        self.assertNotIn("--jq --arg since", self.workflow)
        self.assertNotIn("| head -n 1", self.workflow)

    def test_embedded_selector_returns_only_exact_post_dispatch_control_match(self):
        result = self._run_selector([
            {"id": 41, "created_at": "2026-09-15T02:53:07Z", "head_sha": "a" * 40, "event": "workflow_dispatch"},
            {"id": 42, "created_at": "2026-09-15T02:53:08Z", "head_sha": "a" * 40, "event": "workflow_dispatch"},
            {"id": 43, "created_at": "2026-09-15T02:53:09Z", "head_sha": "b" * 40, "event": "workflow_dispatch"},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "42\t" + "a" * 40 + "\t2026-09-15T02:53:08Z")

    def test_embedded_selector_rejects_ambiguous_exact_matches(self):
        result = self._run_selector([
            {"id": 42, "created_at": "2026-09-15T02:53:08Z", "head_sha": "a" * 40, "event": "workflow_dispatch"},
            {"id": 44, "created_at": "2026-09-15T02:53:09Z", "head_sha": "a" * 40, "event": "workflow_dispatch"},
        ])
        self.assertEqual(result.returncode, 4)
        self.assertIn("RUN_IDENTITY_AMBIGUOUS:42,44", result.stderr)

    def test_adapter_cannot_alias_provider_gateway(self):
        self.assertIn("provider_effect_performed_by_adapter': False", self.workflow)
        self.assertIn("provider_credentials_accessed_by_adapter': False", self.workflow)
        self.assertIn("owner_pc_effect_performed_by_adapter': False", self.workflow)
        self.assertNotIn("/enable", self.workflow)
        self.assertNotIn("/disable", self.workflow)

    def test_enable_or_disable_endpoint_is_rejected(self):
        enable = self.workflow.replace(
            "/actions/workflows/${TARGET_WORKFLOW}/dispatches",
            "/actions/workflows/${TARGET_WORKFLOW}/enable",
        )
        disable = self.workflow.replace(
            "/actions/workflows/${TARGET_WORKFLOW}/dispatches",
            "/actions/workflows/${TARGET_WORKFLOW}/disable",
        )
        self.assertIn("ACTIONS_DISPATCH_ENDPOINT_DRIFT", self.rules(enable))
        self.assertIn("ACTIONS_DISPATCH_FORBIDDEN_BEHAVIOR", self.rules(enable))
        self.assertIn("ACTIONS_DISPATCH_ENDPOINT_DRIFT", self.rules(disable))
        self.assertIn("ACTIONS_DISPATCH_FORBIDDEN_BEHAVIOR", self.rules(disable))

    def test_owner_gate_removal_is_rejected(self):
        altered = self.workflow.replace(
            " && github.event.issue.author_association == 'OWNER'",
            "",
        )
        self.assertIn("ACTIONS_DISPATCH_TRIGGER_DRIFT", self.rules(altered))
        self.assertIn("ACTIONS_DISPATCH_REQUIRED_GUARD_MISSING", self.rules(altered))

    def test_target_workflow_drift_is_rejected(self):
        altered = self.workflow.replace(
            f"TARGET_WORKFLOW: {TARGET_WORKFLOW}",
            "TARGET_WORKFLOW: arbitrary-provider.yml",
        )
        self.assertIn("ACTIONS_DISPATCH_REQUIRED_GUARD_MISSING", self.rules(altered))

    def test_oidc_or_provider_power_is_rejected(self):
        oidc = self.workflow.replace("actions: write", "actions: write\n  id-token: write")
        provider = self.workflow + "\n# gcloud run deploy\n"
        self.assertIn("ACTIONS_DISPATCH_WRITER_OIDC_AUTHORITY", self.rules(oidc))
        self.assertIn("UNAUTHORISED_OIDC", self.rules(oidc))
        self.assertIn("ACTIONS_DISPATCH_WRITER_PROVIDER_AUTHORITY", self.rules(provider))
        self.assertIn("UNAUTHORISED_PROVIDER_MUTATION", self.rules(provider))

    def test_quarantine_controller_semantics_remain_distinct(self):
        rules = {
            row.rule
            for row in analyse_workflow(PHOENIX_PATH, self.phoenix, self.policy)
        }
        self.assertNotIn("ACTIONS_DISPATCH_ENDPOINT_DRIFT", rules)
        self.assertNotIn("ACTIONS_DISPATCH_TRIGGER_DRIFT", rules)
        self.assertIn(PHOENIX_PATH, self.policy["actions_write_workflow_allowlist"])
        self.assertNotIn(PHOENIX_PATH, self.policy["actions_dispatch_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
