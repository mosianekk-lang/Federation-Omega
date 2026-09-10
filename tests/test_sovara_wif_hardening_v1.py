from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "harden_sovara_provider_wif_v1.sh"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
REPOSITORY_SLUG = "mosianekk-lang/Federation-Omega"
MAIN_REF = "refs/heads/main"
EXPECTED_COUNT = 18
EXPECTED_SET_SHA256 = "65e4cc0a148c4a0d7f0fa646692f369becc7d47db7aa68591371fa593de1c07c"


class SovaraWifHardeningV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.paths = cls.policy["oidc_workflow_allowlist"]
        cls.refs = [f"{REPOSITORY_SLUG}/{path}@{MAIN_REF}" for path in cls.paths]

    def test_expected_contract_uses_standard_workflow_ref_and_main_ref(self) -> None:
        for fragment in (
            "assertion.repository_id=='${REPOSITORY_ID}'",
            "assertion.repository_owner_id=='${OWNER_ID}'",
            "assertion.ref=='${MAIN_REF}'",
            "assertion.workflow_ref in ${WORKFLOW_REF_LIST_CEL}",
            "attribute.repository_id=assertion.repository_id",
            "attribute.repository_owner_id=assertion.repository_owner_id",
            "attribute.workflow_ref=assertion.workflow_ref",
        ):
            self.assertIn(fragment, self.source)
        self.assertNotIn("assertion.job_workflow_ref", self.source)
        self.assertNotIn("attribute.workflow_ref=assertion.job_workflow_ref", self.source)

    def test_airlock_oidc_workflow_set_is_pinned_and_fail_closed(self) -> None:
        self.assertEqual(EXPECTED_COUNT, len(self.paths))
        self.assertEqual(len(self.paths), len(set(self.paths)))
        for path in self.paths:
            self.assertRegex(path, r"^\.github/workflows/[A-Za-z0-9._/-]+\.(?:yml|yaml)$")
        digest = hashlib.sha256(("\n".join(sorted(self.refs)) + "\n").encode()).hexdigest()
        self.assertEqual(EXPECTED_SET_SHA256, digest)
        self.assertIn(f'EXPECTED_OIDC_WORKFLOW_COUNT={EXPECTED_COUNT}', self.source)
        self.assertIn(f'EXPECTED_OIDC_WORKFLOW_SET_SHA256="{EXPECTED_SET_SHA256}"', self.source)
        self.assertIn("Airlock OIDC workflow set drifted; refusing silent WIF trust expansion/contraction.", self.source)
        self.assertIn("policy.get('oidc_workflow_allowlist')", self.source)

    def test_generated_condition_fits_google_provider_limit(self) -> None:
        workflow_list = "[" + ",".join(repr(value) for value in self.refs) + "]"
        condition = (
            "assertion.repository_id=='1292795464' && "
            "assertion.repository_owner_id=='261966700' && "
            "assertion.ref=='refs/heads/main' && "
            f"assertion.workflow_ref in {workflow_list}"
        )
        self.assertLessEqual(len(condition), 4096)
        self.assertIn("if ((${#EXPECTED_CONDITION} > 4096)); then", self.source)

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
        self.assertIn("'schema':'SOVARA_WIF_HARDENING_V2'", self.source)
        self.assertIn("'workflow_claim':'workflow_ref'", self.source)
        self.assertIn("'authorized_workflow_set_sha256':'${AUTHORIZED_WORKFLOW_SET_SHA}'", self.source)
        self.assertIn("'mutation_performed':'${mutation}' == 'true'", self.source)
        self.assertIn("'project_role_binding_performed':False", self.source)
        self.assertIn("'model_inference_performed':False", self.source)
        self.assertIn("'traffic_change_performed':False", self.source)


if __name__ == "__main__":
    unittest.main()
