from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.innovation_engine.algorithms import (
    ActionSpecificProofValidator,
    AlgorithmOpportunityMiner,
    ControlPlaneIntegrityGuard,
    CorpusSelectionIntegrityEvaluator,
    DirectiveExecutionCompiler,
    FailureToEngineeringGeneCompiler,
    TerminalFinalityResolver,
)
from evidenceops.innovation_engine.evolution import AlgorithmLedger, EvolutionGovernor
from evidenceops.innovation_engine.foundry import EvidenceOpsAlgorithmFoundry
from evidenceops.innovation_engine.evidenceops_adapter import run_case_cycle


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"
CATALOG = ROOT / "evidenceops" / "innovation_engine" / "algorithm_catalog.json"
SIGNALS = ROOT / "evidenceops" / "innovation_engine" / "fixtures" / "master_bible_lesson_signals.json"


class EvidenceOpsAlgorithmFoundryReleaseTests(unittest.TestCase):
    def test_catalog_registers_fifteen_algorithms(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(15, len(catalog["algorithms"]))
        self.assertEqual("A1_INTERNAL", catalog["authority_ceiling"])
        self.assertFalse(catalog["external_effect"])

    def test_master_bible_lesson_mining_finds_control_and_proof_algorithms(self) -> None:
        result = AlgorithmOpportunityMiner().run(
            json.loads(SIGNALS.read_text(encoding="utf-8"))
        )
        identifiers = {item["algorithm_id"] for item in result.output["opportunities"]}
        self.assertIn("ALG-EOPS-CPIG-001", identifiers)
        self.assertIn("ALG-EOPS-ASPV-001", identifiers)
        self.assertIn("ALG-EOPS-DEC-001", identifiers)

    def test_directive_compiler_blocks_artifact_only_completion(self) -> None:
        result = DirectiveExecutionCompiler().run(
            "Create and send the report",
            available_routes=[{"route_id": "BUILD", "action": "create", "available": True}],
        )
        self.assertFalse(result.output["artifact_only_completion_permitted"])
        self.assertEqual("OWNER_APPROVAL_REQUIRED", result.status)

    def test_ecasp_and_finality_fail_closed(self) -> None:
        gates = {name: True for name in CorpusSelectionIntegrityEvaluator.gate_names}
        gates["G3_BODIES_RETRIEVED"] = False
        corpus = CorpusSelectionIntegrityEvaluator().run(
            requested_claim="exhaustive final selection", gates=gates
        )
        finality = TerminalFinalityResolver().run(
            [{"item_id": "A", "state": "PENDING"}]
        )
        self.assertFalse(corpus.output["selection_or_archive_completion_permitted"])
        self.assertFalse(finality.output["final_certificate_permitted"])

    def test_control_plane_and_action_proof_require_exact_semantics(self) -> None:
        control = ControlPlaneIntegrityGuard().run(
            {
                "record_id": "R1", "record_type": "ROW", "cycle_id": "C1",
                "packet_id": "P1", "idempotency_key": "I1",
                "expected_revision": "1", "current_revision": "2",
                "lease_epoch": "E1", "cycle_start_lease_epoch": "E2",
                "collision_key": "K1", "collision_owner": "B1", "actor_id": "B2",
                "matter_id": "M1", "case_wall_id": "CW1",
            }
        )
        proof = ActionSpecificProofValidator().run(
            {"action_id": "A1", "action": "ENABLE_API", "target_id": "P1"},
            {
                "action": "STATUS", "target_id": "P1",
                "provider_response": "healthy",
                "target_readback": {"health": True}, "checked_at": "now",
                "executed": False, "semantic_match": False,
            },
        )
        self.assertEqual("BLOCKED_FAIL_CLOSED", control.status)
        self.assertEqual("ACTION_PROOF_REJECTED", proof.status)

    def test_failure_compiles_to_gene_only_after_verified_recovery(self) -> None:
        result = FailureToEngineeringGeneCompiler().run(
            failure={"fingerprint": "fp", "category": "CONTRACT", "summary": "failure"},
            recovery={
                "resolved_failure_fingerprint": "fp",
                "repair": "repair", "guard": "guard", "readback": "read back",
            },
            regression={"passed": True, "test_id": "T1"},
        )
        self.assertEqual("ENGINEERING_GENE_COMPILED", result.status)

    def test_evolution_governor_blocks_hard_regression_and_preserves_rollback(self) -> None:
        metrics = {
            "factual_accuracy": 0.8, "proof_completeness": 0.8,
            "security": 1.0, "reversibility": 0.95,
            "completion_rate": 0.7, "contradiction_detection": 0.7,
            "recovery": 0.7, "reuse": 0.6,
            "owner_burden_reduction": 0.5, "cost_efficiency": 0.7,
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = AlgorithmLedger(Path(directory) / "evolution.db")
            ledger.initialize_algorithm(
                algorithm_id="ALG-T", version="1.0.0",
                configuration={"authority_ceiling": "A1_INTERNAL", "external_effect": False},
                metrics=metrics,
            )
            candidate = ledger.create_candidate(
                algorithm_id="ALG-T", candidate_version="1.1.0",
                configuration={"threshold": 0.4, "authority_ceiling": "A1_INTERNAL", "external_effect": False},
                source_lessons=["L1"], expected_benefit="speed",
            )
            regressed = dict(metrics)
            regressed["factual_accuracy"] = 0.6
            decision = EvolutionGovernor(ledger).evaluate_and_maybe_promote(
                candidate_id=candidate["candidate_id"], candidate_metrics=regressed
            )
            self.assertEqual("REJECT", decision.decision)
            self.assertFalse(decision.promoted)
            self.assertEqual("1.0.0", decision.rollback_version)
            self.assertEqual("PASSED", ledger.verify_chain()["status"])

    def test_foundry_runs_without_external_effect_and_replays_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            foundry = EvidenceOpsAlgorithmFoundry(directory, learning_policy_path=POLICY)
            payload = {
                "cycle_id": "ROOT-CANARY",
                "lesson_signals": json.loads(SIGNALS.read_text(encoding="utf-8")),
                "directive": "Build and verify the internal algorithm catalog",
                "available_routes": [
                    {"route_id": "LOCAL", "action": "build verify", "available": True}
                ],
                "finality_items": [{"item_id": "SRC", "state": "EXTRACTED_VERIFIED"}],
            }
            first = foundry.execute_cycle(payload).as_dict()
            second = foundry.execute_cycle(payload).as_dict()
            self.assertEqual("PASSED", first["proof"]["learning_chain"]["status"])
            self.assertFalse(first["external_effect"])
            self.assertEqual(
                first["proof"]["learning_chain"]["ledger_head_hash"],
                second["proof"]["learning_chain"]["ledger_head_hash"],
            )

    def test_case_adapter_preserves_packet_and_verified_fact_boundary(self) -> None:
        packet = {
            "matter_id": "M1", "case_wall_id": "CW1", "packet_id": "P1",
            "mission": {"objective": "analyse and verify the packet"},
            "sources": [
                {"source_id": "S1", "sha256": "a" * 64, "classification": "P1", "state": "EXTRACTED_VERIFIED"}
            ],
            "verified_facts": [
                {"fact_id": "F1", "source_refs": ["S1"], "verification_state": "VERIFIED"}
            ],
            "claims": [
                {"claim_id": "C1", "description": "bounded supported claim", "fact_refs": ["F1"], "support_state": "SUPPORTED"}
            ],
            "contradictions": [], "missing_records": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            result = run_case_cycle(
                packet,
                master_bible_text=(
                    "Unknown Mapper. Epistemic Debt. Failure Laboratory. "
                    "Directive Execution Cascade. Terminal Finality. "
                    "Exhaustive Corpus Selection Integrity. Owner burden. "
                    "Independent implementation replication."
                ),
                workspace=directory,
                learning_policy_path=POLICY,
            )
        self.assertTrue(result["source_packet_unchanged"])
        self.assertFalse(result["verified_fact_write"])
        self.assertFalse(result["external_effect"])
        self.assertEqual("HELD_FOR_EVIDENCEOPS_REVIEW", result["release_state"])


if __name__ == "__main__":
    unittest.main()
