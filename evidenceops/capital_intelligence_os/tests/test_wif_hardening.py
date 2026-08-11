import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "bootstrap_github_wif.sh"
ACTIVATE = ROOT / "ops" / "activate_wif_and_deploy.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-cloud-run.yml"


class WIFHardeningTests(unittest.TestCase):
    def make_fake_gcloud(self, directory: Path) -> tuple[Path, Path]:
        log_path = directory / "gcloud.log"
        fake = directory / "gcloud"
        fake.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -eu
                printf '%s\\n' "$*" >> "${FEDOMEGA_GCLOUD_LOG}"
                case "$*" in
                  "auth list"*) echo "owner@example.com" ;;
                  "config get-value project"*) echo "sov-hybrid-suite" ;;
                  "projects describe sov-hybrid-suite"*) echo "257649435135" ;;
                  "iam service-accounts describe"*) exit 0 ;;
                  "run services describe"*) exit 0 ;;
                  "artifacts repositories describe"*) exit 0 ;;
                  "iam workload-identity-pools describe"*) exit 1 ;;
                  "iam workload-identity-pools providers describe"*) exit 1 ;;
                  "services list"*) exit 0 ;;
                  *) exit 0 ;;
                esac
                """
            ),
            encoding="utf-8",
        )
        fake.chmod(0o755)
        return fake, log_path

    def run_bootstrap(self, mode: str, approval: str | None = None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            _, log_path = self.make_fake_gcloud(tmp)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}:{env['PATH']}"
            env["FEDOMEGA_GCLOUD_LOG"] = str(log_path)
            if approval is not None:
                env["FEDOMEGA_WIF_APPLY_APPROVAL"] = approval
            result = subprocess.run(
                ["bash", str(BOOTSTRAP), mode],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            result.gcloud_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""  # type: ignore[attr-defined]
            return result

    def assert_no_mutation_commands(self, log: str) -> None:
        forbidden = (
            "services enable",
            "config set",
            "workload-identity-pools create",
            "providers create-oidc",
            "providers update-oidc",
            "add-iam-policy-binding",
            "run deploy",
            "builds submit",
        )
        for item in forbidden:
            self.assertNotIn(item, log, item)

    def test_plan_is_default_read_only_and_structured(self):
        result = self.run_bootstrap("--plan")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual("FEDOMEGA-WIF-PLAN", payload["receipt"])
        self.assertEqual("PLAN_REQUIRES_CHANGES", payload["state"])
        self.assertFalse(payload["mutation_performed"])
        self.assertIn("wif_provider_active", payload["missing_controls"])
        self.assert_no_mutation_commands(result.gcloud_log)  # type: ignore[attr-defined]

    def test_apply_fails_before_mutation_without_exact_approval(self):
        result = self.run_bootstrap("--apply")
        self.assertEqual(3, result.returncode, result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual("FEDOMEGA-WIF-APPLY-BLOCKED", payload["receipt"])
        self.assertEqual("APPROVAL_REQUIRED", payload["state"])
        self.assertFalse(payload["mutation_performed"])
        self.assert_no_mutation_commands(result.gcloud_log)  # type: ignore[attr-defined]

    def test_workflow_is_manual_zero_traffic_and_rollback_capable(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("branches: [main]", workflow)
        self.assertIn("google-github-actions/auth@v3", workflow)
        self.assertIn("FEDOMEGA-WIF-CLOUD-VERIFIED", workflow)
        self.assertIn("DEPLOY_SLRK_V3_2_TO_ARCHITRON9", workflow)
        self.assertIn("--no-traffic", workflow)
        self.assertIn("--tag \"$CANARY_TAG\"", workflow)
        self.assertIn("previous_ready_revision", workflow)
        self.assertIn("update-traffic", workflow)
        self.assertIn("version') == '3.2.0'", workflow)
        self.assertIn("ALG-ECASP-001", workflow)

    def test_compatibility_wrapper_has_no_direct_deploy_path(self):
        script = ACTIVATE.read_text(encoding="utf-8")
        self.assertNotIn("gcloud run deploy", script)
        self.assertNotIn("gcloud builds submit", script)
        self.assertIn("--apply-wif", script)
        self.assertIn("manual canary workflow", script)

    def test_bootstrap_uses_repository_and_branch_restriction(self):
        script = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("assertion.repository=='${GITHUB_REPOSITORY}'", script)
        self.assertIn("assertion.ref=='refs/heads/main'", script)
        self.assertIn("roles/artifactregistry.writer", script)
        self.assertIn("roles/run.developer", script)
        self.assertIn("roles/run.invoker", script)
        self.assertIn("roles/iam.serviceAccountUser", script)
        self.assertIn("roles/iam.workloadIdentityUser", script)
        self.assertIn("TARGET_RESOURCE_MISSING", script)


if __name__ == "__main__":
    unittest.main()
