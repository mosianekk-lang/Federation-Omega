from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"
CATALOG = ROOT / "evidenceops" / "innovation_engine" / "algorithm_catalog.json"


class FederationKnowledgeAdoptionPolicyTests(unittest.TestCase):
    def test_learning_policy_binds_the_catalogued_adoption_gate(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        knowledge = policy["knowledge_adoption"]
        identifiers = {item["algorithm_id"] for item in catalog["algorithms"]}
        self.assertEqual("ALG-EOPS-KUAG-001", knowledge["algorithm_id"])
        self.assertIn(knowledge["algorithm_id"], identifiers)
        self.assertEqual(
            [
                "K0_OBSERVED",
                "K1_CAPTURED",
                "K2_HYPOTHESIS",
                "K3_REGRESSION_TESTED",
                "K4_ADOPTED",
                "K5_EXECUTED",
                "K6_IMPACT_PROVEN",
                "K7_FEDERATED",
                "K8_STANDARD",
            ],
            knowledge["states"],
        )

    def test_policy_forbids_copy_synthetic_and_authority_shortcuts(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        controls = set(policy["non_negotiable_controls"])
        self.assertIn("COPY_IS_NOT_ADOPTION_PROOF", controls)
        self.assertIn("SYNTHETIC_IS_NOT_OPERATIONAL_PROOF", controls)
        self.assertIn("KNOWLEDGE_ADOPTION_NEVER_INHERITS_AUTHORITY", controls)
        knowledge = policy["knowledge_adoption"]
        self.assertFalse(knowledge["authority_inheritance_from_knowledge"])
        self.assertTrue(knowledge["standard_promotion_requires_separate_authorized_omega5_gate"])

    def test_shared_projection_excludes_private_learning_fields(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        knowledge = policy["knowledge_adoption"]
        public = set(knowledge["public_projection_fields"])
        private = set(knowledge["private_fields_excluded_from_shared_projection"])
        self.assertFalse(public & private)
        self.assertIn("knowledge_sha256", public)
        self.assertIn("hypothesis", private)
        self.assertIn("causal_mechanism", private)
        self.assertIn("secret_or_credential_material", private)


if __name__ == "__main__":
    unittest.main()
