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

    def test_failed_apply_classifies_effect_before_any_mutating_rollback(self) -> None:
        workflow = self.require_workflow()
        handler = workflow.split("handle_failure() {", 1)[1].split(
            'test "${{ github.event.issue.title }}"', 1
        )[0]
        self.assertIn("readback_effect_state", handler)
        self.assertIn("effect_status=$?", handler)
        self.assertIn('if [[ $effect_status -eq 0 ]]', handler)
        self.assertIn('if [[ $effect_status -eq 10 ]]', handler)
        self.assertIn('if [[ "$effect_window" == "NO_EFFECT" ]]', handler)
        self.assertIn("rollback_to_prestate", handler)
        self.assertLess(handler.index("readback_effect_state"), handler.index("rollback_to_prestate"))
        no_effect_branch = handler.split('if [[ $effect_status -eq 0 ]]', 1)[1].split(
            'if [[ $effect_status -eq 10 ]]', 1
        )[0]
        self.assertNotIn("rollback_to_prestate", no_effect_branch)
        external_drift_branch = handler.split('if [[ "$effect_window" == "NO_EFFECT" ]]', 1)[1].split("fi", 1)[0]
        self.assertNotIn("rollback_to_prestate", external_drift_branch)
        uncertain_branch = handler.split('echo "WIF effect state uncertain', 1)[1].split("exit 98", 1)[0]
        self.assertNotIn("rollback_to_prestate", uncertain_branch)

    def test_readback_classifier_is_provider_read_only(self) -> None:
        workflow = self.require_workflow()
        classifier = workflow.split("readback_effect_state() {", 1)[1].split(
            "rollback_to_prestate() {", 1
        )[0]
        self.assertIn("providers','describe'", classifier)
        self.assertIn("service-accounts','get-iam-policy'", classifier)
        self.assertIn("PRESTATE_EQUIVALENT_NO_ROLLBACK", classifier)
        self.assertIn("PROVIDER_EFFECT_DETECTED", classifier)
        self.assertIn("EFFECT_STATE_UNCERTAIN", classifier)
        for mutator in (
            "add-iam-policy-binding",
            "remove-iam-policy-binding",
            "providers','update-oidc'",
            "gcloud services enable",
        ):
            self.assertNotIn(mutator, classifier)

    def test_mutation_ack_is_armed_only_after_successful_apply_return(self) -> None:
        workflow = self.require_workflow()
        apply = workflow.index("bash ./ops/harden_sovara_provider_wif_v1.sh --apply")
        failure_gate = workflow.index("if [[ $apply_status -ne 0 ]]", apply)
        acknowledged = workflow.index("MUTATION_ACKNOWLEDGED=true", apply)
        self.assertLess(apply, failure_gate)
        self.assertLess(failure_gate, acknowledged)
        self.assertIn('handle_failure "$apply_status" "AMBIGUOUS_APPLY"', workflow)
        self.assertIn("trap 'handle_failure \"$?\" \"ACKED_APPLY\"' ERR", workflow)
        self.assertIn("trap 'handle_failure \"$?\" \"NO_EFFECT\"' ERR", workflow)
        self.assertNotIn("ROLLBACK_NEEDED=true", workflow)

    def test_rollback_restores_exact_prestate_after_detected_effect(self) -> None:
        workflow = self.require_workflow()
        for fragment in (
            "rollback_to_prestate()",
            "add-iam-policy-binding",
            "remove-iam-policy-binding",
            "workload-identity-pools','providers','update-oidc",
            "ROLLBACK_EQUIVALENT",
            "ROLLBACK_EQUIVALENCE_FAILED",
            "condition_restored",
            "mapping_restored",
            "exact_binding_restored",
            "broad_binding_restored",
            "effect_classification': 'PROVIDER_EFFECT_DETECTED'",
            "rollback_invoked': True",
            "exit 97",
        ):
            self.assertIn(fragment, workflow)

    def test_post_apply_contract_requires_v3_event_surface_and_effective_least_privilege(self) -> None:
        workflow = self.require_workflow()
        self.assertIn("SOVARA_WIF_HARDENING_V3", workflow)
        self.assertNotIn("SOVARA_WIF_HARDENING_V1', apply", workflow)
        for fragment in (
            "event_surface_bound_per_workflow",
            "trust_contract_sha256",
            "exact_repository_id_binding_present",
            "broad_repository_name_binding_present",
            "broad_repository_attribute_mapped",
            "broad_repository_name_binding_effective",
            "legacy_broad_repository_name_binding_inert",
            "physical_legacy_binding_removal_required",
            "required_mutations",
        ):
            self.assertIn(fragment, workflow)
        self.assertIn("assert verify.get('broad_repository_attribute_mapped') is False", workflow)
        self.assertIn("assert verify.get('broad_repository_name_binding_effective') is False", workflow)
        self.assertIn("assert verify.get('legacy_broad_repository_name_binding_inert') is True", workflow)
        self.assertNotIn("assert verify.get('broad_repository_name_binding_present') is False", workflow)
        self.assertIn("'schema':'SOVARA_WIF_HARDENING_V3'", self.hardener)

    def test_changed_route_does_not_replay_known_denied_physical_removal(self) -> None:
        workflow = self.require_workflow()
        apply_section = self.hardener.split("# Establish the exact repository-ID binding", 1)[1]
        self.assertNotIn("remove-iam-policy-binding", apply_section)
        self.assertIn("RENDER_BROAD_REPOSITORY_NAME_BINDING_INERT", self.hardener)
        self.assertIn("BROAD_BINDING_EFFECTIVE", self.hardener)
        self.assertIn("BROAD_REPOSITORY_ATTRIBUTE_MAPPED", self.hardener)
        self.assertIn("readback_effect_state", workflow)

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
