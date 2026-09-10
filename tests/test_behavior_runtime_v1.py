import math
import unittest
from federation.behavior_runtime_v1 import (
    BehaviorBundle, BehaviorRegistry, ExperimentEvidence, ExperimentRouter,
    ErrorBudget, SemanticDoneContract,
)


def sealed(bundle_id="B1", parent_id="", rollback_ref="r0", **genes):
    return BehaviorBundle(bundle_id, parent_id, genes or {"ROUTE":"A"}, rollback_ref=rollback_ref).seal()


def evidence(bundle_id, score=0.5, **overrides):
    data = dict(
        bundle_id=bundle_id, cohort_hash="cohort", holdout_hash="holdout", sample_count=30,
        correctness=1.0, proof_completeness=1.0, owner_burden=0.0, recovery=1.0,
        utility_score=score, regression_green=True, shadow_complete=True, canary_complete=True,
        evidence_refs=("proof:1",),
    )
    data.update(overrides)
    return ExperimentEvidence(**data)


class BehaviorRuntimeTests(unittest.TestCase):
    def test_bundle_is_content_addressed(self):
        b = sealed(); self.assertTrue(b.verify()); self.assertEqual(len(b.content_sha256), 64)

    def test_protected_invariant_regression_is_rejected(self):
        b = BehaviorBundle("B", "", {"x":"y"}, protected_invariants=frozenset({"OWNER_AUTHORITY"}), rollback_ref="r")
        with self.assertRaises(ValueError): b.seal()

    def test_unknown_parent_is_rejected(self):
        reg = BehaviorRegistry(sealed("B1"))
        with self.assertRaises(ValueError): reg.register(sealed("B2", parent_id="MISSING"))

    def test_candidate_cannot_promote_without_matched_holdout(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        self.assertEqual(reg.promote("B2", evidence("B1"), evidence("B2", .8, holdout_hash="other")).state, "RETAIN")

    def test_candidate_cannot_promote_with_mismatched_sample_count(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        d = reg.promote("B2", evidence("B1", sample_count=30), evidence("B2", .8, sample_count=29))
        self.assertEqual(d.reason, "UNMATCHED_COHORT_HOLDOUT_OR_SAMPLE_COUNT")

    def test_candidate_cannot_promote_without_shadow_and_canary(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        self.assertEqual(reg.promote("B2", evidence("B1"), evidence("B2", .8, shadow_complete=False)).state, "RETAIN")

    def test_owner_burden_regression_veto(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        self.assertEqual(reg.promote("B2", evidence("B1", .5), evidence("B2", .9, owner_burden=.1)).reason, "OWNER_BURDEN_OR_RECOVERY_REGRESSION")

    def test_recovery_regression_veto(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        self.assertEqual(reg.promote("B2", evidence("B1", .5), evidence("B2", .9, recovery=.9)).reason, "OWNER_BURDEN_OR_RECOVERY_REGRESSION")

    def test_rollback_required_for_promotion(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", ""))
        self.assertEqual(reg.promote("B2", evidence("B1", .5), evidence("B2", .9)).reason, "ROLLBACK_REQUIRED")

    def test_hard_regression_veto_beats_score(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        self.assertEqual(reg.promote("B2", evidence("B1"), evidence("B2", .95, correctness=.99)).reason, "CORRECTNESS_OR_PROOF_REGRESSION")

    def test_green_matched_gain_with_rollback_promotes(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        d = reg.promote("B2", evidence("B1", .5), evidence("B2", .8))
        self.assertEqual((d.state, reg.champion.bundle_id), ("PROMOTE", "B2"))

    def test_nonfinite_utility_rejected(self):
        for score in (math.nan, math.inf, -math.inf):
            with self.subTest(score=score):
                with self.assertRaises(ValueError): evidence("B1", score).validate()

    def test_negative_minimum_delta_rejected(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        with self.assertRaises(ValueError): reg.promote("B2", evidence("B1", .8), evidence("B2", .7), minimum_utility_delta=-.2)

    def test_nonfinite_minimum_delta_rejected(self):
        reg = BehaviorRegistry(sealed("B1")); reg.register(sealed("B2", "B1", "B1"))
        with self.assertRaises(ValueError): reg.promote("B2", evidence("B1", .5), evidence("B2", .9), minimum_utility_delta=math.nan)

    def test_blank_evidence_ref_rejected(self):
        with self.assertRaises(ValueError): evidence("B1", evidence_refs=("   ",)).validate()

    def test_experiment_assignment_is_deterministic(self):
        a = ExperimentRouter.assign("subject", "exp", 2500)
        self.assertEqual(a, ExperimentRouter.assign("subject", "exp", 2500)); self.assertIn(a, {"CHAMPION", "CHALLENGER"})

    def test_error_budget_fails_closed(self):
        self.assertTrue(ErrorBudget().allows_autonomy())
        self.assertFalse(ErrorBudget(unauthorized_actions=1).allows_autonomy())
        self.assertFalse(ErrorBudget(critical_regressions=1).allows_autonomy())
        self.assertFalse(ErrorBudget(failed_recoveries=1).allows_autonomy())

    def test_negative_error_budget_values_fail_closed(self):
        cases = [
            ErrorBudget(unauthorized_actions=-1), ErrorBudget(critical_regressions=-1),
            ErrorBudget(failed_recoveries=-1), ErrorBudget(owner_interventions=-1),
            ErrorBudget(max_failed_recoveries=-1), ErrorBudget(max_owner_interventions=-1),
        ]
        for b in cases:
            with self.subTest(budget=b): self.assertFalse(b.allows_autonomy())

    def test_semantic_done_requires_true_predicate_and_nonblank_proof(self):
        contract = SemanticDoneContract(("DEPLOYED","READBACK"), {"DEPLOYED":"p1","READBACK":"p2"})
        self.assertEqual(contract.evaluate({"DEPLOYED":True,"READBACK":True}), (True, ()))
        self.assertEqual(contract.evaluate({"DEPLOYED":True,"READBACK":False}), (False, ("READBACK",)))
        self.assertEqual(SemanticDoneContract(("DEPLOYED",), {}).evaluate({"DEPLOYED":True}), (False, ("DEPLOYED",)))
        self.assertEqual(SemanticDoneContract(("DEPLOYED",), {"DEPLOYED":"  "}).evaluate({"DEPLOYED":True}), (False, ("DEPLOYED",)))


if __name__ == "__main__": unittest.main()
