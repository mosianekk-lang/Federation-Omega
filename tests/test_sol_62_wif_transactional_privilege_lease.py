from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-wif-hardening-lease.yml"


class Sol62WifTransactionalPrivilegeLeaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_and_exact_issue_gate_remain_required(self) -> None:
        self.assertIn("types: [reopened]", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)
        self.assertIn("SOL62-WIF-HARDEN-20260901", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_project_iam_authority_is_tested_before_any_temporary_role(self) -> None:
        permission_index = self.text.index("resourcemanager.projects.setIamPolicy")
        add_index = self.text.index("projects add-iam-policy-binding")
        self.assertLess(permission_index, add_index)
        self.assertIn(":testIamPermissions", self.text)
        self.assertIn("AUTHORITY_BLOCKED_PRE_EFFECT", self.text)
        self.assertIn("provider_mutation_performed':False", self.text)

    def test_temporary_role_is_narrow_and_revoked(self) -> None:
        self.assertIn("roles/iam.workloadIdentityPoolAdmin", self.text)
        self.assertIn("gcloud projects add-iam-policy-binding", self.text)
        self.assertIn("gcloud projects remove-iam-policy-binding", self.text)
        self.assertIn("trap cleanup_temp_role EXIT", self.text)
        self.assertIn("temporary_wif_admin_role_revoked':True", self.text)
        self.assertIn("temp_role_remaining is False", self.text)
        self.assertNotIn("roles/owner", self.text)
        self.assertNotIn("roles/editor", self.text)

    def test_provider_hardening_stays_on_existing_admitted_script(self) -> None:
        self.assertIn("HARDEN_SOVARA_CANONICAL_WIF_V1", self.text)
        self.assertIn("./ops/harden_sovara_provider_wif_v1.sh --apply", self.text)
        self.assertIn("./ops/harden_sovara_provider_wif_v1.sh --verify", self.text)
        self.assertIn("exact_repository_id_binding_present", self.text)
        self.assertIn("broad_repository_name_binding_present", self.text)
        self.assertIn("condition_match", self.text)
        self.assertIn("mapping_match", self.text)

    def test_no_key_secret_model_or_traffic_authority_is_added(self) -> None:
        self.assertNotIn("service-accounts keys create", self.text)
        self.assertNotIn("secrets versions access", self.text)
        self.assertNotIn("generateContent", self.text)
        self.assertNotIn("run services update-traffic", self.text)
        self.assertIn("service_account_key_created':False", self.text)
        self.assertIn("model_inference_performed':False", self.text)
        self.assertIn("traffic_change_performed':False", self.text)

    def test_failure_receipts_are_uploaded_even_when_preflight_blocks(self) -> None:
        self.assertIn("if: ${{ always() }}", self.text)
        self.assertIn("SOL62_WIF_PRIVILEGE_PREFLIGHT.json", self.text)
        self.assertIn("SOL62_WIF_AUTHORITY_BLOCKED.json", self.text)


if __name__ == "__main__":
    unittest.main()
