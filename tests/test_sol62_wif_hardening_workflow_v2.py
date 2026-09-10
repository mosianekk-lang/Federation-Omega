from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-wif-hardening-lease.yml"
HARDENER = ROOT / "ops" / "harden_sovara_provider_wif_v1.sh"


class Sol62WifHardeningWorkflowV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else None
        cls.hardener = HARDENER.read_text(encoding="utf-8")

    def require_workflow(self) -> str:
        if self.workflow is None:
            self.skipTest("workflow-free export excludes repository workflow controls")
        return self.workflow

    def test_exact_owner_reopen_and_oidc_gate_remain(self) -> None:
        workflow = self.require_workflow()
        for fragment in (
            "types: [reopened]",
            "github.event.issue.author_association == 'OWNER'",
            "github.event.issue.title == 'SOL62-WIF-HARDEN-20260901'",
            "id-token: write",
            "persist-credentials: false",
            "workload_identity_provider: ${{ env.WIF_PROVIDER }}",
            "service_account: ${{ env.DEPLOYER_SA }}",
        ):
            self.assertIn(fragment, workflow)

    def test_execution_is_bound_to_exact_issue_event_source_sha(self) -> None:
        workflow = self.require_workflow()
        self.assertIn("SOURCE_SHA: ${{ github.sha }}", workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$SOURCE_SHA"', workflow)
        self.assertNotIn("ref: main", workflow)

    def test_private_prestate_captures_only_mutated_provider_and_iam_surfaces(self) -> None:
        workflow = self.require_workflow()
        for fragment in (
            "/tmp/sol62-wif-private/provider-before.json",
            "/tmp/sol62-wif-private/iam-before.json",
            "attributeCondition",
            "attributeMapping",
            "issuerUri",
            "roles/iam.workloadIdentityUser",
            "exact_binding_present",
            "broad_binding_present",
            "PROVIDER_PRESTATE_NOT_ACTIVE",
            "PROVIDER_PRESTATE_MAPPING_UNREADABLE",
        ):
            self.assertIn(fragment, workflow)

    def test_plan_prevents_false_noop_mutation_claim(self) -> None:
        workflow = self.require_workflow()
        plan = workflow.index("bash ./ops/harden_sovara_provider_wif_v1.sh --plan")
        gate = workflow.index('if [[ "$PLAN_STATE" == "ALREADY_HARDENED" ]]')
        apply = workflow.index("bash ./ops/harden_sovara_provider_wif_v1.sh --apply")
        self.assertLess(plan, gate)
        self.assertLess(gate, apply)
        self.assertIn('cp "$PUBLIC/WIF_HARDEN_PLAN.json" "$PUBLIC/WIF_HARDEN_APPLY.json"', workflow)
        self.assertIn("assert apply.get('mode') == 'plan'", workflow)
        self.assertIn("assert apply.get('mutation_performed') is False", workflow)

    def test_rollback_is_armed_before_mutating_apply_and_restores_exact_prestate(self) -> None:
        workflow = self.require_workflow()
        armed = workflow.index("ROLLBACK_NEEDED=true")
        apply = workflow.index("bash ./ops/harden_sovara_provider_wif_v1.sh --apply")
        disarmed = workflow.index("ROLLBACK_NEEDED=false", armed + 1)
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
            self.assertIn(fragment, workflow)

    def test_post_apply_contract_requires_v3_event_surface_and_exact_principals(self) -> None:
        workflow = self.require_workflow()
        self.assertIn("SOVARA_WIF_HARDENING_V3", workflow)
        self.assertNotIn("SOVARA_WIF_HARDENING_V1', apply", workflow)
        self.assertIn("event_surface_bound_per_workflow", workflow)
        self.assertIn("trust_contract_sha256", workflow)
        self.assertIn("exact_repository_id_binding_present", workflow)
        self.assertIn("broad_repository_name_binding_present", workflow)
        self.assertIn("required_mutations", workflow)
        self.assertIn("'schema':'SOVARA_WIF_HARDENING_V3'", self.hardener)

    def test_failure_receipts_are_uploaded_without_private_raw_prestate(self) -> None:
        workflow = self.require_workflow()
        self.assertIn("if: always()", workflow)
        self.assertIn("raw_provider_persisted_in_artifact': False", workflow)
        self.assertIn("raw_iam_policy_persisted_in_artifact': False", workflow)
        self.assertIn("path: /tmp/sol62-wif\n", workflow)
        self.assertNotIn("path: /tmp/sol62-wif-private", workflow)
        self.assertNotIn("auth print-access-token", workflow)
        self.assertNotIn("credentials_file_path", workflow)

    def test_transaction_does_not_enable_apis_or_touch_application_runtime(self) -> None:
        workflow = self.require_workflow()
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
            self.assertNotIn(fragment, workflow)


if __name__ == "__main__":
    unittest.main()
