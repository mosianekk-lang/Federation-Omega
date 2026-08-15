from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evidenceops.innovation_engine.algorithm_knowledge_utility_adoption_gate import (
    KnowledgeUtilityAdoptionGate,
)
from evidenceops.innovation_engine.foundry import EvidenceOpsAlgorithmFoundry


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"


class FederationKnowledgeAdoptionFoundryTests(unittest.TestCase):
    def test_foundry_executes_registered_knowledge_candidate(self) -> None:
        knowledge = {
            "knowledge_id": "NK-FOUNDRY-001",
            "title": "Generic health is not provider action proof",
            "origin_event": "FAIL-001",
            "origin_system": "ARCHITRON",
            "knowledge_class": "FAILURE_LESSON",
            "capture_ref": "FAILURE:001",
            "hypothesis": "Action-specific validation prevents health-response false positives.",
            "causal_mechanism": "Requested action and target are compared with semantic provider readback.",
            "transfer_conditions": ["provider action", "action-specific readback"],
            "non_transfer_conditions": ["pure local calculation"],
            "state": "K2_HYPOTHESIS",
        }
        digest = KnowledgeUtilityAdoptionGate.knowledge_sha256(knowledge)
        candidate = {
            "knowledge": knowledge,
            "regression_receipts": [
                {
                    "knowledge_id": "NK-FOUNDRY-001",
                    "knowledge_sha256": digest,
                    "status": "PASS",
                    "proof_ref": "REGRESSION:001",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            foundry = EvidenceOpsAlgorithmFoundry(directory, learning_policy_path=POLICY)
            result = foundry.execute_cycle(
                {
                    "cycle_id": "KNOWLEDGE-CANARY-001",
                    "lesson_signals": [],
                    "knowledge_candidates": [candidate],
                }
            ).as_dict()
        by_id = {item["algorithm_id"]: item for item in result["algorithm_results"]}
        self.assertIn("ALG-EOPS-KUAG-001", by_id)
        knowledge_result = by_id["ALG-EOPS-KUAG-001"]
        self.assertEqual("K3_REGRESSION_TESTED", knowledge_result["output"]["highest_evidence_state"])
        self.assertFalse(result["external_effect"])


if __name__ == "__main__":
    unittest.main()
