from __future__ import annotations

import unittest

from evidenceops.innovation_engine.algorithm_knowledge_utility_adoption_gate import (
    KnowledgeUtilityAdoptionGate,
)


class KnowledgeUtilityAdoptionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = KnowledgeUtilityAdoptionGate()

    def knowledge(self, state: str = "K0_OBSERVED") -> dict[str, object]:
        return {
            "knowledge_id": "NK-TEST-001",
            "title": "Generic health is not action-specific proof",
            "origin_event": "FAILURE-001",
            "origin_system": "ARCHITRON",
            "knowledge_class": "FAILURE_LESSON",
            "capture_ref": "FAILURE-LEDGER:001",
            "hypothesis": "Action-specific semantic validation prevents generic-health false positives.",
            "causal_mechanism": "The validator binds requested action and target to provider response and readback.",
            "transfer_conditions": ["provider-bound action", "action-specific readback available"],
            "non_transfer_conditions": ["pure local deterministic calculation"],
            "state": state,
        }

    def regression(self, knowledge: dict[str, object], status: str = "PASS") -> dict[str, object]:
        return {
            "knowledge_id": knowledge["knowledge_id"],
            "knowledge_sha256": self.gate.knowledge_sha256(knowledge),
            "status": status,
            "proof_ref": f"REGRESSION:{status}",
        }

    def adoption(
        self,
        knowledge: dict[str, object],
        system: str,
        *,
        real: bool = False,
        independence: bool = False,
        authority_inherited: bool = False,
    ) -> dict[str, object]:
        return {
            "knowledge_id": knowledge["knowledge_id"],
            "knowledge_sha256": self.gate.knowledge_sha256(knowledge),
            "adopter_system": system,
            "adoption_mode": "RUNTIME_GATE",
            "source_ref": f"{system}:CONTROL",
            "authority_inherited": authority_inherited,
            "real_execution": real,
            "execution_ref": f"{system}:EXECUTION" if real else "",
            "outcome": "GENERIC_HEALTH_REJECTED" if real else "",
            "behavior_changed": real,
            "independence_ref": f"{system}:INDEPENDENCE" if independence else "",
        }

    def impact(self, *, operational: int = 4, synthetic: int = 20) -> dict[str, object]:
        return {
            "operational_samples": operational,
            "synthetic_samples": synthetic,
            "proof_completion": 0.90,
            "candidate_confidence": 0.80,
            "shadow_qualified": True,
            "metrics": [
                {
                    "name": "false_positive_rate",
                    "baseline": 0.40,
                    "after": 0.05,
                    "direction": "LOWER_BETTER",
                    "proof_ref": "IMPACT:FALSE-POSITIVE-RATE",
                },
                {
                    "name": "proof_quality",
                    "baseline": 0.60,
                    "after": 0.90,
                    "direction": "HIGHER_BETTER",
                    "proof_ref": "IMPACT:PROOF-QUALITY",
                },
            ],
        }

    def test_claimed_state_cannot_outrun_evidence(self) -> None:
        knowledge = self.knowledge()
        knowledge["capture_ref"] = ""
        knowledge["claimed_state"] = "K8_STANDARD"
        result = self.gate.run(knowledge)
        self.assertEqual("K0_OBSERVED", result.output["highest_evidence_state"])
        self.assertIn("CLAIMED_STATE_EXCEEDS_EVIDENCE", result.violations)

    def test_failure_capture_does_not_invent_causal_hypothesis(self) -> None:
        captured = self.gate.capture_failure_memory(
            knowledge_id="NK-FAIL-001",
            title="Failure lesson",
            origin_system="ARCHITRON",
            origin_event="FAIL-001",
            capture_ref="FAILURE-MEMORY:001",
            failure_fingerprint="SEMANTIC_FAILURE:generic health",
            repair_action="add action-specific validation",
        )
        self.assertEqual("K1_CAPTURED", captured["state"])
        self.assertEqual("", captured["hypothesis"])
        self.assertEqual("", captured["causal_mechanism"])

    def test_regression_pass_advances_only_to_k3_without_adopter(self) -> None:
        knowledge = self.knowledge("K2_HYPOTHESIS")
        result = self.gate.run(knowledge, regression_receipts=[self.regression(knowledge)])
        self.assertEqual("K3_REGRESSION_TESTED", result.output["highest_evidence_state"])
        self.assertEqual("K3_REGRESSION_TESTED", result.output["next_state"])

    def test_adoption_requires_other_system_and_matching_hash(self) -> None:
        knowledge = self.knowledge("K3_REGRESSION_TESTED")
        same_origin = self.adoption(knowledge, "ARCHITRON")
        bad_hash = self.adoption(knowledge, "BUBBLES")
        bad_hash["knowledge_sha256"] = "0" * 64
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[same_origin, bad_hash],
        )
        self.assertEqual("K3_REGRESSION_TESTED", result.output["highest_evidence_state"])
        self.assertIn("ADOPTION_REQUIRES_OTHER_SYSTEM", result.violations)
        self.assertIn("ADOPTION_KNOWLEDGE_HASH_MISMATCH", result.violations)

    def test_adoption_never_inherits_authority(self) -> None:
        knowledge = self.knowledge("K3_REGRESSION_TESTED")
        receipt = self.adoption(knowledge, "BUBBLES", authority_inherited=True)
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[receipt],
        )
        self.assertEqual(0, result.output["valid_adoption_count"])
        self.assertIn("KNOWLEDGE_ADOPTION_CANNOT_INHERIT_AUTHORITY", result.violations)

    def test_real_execution_is_separate_from_adoption(self) -> None:
        knowledge = self.knowledge("K3_REGRESSION_TESTED")
        adopted = self.adoption(knowledge, "BUBBLES", real=False)
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[adopted],
        )
        self.assertEqual("K4_ADOPTED", result.output["highest_evidence_state"])
        self.assertEqual(0, result.output["real_execution_count"])

    def test_measured_impact_is_required_for_k6_and_unknown_stays_unknown(self) -> None:
        knowledge = self.knowledge("K5_EXECUTED")
        adoption = self.adoption(knowledge, "BUBBLES", real=True, independence=True)
        unknown_impact = {
            "operational_samples": 10,
            "synthetic_samples": 100,
            "proof_completion": None,
            "candidate_confidence": None,
            "shadow_qualified": False,
            "metrics": [{"name": "owner_load", "baseline": None, "after": None}],
        }
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[adoption],
            impact=unknown_impact,
        )
        self.assertEqual("K5_EXECUTED", result.output["highest_evidence_state"])
        self.assertIsNone(result.output["impact"]["proof_completion"])
        self.assertIsNone(result.output["impact"]["candidate_confidence"])
        self.assertIn("IMPACT_METRIC_NOT_MEASURED", result.violations)

    def test_synthetic_samples_do_not_substitute_for_operational_samples(self) -> None:
        knowledge = self.knowledge("K5_EXECUTED")
        adoption = self.adoption(knowledge, "BUBBLES", real=True, independence=True)
        impact = self.impact(operational=0, synthetic=1000)
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[adoption],
            impact=impact,
        )
        self.assertEqual("K5_EXECUTED", result.output["highest_evidence_state"])

    def test_k7_requires_three_independent_executing_adopters(self) -> None:
        knowledge = self.knowledge("K6_IMPACT_PROVEN")
        adopters = [
            self.adoption(knowledge, system, real=True, independence=True)
            for system in ("BUBBLES", "CASEFORGE", "EVIDENCEOPS")
        ]
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=adopters,
            impact=self.impact(),
        )
        self.assertEqual("K7_FEDERATED", result.output["highest_evidence_state"])
        self.assertEqual(3, result.output["independent_execution_system_count"])

    def test_k8_requires_operational_thresholds_and_explicit_authorization(self) -> None:
        knowledge = self.knowledge("K7_FEDERATED")
        adopters = [
            self.adoption(knowledge, system, real=True, independence=True)
            for system in ("BUBBLES", "CASEFORGE", "EVIDENCEOPS")
        ]
        impact = self.impact(operational=12)
        without_authority = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=adopters,
            impact=impact,
        )
        self.assertEqual("K7_FEDERATED", without_authority.output["highest_evidence_state"])
        authorization = {
            "knowledge_id": knowledge["knowledge_id"],
            "knowledge_sha256": self.gate.knowledge_sha256(knowledge),
            "authorized": True,
            "authority_ref": "OMEGA5-PROMOTION:001",
        }
        promoted = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=adopters,
            impact=impact,
            promotion_authorization=authorization,
        )
        self.assertEqual("K8_STANDARD", promoted.output["highest_evidence_state"])
        self.assertEqual("STANDARD", promoted.output["utility_verdict"])

    def test_persisted_transition_advances_only_one_state_at_a_time(self) -> None:
        knowledge = self.knowledge("K2_HYPOTHESIS")
        adopters = [
            self.adoption(knowledge, system, real=True, independence=True)
            for system in ("BUBBLES", "CASEFORGE", "EVIDENCEOPS")
        ]
        authorization = {
            "knowledge_id": knowledge["knowledge_id"],
            "knowledge_sha256": self.gate.knowledge_sha256(knowledge),
            "authorized": True,
            "authority_ref": "OMEGA5-PROMOTION:001",
        }
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=adopters,
            impact=self.impact(operational=12),
            promotion_authorization=authorization,
        )
        self.assertEqual("K8_STANDARD", result.output["highest_evidence_state"])
        self.assertEqual("K3_REGRESSION_TESTED", result.output["next_state"])

    def test_regression_failure_forces_active_rollback_without_erasing_history(self) -> None:
        knowledge = self.knowledge("K7_FEDERATED")
        adopters = [
            self.adoption(knowledge, system, real=True, independence=True)
            for system in ("BUBBLES", "CASEFORGE", "EVIDENCEOPS")
        ]
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge, "PASS"), self.regression(knowledge, "FAIL")],
            adoption_receipts=adopters,
            impact=self.impact(operational=12),
        )
        self.assertEqual("K2_HYPOTHESIS", result.output["highest_evidence_state"])
        self.assertEqual("ROLLBACK", result.output["utility_verdict"])
        self.assertEqual("KNOWLEDGE_ROLLBACK_REQUIRED", result.status)
        self.assertIn("CURRENT_STATE_EXCEEDS_CURRENT_EVIDENCE", result.violations)

    def test_public_summary_excludes_private_reasoning_and_raw_proof_details(self) -> None:
        knowledge = self.knowledge("K3_REGRESSION_TESTED")
        result = self.gate.run(
            knowledge,
            regression_receipts=[self.regression(knowledge)],
            adoption_receipts=[self.adoption(knowledge, "BUBBLES")],
        )
        summary = result.output["public_summary"]
        self.assertNotIn("hypothesis", summary)
        self.assertNotIn("causal_mechanism", summary)
        self.assertNotIn("transfer_conditions", summary)
        self.assertNotIn("evidence_refs", summary)
        self.assertEqual("NK-TEST-001", summary["knowledge_id"])


if __name__ == "__main__":
    unittest.main()
