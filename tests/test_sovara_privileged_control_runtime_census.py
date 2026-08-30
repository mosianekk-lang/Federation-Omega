from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sovara" / "gemini" / "privileged_control_runtime_census.py"
ACTAS = ROOT / "sovara" / "gemini" / "admin_actas_census.py"
REQUEST = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"


class SovaraPrivilegedControlRuntimeCensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = SCRIPT.read_text(encoding="utf-8")
        self.actas = ACTAS.read_text(encoding="utf-8")
        self.request = json.loads(REQUEST.read_text(encoding="utf-8"))

    def test_active_request_is_read_only_g0(self) -> None:
        self.assertEqual("G0_READ_ONLY_VERIFY", self.request["mode"])
        self.assertEqual("ADMIN_AUTHORITY_GRAPH_CENSUS", self.request["g0_objective"])
        self.assertTrue(self.request["privileged_control_runtime_census"])
        self.assertFalse(self.request["provider_mutation_allowed"])
        self.assertFalse(self.request["model_inference_allowed"])
        self.assertTrue(self.request["privileged_control_runtime_scope"]["read_only"])

    def test_exact_privileged_runtime_targets_are_current(self) -> None:
        self.assertIn('"federation-omega-operator", "region": "africa-south1"', self.script)
        self.assertIn('fo-operator-sa@{PROJECT}.iam.gserviceaccount.com', self.script)
        self.assertIn('"afeme-sovereign-control-plane-v4", "region": "africa-south1"', self.script)
        self.assertIn('afeme-sovereign-runtime-v4@{PROJECT}.iam.gserviceaccount.com', self.script)

    def test_probe_is_get_only_and_never_resolves_secret_manager(self) -> None:
        self.assertIn('method="GET"', self.script)
        self.assertNotIn('method="POST"', self.script)
        self.assertNotIn("add-iam-policy-binding", self.script)
        self.assertNotIn("setIamPolicy", self.script)
        self.assertNotIn("secretmanager", self.script.lower())
        self.assertNotIn("x-fo-admin-token", self.script.lower())

    def test_authenticated_probe_mints_identity_token_without_recording_it(self) -> None:
        self.assertIn('"gcloud", "auth", "print-identity-token"', self.script)
        self.assertIn('"Authorization"] = f"Bearer {token}"', self.script)
        self.assertNotIn('"identity_token": token', self.script)
        self.assertIn('"identity_token_minted": bool(token)', self.script)

    def test_receipt_requires_service_specific_identity_and_no_mutation(self) -> None:
        self.assertIn('"runtime_identity_matches_expected"', self.script)
        self.assertIn('"wif_callable_privileged_runtimes"', self.script)
        self.assertIn('"provider_mutation_performed": False', self.script)
        self.assertIn('"secret_payload_accessed": False', self.script)
        self.assertIn('"credential_values_recorded": False', self.script)

    def test_existing_g0_probe_chains_privileged_runtime_census(self) -> None:
        self.assertIn('from privileged_control_runtime_census import main as privileged_runtime_main', self.actas)
        self.assertIn('privileged_runtime_main()', self.actas)


if __name__ == "__main__":
    unittest.main()
