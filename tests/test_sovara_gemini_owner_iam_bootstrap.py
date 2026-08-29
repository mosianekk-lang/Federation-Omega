from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sovara" / "gemini" / "owner_iam_bootstrap.sh"


class SovaraGeminiOwnerIamBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_script_is_valid_bash(self) -> None:
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_exact_three_role_bindings_only(self) -> None:
        expected = {
            'roles/aiplatform.user',
            'roles/serviceusage.serviceUsageConsumer',
            'roles/run.developer',
        }
        for role in expected:
            self.assertIn(role, self.source)
        forbidden = (
            'roles/owner',
            'roles/resourcemanager.projectIamAdmin',
            'roles/iam.serviceAccountAdmin',
            'roles/editor',
        )
        for role in forbidden:
            self.assertNotIn(f'--role {role}', self.source)
            self.assertNotIn(f'--role "{role}"', self.source)

    def test_deployer_identity_is_refused_as_iam_admin(self) -> None:
        self.assertIn('Refusing to use the ordinary deployment identity for project-IAM administration', self.source)
        self.assertIn('resourcemanager.projects.setIamPolicy', self.source)

    def test_apply_requires_explicit_exact_confirmation(self) -> None:
        self.assertIn('SOVARA_OWNER_IAM_APPLY', self.source)
        self.assertIn('ATTACH_EXACT_GEMINI_ADC_BINDINGS_V1', self.source)

    def test_no_identity_or_wif_expansion_commands_exist(self) -> None:
        forbidden = (
            'service-accounts create',
            'keys create',
            'workload-identity-pools create',
            'workload-identity-pools providers create',
            'services enable',
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.source)

    def test_receipt_records_only_added_bindings_for_rollback(self) -> None:
        self.assertIn("'bindings_added':added", self.source)
        self.assertIn('remove-iam-policy-binding', self.source)
        self.assertIn('ROLLBACK_EXACT_GEMINI_ADC_BINDINGS_V1', self.source)
        self.assertIn("provider_readback_verified':True", self.source)

    def test_canonical_runtime_and_deployer_are_fixed(self) -> None:
        self.assertIn('superior-logic-runtime@${PROJECT_ID}.iam.gserviceaccount.com', self.source)
        self.assertIn('superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com', self.source)
        self.assertNotIn('sv-gemini-runtime', self.source)


if __name__ == '__main__':
    unittest.main()
