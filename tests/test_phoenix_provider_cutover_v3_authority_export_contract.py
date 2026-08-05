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
        self.assertEqual("1.0.17", policy["version"])
        required = set(policy["ops"]["required_files"])
        required.update(policy["ops"].get("required_v3_files", []))
        expected = {
            "provider_authority_probe.py",
            "provider_cutover_owner_authority_bound.py",
            "provider_cutover_authority_bound.py",
            "provider_cutover_candidate.py",
            "provider_cutover_guarded.py",
            "provider_cutover_v3_live_guard.py",
            "owner_sealed_packet.py",
            "owner_custody_ceremony.py",
            "owner_custody_attestation.py",
            "provider_authenticated_owner_attestation.py",
            "provider_attested_authorization.py",
            "owner_execution_handoff.py",
            "provider_cutover.py",
            "provider_cutover_authorization_use.py",
            "provider_cutover_v3_1.py",
            "provider_cutover_v3_base.py",
            "provider_cutover_outcome_reconciler.py",
            "governance/APPLY_ENTRYPOINT.json",
            "governance/CUTOVER_CANDIDATE_CONTRACT.json",
            "governance/PROVIDER_AUTHORITY_PROBE_CONTRACT.json",
            "governance/OWNER_SEALED_PACKET_CANDIDATE_CONTRACT.json",
            "governance/OWNER_CUSTODY_CEREMONY_CONTRACT.json",
            "governance/OWNER_CUSTODY_ATTESTATION_CONTRACT.json",
            "governance/PROVIDER_AUTHENTICATED_OWNER_ATTESTATION_CONTRACT.json",
            "governance/PROVIDER_ATTESTED_AUTHORIZATION_CONTRACT.json",
            "governance/OWNER_EXECUTION_HANDOFF_CONTRACT.json",
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
        self.assertIn('"version": "3.5"', source)
        self.assertIn(
            '"entrypoint": "provider_cutover_owner_authority_bound.py"', source
        )
        self.assertIn(
            '"authority_bound_internal_entrypoint": "provider_cutover_authority_bound.py"',
            source,
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
        self.assertIn('"provider_authority_receipt_max_age_seconds": 300', source)
        self.assertIn(
            '"provider_authority_just_in_time_reprobe_required": True', source
        )
        self.assertIn('"provider_authority_probe_get_only": True', source)
        self.assertIn(
            '"owner_authorization_provider_receipt_hash_binding_required": True',
            source,
        )
        self.assertIn(
            '"owner_authorization_repository_creation_endpoint_binding_required": True',
            source,
        )
        self.assertIn(
            '"owner_sealed_packet_candidate_builder": "owner_sealed_packet.py"',
            source,
        )
        self.assertNotIn('"entrypoint": "provider_cutover.py"', source)

    def test_ops_contract_matches_apply_contract(self):
        governance = ROOT / "phoenix" / "ops-template" / "governance"
        ops = json.loads((governance / "OPS_CONTRACT.json").read_text())
        entrypoint = json.loads((governance / "APPLY_ENTRYPOINT.json").read_text())
        authority = json.loads(
            (governance / "PROVIDER_AUTHORITY_PROBE_CONTRACT.json").read_text()
        )
        self.assertEqual("1.4.0", ops["version"])
        self.assertEqual(
            "provider_cutover_owner_authority_bound.py",
            ops["canonical_apply_entrypoint"],
        )
        self.assertEqual(
            ops["canonical_apply_entrypoint"],
            entrypoint["canonical_apply_entrypoint"],
        )
        rules = ops["authority_rules"]
        self.assertTrue(
            rules["owner_authorization_provider_receipt_hash_binding_required"]
        )
        self.assertTrue(
            rules[
                "owner_authorization_repository_creation_endpoint_binding_required"
            ]
        )
        self.assertFalse(
            rules["owner_authorization_external_commercial_gate_advancement_allowed"]
        )
        self.assertTrue(rules["provider_authority_receipt_required"])
        self.assertEqual(300, rules["provider_authority_receipt_max_age_seconds"])
        self.assertTrue(rules["provider_authority_just_in_time_reprobe_required"])
        self.assertTrue(rules["provider_authority_continuity_required"])
        self.assertTrue(
            entrypoint["owner_authorization_provider_receipt_hash_binding"]
        )
        self.assertTrue(
            entrypoint["owner_authorization_repository_creation_endpoint_binding"]
        )
        self.assertFalse(
            entrypoint[
                "owner_authorization_external_commercial_gate_advancement_allowed"
            ]
        )
        self.assertTrue(entrypoint["provider_authority_receipt_required"])
        self.assertEqual(
            300, entrypoint["provider_authority_receipt_max_age_seconds"]
        )
        self.assertTrue(
            entrypoint["provider_authority_just_in_time_reprobe_required"]
        )
        self.assertTrue(
            entrypoint["provider_authority_continuity_drift_invalidates"]
        )
        self.assertTrue(authority["probe_get_only"])
        self.assertEqual(300, authority["authority_receipt_max_age_seconds"])
        self.assertTrue(
            authority["just_in_time_reprobe_required_before_authorization_state"]
        )
        self.assertFalse(authority["credential_value_recorded"])
        self.assertFalse(authority["provider_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
