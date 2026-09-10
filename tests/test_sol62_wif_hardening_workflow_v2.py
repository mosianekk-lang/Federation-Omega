from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-wif-hardening-lease.yml"
HARDENER = ROOT / "ops" / "harden_sovara_provider_wif_v1.sh"


class Sol62WifHardeningWorkflowV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.hardener = HARDENER.read_text(encoding="utf-8")

    def test_exact_owner_issue_and_oidc_gate_remain(self) -> None:
        for fragment in (
            "github.event.issue.author_association == 'OWNER'",
            "github.event.issue.title == 'SOL62-WIF-HARDEN-20260901'",
            "id-token: write",
            "persist-credentials: false",
            "workload_identity_provider: ${{ env.WIF_PROVIDER }}",
            "service_account: ${{ env.DEPLOYER_SA }}",
        ):
            self.assertIn(fragment, self.workflow)

    def test_private_prestate_captures_only_mutated_provider_and_iam_surfaces(self) -> None:
        for fragment in (
            "/tmp/sol62-wif-private/provider-before.json",
            "/tmp/sol62-wif-private/iam-before.json",
            "attributeCondition",
            "attributeMapping",
            "issuerUri",
            "roles/iam.workloadIdentityUser",
            "exact_binding_present",
            "broad_binding_present",
        ):
            self.assertIn(fragment, self.workflow)
        self.assertIn("PROVIDER_PRESTATE_NOT_ACTIVE", self.workflow)
        self.assertIn("PROVIDER_PRESTATE_MAPPING_UNREADABLE", self.workflow)

    def test_rollback_is_armed_before_apply_and_restores_affected_prestate(self) -> None:
        armed = self.workflow.index("ROLLBACK_NEEDED=true")
        apply = self.workflow.index("./ops/harden_sovara_provider_wif_v1.sh --apply")
        disarmed = self.workflow.index("ROLLBACK_NEEDED=false", armed + 1)
        self.assertLess(armed, apply)
        self.assertLess(apply, disarmed)
        for fragment in (
            "rollback_to_prestate()",
            "trap on_error ERR",
            "add-iam-policy-binding",
            "remove-iam-policy-binding",
            "workload-identity-pools','providers','update-oidc",
            "ROLLBACK_EQUIVALENT",
            "ROLLBACK_EQUIVALENCE_FAILED",
            "condition_restored",
            "mapping_restored",
            "exact_binding_restored",
            "broad_binding_restored",
            "exit 97",
        ):
            self.assertIn(fragment, self.workflow)

    def test_post_apply_contract_requires_v3_and_truthful_noop(self) -> None:
        self.assertIn("SOVARA_WIF_HARDENING_V3", self.workflow)
        self.assertNotIn("SOVARA_WIF_HARDENING_V1', apply", self.workflow)
        self.assertIn("{'APPLIED_AND_VERIFIED','ALREADY_HARDENED'}", self.workflow)
        self.assertIn("assert apply.get('mutation_performed') is False", self.workflow)
        self.assertIn("assert apply.get('mutation_performed') is True", self.workflow)
        self.assertIn("event_surface_bound_per_workflow", self.workflow)
        self.assertIn("required_mutations", self.workflow)
        self.assertIn('emit_receipt "ALREADY_HARDENED" false', self.hardener)

    def test_artifact_is_sanitized_and_excludes_private_raw_prestate(self) -> None:
        self.assertIn("raw_provider_persisted_in_artifact': False", self.workflow)
        self.assertIn("raw_iam_policy_persisted_in_artifact': False", self.workflow)
        self.assertIn("path: /tmp/sol62-wif\n", self.workflow)
        self.assertNotIn("path: /tmp/sol62-wif-private", self.workflow)
        self.assertNotIn("auth print-access-token", self.workflow)
        self.assertNotIn("credentials_file_path", self.workflow)

    def test_source_transaction_does_not_enable_apis_or_touch_application_runtime(self) -> None:
        forbidden = (
            "gcloud services enable",
            "gcloud projects add-iam-policy-binding",
            "gcloud run deploy",
            "gcloud run services",
            "gcloud secrets",
            "secretmanager",
            "generateContent",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.workflow)


if __name__ == "__main__":
    unittest.main()
