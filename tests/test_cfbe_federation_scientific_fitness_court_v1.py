from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.federation_scientific_fitness_court_v1 import (
    FitnessAction,
    ScientificExperiment,
    SystemFitnessObservation,
    compile_fitness_court,
    default_scientific_experiments,
    derive_system_actions,
    rank_experiments,
)


MAIN = "0b359d501450c9875c336862249a87531c84d67d"


def estate():
    return [
        {"system_id":"BUBBLES","role":"orchestration","semantic_cluster":"ORCHESTRATION","current_projection_verified":True,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":1.0,"dependency_ids":["KDV","CFBE"]},
        {"system_id":"FORMATION_OMEGA","role":"formation","semantic_cluster":"ORCHESTRATION","current_projection_verified":False,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":0,"complexity_cost":1.2,"dependency_ids":["KDV"]},
        {"system_id":"OMEGA_ONE","role":"scheduler","semantic_cluster":"ORCHESTRATION","current_projection_verified":False,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":0,"complexity_cost":1.2,"dependency_ids":["CFBE"]},
        {"system_id":"JARVIS","role":"independent assurance","semantic_cluster":"ASSURANCE","current_projection_verified":False,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":0,"complexity_cost":0.9,"dependency_ids":["KDV"],"independent_assurance_role":True},
        {"system_id":"REALITY_GUARD","role":"truth/failure guard","semantic_cluster":"ASSURANCE","current_projection_verified":True,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":0.8,"dependency_ids":["KDV"],"independent_assurance_role":True},
        {"system_id":"PROOFOS","role":"proof selection","semantic_cluster":"ASSURANCE","current_projection_verified":True,"proof_state":"SOURCE_PROVEN","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":0.8,"dependency_ids":["KDV"]},
        {"system_id":"KDV","role":"canonical state","semantic_cluster":"STATE_MEMORY","current_projection_verified":True,"proof_state":"PROVEN_BOUNDED","provider_runtime_proven":True,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":1.0,"dependency_ids":[]},
        {"system_id":"CFBE","role":"benchmark governor","semantic_cluster":"EVALUATION","current_projection_verified":True,"proof_state":"SOURCE_PROVEN","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":1.0,"dependency_ids":["KDV"]},
        {"system_id":"SENTINEL","role":"freshness observer","semantic_cluster":"OBSERVABILITY","current_projection_verified":True,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":0.8,"dependency_ids":["KDV"],"independent_assurance_role":True},
        {"system_id":"FAILURE_WIN_AUTOFIX","role":"recovery","semantic_cluster":"RECOVERY","current_projection_verified":True,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":0.9,"dependency_ids":["KDV"]},
        {"system_id":"SOVARA","role":"effect authority","semantic_cluster":"EXECUTION_AUTHORITY","current_projection_verified":True,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":1,"complexity_cost":1.0,"dependency_ids":["KDV","CFBE"]},
        {"system_id":"CHATBRIDGE","role":"continuity","semantic_cluster":"CONTINUITY","current_projection_verified":False,"proof_state":"PARTIAL","provider_runtime_proven":False,"owner_value_pairs":0,"invocation_evidence_count":0,"complexity_cost":1.1,"dependency_ids":["KDV"]},
    ]


class FitnessCourtTests(unittest.TestCase):
    def test_default_queue_is_twelve_no_effect_experiments(self):
        items = default_scientific_experiments()
        self.assertEqual(len(items), 12)
        self.assertEqual(len({x.experiment_id for x in items}), 12)
        self.assertTrue(all(not x.provider_effect_authorized for x in items))
        self.assertTrue(all(x.execution_class == "A1_INTERNAL_NO_EFFECT" for x in items))

    def test_information_gain_ranks_owner_value_first(self):
        ranked = rank_experiments(default_scientific_experiments())
        self.assertEqual(ranked[0].experiment_id, "EXP-CFBE-FIT-001")

    def test_unproven_value_triggers_value_proof(self):
        item = SystemFitnessObservation.from_mapping(estate()[0])
        receipt = derive_system_actions(item)
        self.assertIn(FitnessAction.PROVE_OWNER_VALUE, receipt.actions)

    def test_provider_expansion_held_before_value(self):
        item = SystemFitnessObservation.from_mapping(estate()[0])
        receipt = derive_system_actions(item)
        self.assertIn(FitnessAction.HOLD_PROVIDER_EXPANSION_UNTIL_VALUE, receipt.actions)

    def test_stale_projection_reanchors(self):
        item = SystemFitnessObservation.from_mapping(estate()[1])
        receipt = derive_system_actions(item)
        self.assertIn(FitnessAction.REANCHOR_CURRENT_SOURCE, receipt.actions)

    def test_independent_assurance_is_preserved(self):
        item = SystemFitnessObservation.from_mapping(estate()[3])
        receipt = derive_system_actions(item)
        self.assertIn(FitnessAction.PRESERVE_INDEPENDENCE, receipt.actions)

    def test_complete_bounded_system_can_retain(self):
        item = SystemFitnessObservation(
            "X","bounded","UNIQUE",True,"PROVEN",True,10,2,1.0,(),False,("proof",)
        )
        receipt = derive_system_actions(item)
        self.assertEqual(receipt.actions, (FitnessAction.RETAIN,))

    def test_court_detects_two_overlap_clusters(self):
        receipt = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        self.assertEqual(set(receipt.overlap_clusters), {"ASSURANCE","ORCHESTRATION"})

    def test_court_records_full_owner_value_deficit(self):
        receipt = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        self.assertEqual(receipt.owner_value_pair_deficit, 10)
        self.assertEqual(receipt.next_experiment_id, "EXP-CFBE-FIT-001")

    def test_court_never_creates_top_level_system(self):
        receipt = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        self.assertFalse(receipt.new_top_level_system_required)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)

    def test_structural_overlap_only_creates_review_actions(self):
        receipt = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        self.assertTrue(any(x.startswith("RUN_EQUIVALENCE_COURT:") for x in receipt.structural_ecology_actions))

    def test_invalid_source_sha_rejected(self):
        with self.assertRaises(ValueError):
            compile_fitness_court(source_main_sha="bad", system_observations=estate(), owner_value_pair_count=0)

    def test_duplicate_system_rejected(self):
        items = estate()
        items.append(dict(items[0]))
        with self.assertRaises(ValueError):
            compile_fitness_court(source_main_sha=MAIN, system_observations=items, owner_value_pair_count=0)

    def test_effectful_experiment_rejected(self):
        with self.assertRaises(ValueError):
            ScientificExperiment(
                "E",("X",),"h","m",(),.5,.2,1,.1,.9,
                provider_effect_authorized=True,
            ).validate()

    def test_receipt_hash_is_deterministic(self):
        left = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        right = compile_fitness_court(source_main_sha=MAIN, system_observations=estate(), owner_value_pair_count=0)
        self.assertEqual(left.receipt_sha256, right.receipt_sha256)


if __name__ == "__main__":
    unittest.main()
