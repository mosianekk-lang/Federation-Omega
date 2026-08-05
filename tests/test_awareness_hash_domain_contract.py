from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AwarenessHashDomainContractTests(unittest.TestCase):
    def test_hash_domain_contract_matches_public_contract(self):
        domain = json.loads(
            (ROOT / "governance" / "federation_awareness_hash_domain_v2.json").read_text()
        )
        public = json.loads(
            (ROOT / "governance" / "federation_surface_awareness_v1.json").read_text()
        )
        private = public["private_manifest"]
        self.assertEqual(domain["legacy_logical_sha256"], private["legacy_logical_sha256"])
        self.assertEqual(domain["logical_sha256_v2"], private["logical_sha256_v2"])
        self.assertEqual(
            "governance/federation_awareness_hash_domain_v2.json",
            private["hash_domain_contract"],
        )
        self.assertTrue(private["runtime_fields_excluded_from_logical_hash"])

    def test_contract_has_rollback_and_truth_boundaries(self):
        domain = json.loads(
            (ROOT / "governance" / "federation_awareness_hash_domain_v2.json").read_text()
        )
        self.assertTrue(domain["mutation_policy"]["rollback_plan_required"])
        self.assertFalse(domain["truth_boundary"]["hash_domain_contract_proves_drive_mutation"])
        self.assertFalse(domain["truth_boundary"]["rollback_simulation_proves_provider_rollback"])


if __name__ == "__main__":
    unittest.main()
