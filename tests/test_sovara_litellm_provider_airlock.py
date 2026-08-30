from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "github_airlock_sovara", ROOT / "tools" / "github_airlock.py"
)
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)
POLICY = AIRLOCK.load_policy(ROOT / "governance" / "github_airlock_policy.json")
WORKFLOW_PATH = ".github/workflows/sovara-litellm-v2-3-provider-admission.yml"
WORKFLOW = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")


class SovaraLiteLLMProviderAirlockTests(unittest.TestCase):
    def rules(self, findings):
        return {finding.rule for finding in findings}

    def contract(self, permissions: str = "  contents: read\n  id-token: write\n") -> str:
        return f"""name: SOVARA LiteLLM v2.3 Provider Admission
on:
  push:
    branches: [\"main\"]
  workflow_dispatch:
permissions:
{permissions}concurrency:
  group: sovara-litellm-v2-3-provider-admission-${{{{ github.ref }}}}
  cancel-in-progress: false
jobs:
  provider:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - uses: google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093
      - uses: google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
"""

    def test_exact_oidc_artifact_only_contract_passes(self):
        findings = AIRLOCK.analyse_workflow(WORKFLOW_PATH, self.contract(), POLICY)
        self.assertEqual([], findings)

    def test_gateway_is_explicitly_admitted_for_oidc(self):
        self.assertIn(WORKFLOW_PATH, set(POLICY["oidc_workflow_allowlist"]))
        self.assertIn(WORKFLOW_PATH, POLICY["active_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, POLICY["execution_quarantine"]["keep_active"])
        self.assertIn(
            ".github/workflows/cios-production-lane.yml",
            set(POLICY["oidc_workflow_allowlist"]),
        )

    def test_provider_execution_is_dispatch_or_explicit_request_only(self):
        self.assertIn("id: provider_mode", WORKFLOW)
        self.assertIn('if [[ "${GITHUB_EVENT_NAME}" == "workflow_dispatch" ]]; then', WORKFLOW)
        self.assertIn('scope=SOURCE_VALIDATION_ONLY', WORKFLOW)
        self.assertIn('scope=FULL_PROVIDER_ADMISSION', WORKFLOW)
        self.assertIn('if grep -Fxq "${GEMINI_REQUEST_FILE}" <<<"${changed}"; then', WORKFLOW)
        self.assertGreaterEqual(
            WORKFLOW.count("if: steps.provider_mode.outputs.requested == 'true'"),
            3,
        )
        self.assertIn("Authenticate through exact repository-scoped Google WIF", WORKFLOW)
        self.assertIn("Execute provider admission, canaries, deployment, and rollback gates", WORKFLOW)

    def test_push_path_is_truthful_source_validation_only(self):
        self.assertIn("'execution_scope':scope", WORKFLOW)
        self.assertIn("'provider_admission_attempted':scope=='FULL_PROVIDER_ADMISSION'", WORKFLOW)
        self.assertIn("'provider_admission_completed':scope=='FULL_PROVIDER_ADMISSION' and code==0", WORKFLOW)
        self.assertIn("'provider_state_claimed':scope=='FULL_PROVIDER_ADMISSION' and code==0", WORKFLOW)
        self.assertIn('.execution_scope == "SOURCE_VALIDATION_ONLY"', WORKFLOW)
        self.assertIn('.provider_admission_attempted == false', WORKFLOW)
        self.assertIn('.provider_state_claimed == false', WORKFLOW)
        self.assertIn("no WIF exchange was attempted", WORKFLOW)

    def test_mode_specific_requests_do_not_become_full_provider_admission(self):
        for scope in (
            "G0_READ_ONLY_VERIFY",
            "G1_ADC_APPLY_VERIFY",
            "G2_CREATIVE_ARCHITECTURE_CHALLENGE",
            "G3_PRIVATE_GATEWAY_CANARY",
        ):
            with self.subTest(scope=scope):
                self.assertIn(scope, WORKFLOW)
        self.assertIn("scope=='FULL_PROVIDER_ADMISSION'", WORKFLOW)
        self.assertIn(".provider_admission_attempted == false", WORKFLOW)

    def test_gateway_cannot_gain_source_write(self):
        findings = AIRLOCK.analyse_workflow(
            WORKFLOW_PATH,
            self.contract("  contents: write\n  id-token: write\n"),
            POLICY,
        )
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", self.rules(findings))

    def test_unlisted_oidc_workflow_still_fails_closed(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/unlisted-provider.yml",
            self.contract(),
            POLICY,
        )
        rules = self.rules(findings)
        self.assertIn("WORKFLOW_NOT_ALLOWLISTED", rules)
        self.assertIn("UNAUTHORISED_OIDC", rules)

    def test_gateway_push_scope_is_exactly_main(self):
        drifted = self.contract().replace(
            'branches: ["main"]', 'branches: ["main", "develop"]'
        )
        findings = AIRLOCK.analyse_workflow(WORKFLOW_PATH, drifted, POLICY)
        self.assertIn("UNAUTHORISED_PUSH_SCOPE", self.rules(findings))

    def test_gateway_uses_only_immutable_action_refs(self):
        drifted = self.contract().replace(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            "actions/upload-artifact@v4",
        )
        findings = AIRLOCK.analyse_workflow(WORKFLOW_PATH, drifted, POLICY)
        self.assertIn("MUTABLE_ACTION_REFERENCE", self.rules(findings))


if __name__ == "__main__":
    unittest.main()
