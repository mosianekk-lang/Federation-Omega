from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AuthorityExportContractTests(unittest.TestCase):
    def test_export_policy_requires_complete_authority_bound_ops_package(self):
        policy = json.loads(
            (ROOT / "phoenix" / "export_policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual("1.0.10", policy["version"])
        required = set(policy["ops"]["required_files"])
        required.update(policy["ops"].get("required_v3_files", []))
        expected = {
            "provider_authority_probe.py",
            "provider_cutover_authority_bound.py",
            "provider_cutover_candidate.py",
            "provider_cutover_guarded.py",
            "provider_cutover_v3_live_guard.py",
            "provider_cutover.py",
            "provider_cutover_authorization_use.py",
            "provider_cutover_v3_1.py",
            "provider_cutover_v3_base.py",
            "provider_cutover_outcome_reconciler.py",
            "governance/APPLY_ENTRYPOINT.json",
            "governance/CUTOVER_CANDIDATE_CONTRACT.json",
            "governance/PROVIDER_AUTHORITY_PROBE_CONTRACT.json",
            "governance/OPS_CONTRACT.json",
        }
        self.assertTrue(expected.issubset(required), sorted(expected - required))
        self.assertIn(
            "provider_cutover_authorization_use.py",
            policy["ops"]["required_v3_files"],
        )

    def test_v3_builder_enforces_base_and_v3_requirements(self):
        source = (ROOT / "phoenix" / "build_exports_v3.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'required.update(policy["ops"].get("required_v3_files", []))',
            source,
        )

    def test_export_receipt_metadata_names_true_canonical_route(self):
        source = (ROOT / "phoenix" / "build_exports_v3.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"entrypoint": "provider_cutover_authority_bound.py"', source
        )
        self.assertIn(
            '"provider_authority_probe": "provider_authority_probe.py"', source
        )
        self.assertIn(
            '"candidate_validator": "provider_cutover_candidate.py"', source
        )
        self.assertIn(
            '"authorization_base_coordinator": "provider_cutover.py"', source
        )
        self.assertIn('"provider_authority_receipt_required": True', source)
        self.assertIn('"provider_authority_probe_get_only": True', source)
        self.assertNotIn('"entrypoint": "provider_cutover.py"', source)

    def test_ops_contract_matches_apply_contract(self):
        governance = ROOT / "phoenix" / "ops-template" / "governance"
        ops = json.loads((governance / "OPS_CONTRACT.json").read_text())
        entrypoint = json.loads((governance / "APPLY_ENTRYPOINT.json").read_text())
        authority = json.loads(
            (governance / "PROVIDER_AUTHORITY_PROBE_CONTRACT.json").read_text()
        )
        self.assertEqual("1.2.0", ops["version"])
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            ops["canonical_apply_entrypoint"],
        )
        self.assertEqual(
            ops["canonical_apply_entrypoint"],
            entrypoint["canonical_apply_entrypoint"],
        )
        self.assertTrue(ops["authority_rules"]["provider_authority_receipt_required"])
        self.assertTrue(entrypoint["provider_authority_receipt_required"])
        self.assertTrue(authority["probe_get_only"])
        self.assertFalse(authority["credential_value_recorded"])
        self.assertFalse(authority["provider_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
