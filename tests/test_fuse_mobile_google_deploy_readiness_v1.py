from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fo-wif-semantic-canary-v2.yml"


class FuseMobileGoogleDeployReadinessV1Tests(unittest.TestCase):
    def _text_or_skip_export(self) -> str:
        if not WORKFLOW.is_file():
            self.skipTest("GitHub workflow controls are outside the reduced Phoenix exported-core surface")
        return WORKFLOW.read_text()

    def test_readiness_probe_is_owner_only_keyless_and_zero_mutation(self) -> None:
        text = self._text_or_skip_export()
        self.assertIn("author_association == 'OWNER'", text)
        self.assertIn("id-token: write", text)
        self.assertIn("workload_identity_provider", text)
        self.assertIn("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com", text)
        self.assertIn("provider_mutation_performed':False", text)
        self.assertNotIn("gcloud projects add-iam-policy-binding", text)
        self.assertNotIn("gcloud artifacts repositories add-iam-policy-binding", text)
        self.assertNotIn("gcloud run services add-iam-policy-binding", text)

    def test_effective_authority_uses_project_or_resource_inheritance(self) -> None:
        text = self._text_or_skip_export()
        self.assertIn("project_run_developer", text)
        self.assertIn("project_artifact_registry_writer", text)
        self.assertIn("repository_artifact_registry_writer", text)
        self.assertIn("project_service_account_user", text)
        self.assertIn("runtime_service_account_user", text)
        self.assertIn("effective_ar_writer=project_ar_writer or repo_ar_writer", text)
        self.assertIn("effective_sa_user=project_sa_user or runtime_sa_user", text)
        self.assertIn("effective_invoke=project_run_developer or project_run_invoker", text)
        self.assertIn("conditional_bindings_not_promoted':True", text)

    def test_fuse_mobile_readiness_is_immutable_artifact_input(self) -> None:
        text = self._text_or_skip_export()
        self.assertIn("FUSE_MOBILE_GOOGLE_DEPLOYMENT_AUTHORITY_V1", text)
        self.assertIn("FUSE_MOBILE_DIRECT_DEPLOY_READY", text)
        self.assertIn("direct_runner_build_push_deploy_ready", text)
        self.assertIn("private_canary_invoke_ready", text)
        self.assertIn("g0-output/fuse-mobile-deploy-readiness.json", text)
        self.assertIn("fuse_mobile_deployment_authority", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)


if __name__ == "__main__":
    unittest.main()
