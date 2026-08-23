import unittest

from ao_harmonic_v3.adaptive_cycle import (
    AdaptiveCycleEngine,
    AdaptiveCycleRequest,
    BestEffortGovernor,
    BoundedDeltaMemory,
    CodeRestructuringPlanner,
    CodeUnit,
    CompactionPolicy,
    ContextAtom,
    ContextCompactor,
    CycleOutcome,
    EffortRecord,
)
from ao_harmonic_v3.evolution import LearningEvent, LearningLedger
from ao_harmonic_v3.models import PerformanceVector


def effort() -> EffortRecord:
    return EffortRecord(
        attempted_routes=("primary", "fallback"),
        self_tests=(("unit", True), ("readback", True)),
        prework_complete=True,
    )


class AdaptiveCycleTests(unittest.TestCase):
    def test_two_x_target_is_measured_before_claim(self):
        incumbent = PerformanceVector(quality=2, reliability=2, proof=1)
        candidate = PerformanceVector(quality=5, reliability=4, proof=3)
        result = AdaptiveCycleEngine().run(
            AdaptiveCycleRequest(
                cycle_id="C1",
                objective="improve task quality",
                incumbent=incumbent,
                candidate=candidate,
                effort=effort(),
                invariant_checks=(("no_regression", True),),
            )
        )
        self.assertEqual(result.outcome, CycleOutcome.PROMOTE_2X)
        self.assertTrue(result.promote)
        self.assertTrue(result.target_met)
        self.assertEqual(result.claim_state, "MEASURED_2X_TARGET_MET")

    def test_incremental_gain_is_promoted_without_false_2x_claim(self):
        incumbent = PerformanceVector(quality=4, reliability=4, proof=2)
        candidate = PerformanceVector(quality=5, reliability=4, proof=3)
        result = AdaptiveCycleEngine().run(
            AdaptiveCycleRequest(
                cycle_id="C2",
                objective="improve task quality",
                incumbent=incumbent,
                candidate=candidate,
                effort=effort(),
            )
        )
        self.assertEqual(result.outcome, CycleOutcome.PROMOTE_INCREMENTAL)
        self.assertTrue(result.promote)
        self.assertFalse(result.target_met)
        self.assertEqual(result.claim_state, "MEASURED_IMPROVEMENT_NOT_2X")

    def test_regression_is_not_promoted(self):
        incumbent = PerformanceVector(quality=5, reliability=5, proof=5)
        candidate = PerformanceVector(quality=2, reliability=2, proof=2)
        result = AdaptiveCycleEngine().run(
            AdaptiveCycleRequest(
                cycle_id="C3",
                objective="improve task quality",
                incumbent=incumbent,
                candidate=candidate,
                effort=effort(),
            )
        )
        self.assertEqual(result.outcome, CycleOutcome.HOLD_NO_GAIN)
        self.assertFalse(result.promote)

    def test_failed_invariant_overrides_high_score(self):
        result = AdaptiveCycleEngine().run(
            AdaptiveCycleRequest(
                cycle_id="C4",
                objective="improve safely",
                incumbent=PerformanceVector(quality=1),
                candidate=PerformanceVector(quality=10),
                effort=effort(),
                invariant_checks=(("privacy", False),),
            )
        )
        self.assertEqual(result.outcome, CycleOutcome.REJECT_INVARIANT)
        self.assertFalse(result.promote)
        self.assertEqual(result.failed_invariants, ("privacy",))

    def test_best_effort_requires_route_and_self_test(self):
        assessment = BestEffortGovernor().assess(
            objective="task",
            effort=EffortRecord(),
        )
        self.assertFalse(assessment.complete)
        self.assertIn("NO_EXECUTION_ROUTE_ATTEMPTED", assessment.issues)
        self.assertIn("SELF_TEST_MISSING", assessment.issues)

    def test_owner_only_gate_can_complete_prework(self):
        assessment = BestEffortGovernor().assess(
            objective="task",
            effort=EffortRecord(
                attempted_routes=("safe-prework",),
                self_tests=(("prework", True),),
                critical_blockers=("PROVIDER_OWNER_GATE",),
                owner_only_gates=("PROVIDER_OWNER_GATE",),
                prework_complete=True,
            ),
        )
        self.assertTrue(assessment.complete)
        self.assertEqual(assessment.status, "BEST_EFFORT_AT_OWNER_GATE")

    def test_compactor_deduplicates_and_respects_budget(self):
        compactor = ContextCompactor(
            CompactionPolicy(max_active_atoms=2, max_active_chars=180, max_atom_chars=120)
        )
        atoms = (
            ContextAtom("objective", "Complete the task with proof.", "OBJECTIVE", pinned=True),
            ContextAtom("fact-1", "Verified fact alpha beta gamma delta epsilon zeta eta theta.", "VERIFIED_FACT", proof_refs=("P1",)),
            ContextAtom("fact-2", "Verified fact alpha beta gamma delta epsilon zeta eta theta.", "VERIFIED_FACT", proof_refs=("P2",)),
            ContextAtom("reference", "x" * 500, "REFERENCE"),
        )
        result = compactor.compact(atoms)
        self.assertEqual(result.before_atoms, 4)
        self.assertLessEqual(len(result.active_atoms), 2)
        self.assertTrue(any(group["canonical_atom_id"] == "fact-1" for group in result.duplicate_groups))
        canonical = next(atom for atom in result.active_atoms if atom.atom_id == "fact-1")
        self.assertEqual(canonical.proof_refs, ("P1", "P2"))
        self.assertTrue(any(item["reason"] == "WORKING_SET_BUDGET" for item in result.archive_manifest))

    def test_pinned_atom_survives_even_when_budget_overflows(self):
        result = ContextCompactor(
            CompactionPolicy(max_active_atoms=1, max_active_chars=40, max_atom_chars=30)
        ).compact(
            (
                ContextAtom("objective", "A" * 200, "OBJECTIVE", pinned=True),
                ContextAtom("decision", "B" * 200, "DECISION", pinned=True),
            )
        )
        self.assertEqual(len(result.active_atoms), 2)
        self.assertTrue(result.budget_overflow)
        self.assertTrue(all(atom.compacted for atom in result.active_atoms))

    def test_restructuring_prefers_merge_and_extraction(self):
        actions = CodeRestructuringPlanner().plan(
            (
                CodeUnit(
                    component_id="monolith",
                    lines_of_code=1200,
                    complexity=40,
                    duplication_ratio=0.85,
                    change_frequency=0.8,
                    test_confidence=0.2,
                    context_weight=0.9,
                    unique_function=False,
                ),
            )
        )
        names = {action.action for action in actions}
        self.assertIn("MERGE_DUPLICATE_IMPLEMENTATIONS", names)
        self.assertIn("EXTRACT_STABLE_MODULE_BOUNDARIES", names)
        self.assertIn("SPLIT_BY_RESPONSIBILITY", names)
        self.assertIn("ADD_CHARACTERIZATION_TESTS_BEFORE_REBUILD", names)

    def test_delta_memory_is_bounded_and_tamper_evident(self):
        memory = BoundedDeltaMemory(max_records=2, max_delta_characters=128)
        memory.commit({"cycle": 1, "state": {"a": 1}})
        memory.commit({"cycle": 2, "state": {"a": 2}})
        memory.commit({"cycle": 3, "state": {"a": 3}})
        snapshot = memory.snapshot()
        self.assertEqual(snapshot["retained_records"], 2)
        self.assertNotEqual(snapshot["checkpoint_hash"], "GENESIS")
        self.assertTrue(snapshot["verified"])
        memory._records[0]["delta"] = {"tampered": True}
        self.assertFalse(memory.verify())

    def test_learning_ledger_compacts_to_checkpoint(self):
        ledger = LearningLedger(max_records=2)
        ledger.append(LearningEvent("C1", "one", "DONE", "one"))
        ledger.append(LearningEvent("C2", "two", "DONE", "two"))
        ledger.append(LearningEvent("C3", "three", "DONE", "three"))
        self.assertEqual(len(ledger.records), 2)
        self.assertNotEqual(ledger.checkpoint_hash, "GENESIS")
        self.assertEqual(ledger.total_appended, 3)
        self.assertTrue(ledger.verify())


if __name__ == "__main__":
    unittest.main()
