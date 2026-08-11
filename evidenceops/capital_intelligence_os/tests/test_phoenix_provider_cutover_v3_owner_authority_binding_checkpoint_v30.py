from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_authority_binding_checkpoint_v30.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v30.json"


def verify_hash(payload: dict, field: str) -> str:
    body = dict(payload)
    claimed = body.pop(field)
    calculated = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if claimed != calculated:
        raise AssertionError(f"{field} mismatch")
    return claimed


class OwnerAuthorityBindingCheckpointV30Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        cls.p = json.loads(PROJECTION.read_text(encoding="utf-8"))

    def test_hashes_dependency_order_and_service_priority(self):
        self.assertEqual("67acaab603e7a1c6c6c1618a4201673f6c6ba6a49b29642e680734093bd4624d", verify_hash(self.c, "checkpoint_sha256"))
        self.assertEqual("8d45d4301c41a7ab974988f55c5255d72d1b5480d6e2e1c625a9a476d40efb0a", verify_hash(self.p, "projection_sha256"))
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], self.p["dependency_order"])
        self.assertTrue(self.p["dependency_order_preserved"])
        self.assertTrue(self.p["service_enabled_platform_first"])
        self.assertTrue(self.p["self_service_saas_held"])

    def test_owner_provider_binding_is_canonical(self):
        engine = self.c["export_receipt"]["provider_cutover_engine"]
        self.assertEqual("3.5", engine["version"])
        self.assertEqual("provider_cutover_owner_authority_bound.py", engine["entrypoint"])
        self.assertTrue(engine["owner_authorization_provider_receipt_hash_binding_required"])
        self.assertTrue(engine["owner_authorization_repository_creation_endpoint_binding_required"])
        self.assertFalse(engine["owner_authorization_external_commercial_gate_advancement_allowed"])
        self.assertFalse(engine["provider_apply_performed"])

    def test_provider_native_proofs_and_archives_are_exact(self):
        admission = self.c["provider_native_admission"]
        self.assertEqual(30968927309, admission["airlock_run"])
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual("155/155_PASS", admission["provider_control_regressions"]["provider_cutover_v3_family"])
        final = self.c["provider_native_final_head"]
        self.assertEqual("7f28a6e1770c8671bdf56d4b305f816955905122", final["source_sha"])
        self.assertEqual(30969403510, final["workflow_run"])
        self.assertEqual("success", final["conclusion"])
        receipt = self.c["export_receipt"]
        self.assertEqual("f7f544e8ca5ea8e726ad949999efe80ad20a4e6805df002c83b78beb5a07c912", receipt["core"]["archive_sha256"])
        self.assertEqual("1ff013f6b4347bf76d6140e4062a88f154bf6102bcb152f43b2bbc96eaa85a71", receipt["ops"]["archive_sha256"])
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])

    def test_live_authority_commercial_truth_and_drive_fail_closed(self):
        authority = self.c["provider_authority_readback"]
        self.assertEqual(["mosianekk-lang/Federation-Omega"], authority["installed_repositories"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_core_repository"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_ops_repository"])
        self.assertFalse(authority["provider_mutation_performed"])
        truth = self.c["commercial_truth"]
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        drive = self.c["google_drive_release"]
        self.assertFalse(drive["shared"])
        self.assertEqual("a8d11a06e5bb564130c8d56841946c3826bb022943f936622a8e0ddebe30ca4f", drive["text_export_sha256"])


if __name__ == "__main__":
    unittest.main()
