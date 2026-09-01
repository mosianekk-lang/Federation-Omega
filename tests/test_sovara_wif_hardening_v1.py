from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "harden_sovara_provider_wif_v1.sh"


class SovaraWifHardeningV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_expected_contract_is_the_hardened_canonical_workflow_contract(self) -> None:
        for fragment in (
            "assertion.repository_id=='${REPOSITORY_ID}'",
            "assertion.repository_owner_id=='${OWNER_ID}'",
            "assertion.ref=='refs/heads/main'",
            "assertion.job_workflow_ref=='${CANONICAL_WORKFLOW}'",
            "(assertion.event_name=='workflow_dispatch' || assertion.event_name=='push')",
            "attribute.repository_id=assertion.repository_id",
            "attribute.repository_owner_id=assertion.repository_owner_id",
            "attribute.workflow_ref=assertion.job_workflow_ref",
        ):
            self.assertIn(fragment, self.source)

    def test_exact_repository_id_binding_replaces_broad_repository_name_binding(self) -> None:
        self.assertIn("attribute.repository_id/${REPOSITORY_ID}", self.source)
        self.assertIn("attribute.repository/mosianekk-lang/Federation-Omega", self.source)
        self.assertIn("ADD_EXACT_REPOSITORY_ID_WIF_BINDING", self.source)
        self.assertIn("REMOVE_BROAD_REPOSITORY_NAME_WIF_BINDING", self.source)
        self.assertIn("service-accounts add-iam-policy-binding", self.source)
        self.assertIn("service-accounts remove-iam-policy-binding", self.source)

    def test_apply_requires_explicit_narrow_confirmation(self) -> None:
        self.assertIn('APPLY_CONFIRMATION="HARDEN_SOVARA_CANONICAL_WIF_V1"', self.source)
        self.assertIn("SOVARA_WIF_HARDENING_APPROVAL", self.source)
        self.assertIn("Refusing mutation without", self.source)

    def test_source_cannot_expand_provider_or_application_authority(self) -> None:
        forbidden = (
            "gcloud services enable",
            "gcloud projects add-iam-policy-binding",
            "gcloud run services add-iam-policy-binding",
            "gcloud run deploy",
            "gcloud artifacts repositories add-iam-policy-binding",
            "gcloud iam service-accounts create",
            "secretmanager",
            "curl ",
            "docker ",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.source)

    def test_safe_ordering_establishes_exact_binding_then_hardens_then_removes_broad(self) -> None:
        add_exact = self.source.index('if [[ "$EXACT_BINDING" != true ]]')
        update_provider = self.source.index('if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true ]]')
        remove_broad = self.source.index('if [[ "$BROAD_BINDING" == true ]]')
        self.assertLess(add_exact, update_provider)
        self.assertLess(update_provider, remove_broad)

    def test_verify_is_fail_closed_and_receipt_separates_mutation(self) -> None:
        self.assertIn('emit_receipt "NOT_VERIFIED" false; exit 1', self.source)
        self.assertIn("'mutation_performed':'${mutation}' == 'true'", self.source)
        self.assertIn("'project_role_binding_performed':False", self.source)
        self.assertIn("'model_inference_performed':False", self.source)
        self.assertIn("'traffic_change_performed':False", self.source)


if __name__ == "__main__":
    unittest.main()
