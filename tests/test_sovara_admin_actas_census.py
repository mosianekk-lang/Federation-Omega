from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sovara" / "gemini" / "admin_actas_census.py"
BOOTSTRAP = ROOT / "sovara" / "gemini" / "bootstrap_gateway.sh"
G0_TEMPLATE = ROOT / "governance" / "sovara_gemini_g0_authority_census_request_template_v1.json"


class SovaraAdminActAsCensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = SCRIPT.read_text(encoding="utf-8")
        self.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.request = json.loads(G0_TEMPLATE.read_text(encoding="utf-8"))

    def test_g0_template_is_read_only_and_role_stable(self) -> None:
        self.assertEqual("G0_READ_ONLY_VERIFY", self.request["mode"])
        self.assertEqual("ADMIN_AUTHORITY_GRAPH_CENSUS", self.request["g0_objective"])
        self.assertTrue(self.request["admin_actas_census_probe"])
        self.assertFalse(self.request["provider_mutation_allowed"])
        self.assertFalse(self.request["model_inference_allowed"])
        self.assertTrue(self.request["admin_actas_census_scope"]["read_only"])

    def test_only_actas_permission_is_tested_on_admin_service_accounts(self) -> None:
        self.assertIn('ACT_AS_PERMISSION = "iam.serviceAccounts.actAs"', self.script)
        self.assertIn('"roles/owner"', self.script)
        self.assertIn('"roles/resourcemanager.projectIamAdmin"', self.script)
        self.assertIn('"roles/iam.securityAdmin"', self.script)
        self.assertIn(":testIamPermissions", self.script)
        self.assertNotIn("add-iam-policy-binding", self.script)
        self.assertNotIn("setIamPolicy", self.script)
        self.assertNotIn("service-accounts create", self.script)

    def test_known_control_runtime_identity_readback_is_bounded(self) -> None:
        self.assertIn('(\"architron9\", \"africa-south1\")', self.script)
        self.assertIn('(\"federation-omega-operator\", \"us-central1\")', self.script)
        self.assertIn('"gcloud", "run", "services", "describe"', self.script)
        self.assertIn('"service_account"', self.script)
        self.assertIn('"admin_control_runtime_matches"', self.script)

    def test_bootstrap_runs_census_only_during_verify(self) -> None:
        self.assertIn('if [[ "$MODE" == "verify" && -f sovara/gemini/admin_actas_census.py ]]', self.bootstrap)
        self.assertIn('python3 sovara/gemini/admin_actas_census.py >&2 || true', self.bootstrap)

    def test_receipt_forbids_secret_and_provider_mutation_claims(self) -> None:
        self.assertIn('"provider_mutation_performed": False', self.script)
        self.assertIn('"credential_values_recorded": False', self.script)
        self.assertIn('"secret_payload_accessed": False', self.script)
        self.assertIn('"automated_owner_worker_route_available": bool(reusable)', self.script)


if __name__ == "__main__":
    unittest.main()
