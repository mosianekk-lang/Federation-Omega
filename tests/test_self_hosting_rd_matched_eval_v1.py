from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import unittest

from federation.self_hosting_rd_matched_eval_v1 import (
    EngineeringObservation,
    MatchedPair,
    evaluate_matched_cohort,
)

ROOT=Path(__file__).resolve().parents[1]
GOV=json.loads((ROOT/"governance/self_hosting_rd_matched_eval_v1.json").read_text(encoding="utf-8"))
INC="1"*40
CHA="2"*40


def dig(text: str) -> str:
    return "sha256:"+sha256(text.encode()).hexdigest()


def obs(arm: str, i: int, state: str, *, env: str | None = None, regress: str | None = None) -> EngineeringObservation:
    metrics={
        "verified_output_ratio":1.0,
        "elapsed_seconds":10.0 if arm=="INCUMBENT" else 8.0,
        "tool_calls":10.0 if arm=="INCUMBENT" else 8.0,
        "owner_interventions":1.0 if arm=="INCUMBENT" else 0.0,
        "unintended_writes":0.0,
        "safety_regressions":0.0,
        "external_runtime_dependencies":1.0 if arm=="INCUMBENT" else 0.0,
        "reproducibility_ratio":1.0,
        "rollback_success_ratio":1.0,
    }
    if regress=="quality" and arm=="CHALLENGER":
        metrics["verified_output_ratio"]=0.8
    if regress=="owner" and arm=="CHALLENGER":
        metrics["owner_interventions"]=2.0
    prefix="inc" if arm=="INCUMBENT" else "cha"
    return EngineeringObservation(
        arm=arm,pair_id=f"P{i:02d}",mission_class="BOUNDED_ENGINEERING",
        task_signature=dig(f"task-{i}"),oracle_id="ORACLE-V1",
        input_digest=dig(f"input-{i}"),environment_digest=env or dig("env-v1"),
        source_head_sha=INC if arm=="INCUMBENT" else CHA,
        evidence_state=state,
        metrics=metrics,
        proof_refs=(f"proof:{prefix}:{i}:a",f"proof:{prefix}:{i}:b"),
    )


def pairs(state: str, n: int=12, regress: str | None=None) -> tuple[MatchedPair,...]:
    return tuple(MatchedPair(obs("INCUMBENT",i,state),obs("CHALLENGER",i,state,regress=regress)) for i in range(n))


class SelfHostingRDMatchedEvalV1Tests(unittest.TestCase):
    def test_deterministic_ci_matching_does_not_manufacture_operational_proof(self):
        r=evaluate_matched_cohort(
            candidate_id="C1",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=pairs("DETERMINISTIC_CI_BOUNDED_RUNTIME"),cfbe_spec=GOV["cfbe_spec"])
        self.assertTrue(r.matched_conditions_pass)
        self.assertTrue(r.quality_nonnegative)
        self.assertEqual(r.operational_pair_count,0)
        self.assertFalse(r.matched_eval_proven)
        self.assertEqual(r.decision,"HOLD_NO_OPERATIONAL_MATCHED_EVIDENCE")
        self.assertFalse(r.promotion_authorized)

    def test_operational_matched_cohort_can_prove_matched_eval_only(self):
        r=evaluate_matched_cohort(
            candidate_id="C2",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=pairs("REPEATED_OPERATIONAL_SCOPED"),cfbe_spec=GOV["cfbe_spec"])
        self.assertEqual(r.matched_pair_count,12)
        self.assertEqual(r.operational_pair_count,12)
        self.assertTrue(r.quality_nonnegative)
        self.assertTrue(r.matched_eval_proven)
        self.assertFalse(r.owner_value_proven)
        self.assertFalse(r.independent_judge_ack)
        self.assertFalse(r.promotion_authorized)
        self.assertEqual(r.decision,"MATCHED_EVAL_PROVEN__OWNER_VALUE_AND_JUDGE_OPEN")

    def test_environment_mismatch_holds_cohort(self):
        ps=list(pairs("REPEATED_OPERATIONAL_SCOPED"))
        i=ps[0].incumbent
        ps[0]=MatchedPair(i,obs("CHALLENGER",0,"REPEATED_OPERATIONAL_SCOPED",env=dig("different-env")))
        r=evaluate_matched_cohort(
            candidate_id="C3",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=tuple(ps),cfbe_spec=GOV["cfbe_spec"])
        self.assertFalse(r.matched_conditions_pass)
        self.assertFalse(r.matched_eval_proven)
        self.assertIn("MATCHED_EVAL_ENVIRONMENT_MISMATCH",r.blockers)

    def test_quality_regression_hard_blocks(self):
        r=evaluate_matched_cohort(
            candidate_id="C4",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=pairs("REPEATED_OPERATIONAL_SCOPED",regress="quality"),cfbe_spec=GOV["cfbe_spec"])
        self.assertFalse(r.quality_nonnegative)
        self.assertFalse(r.matched_eval_proven)
        self.assertEqual(r.decision,"HOLD_QUALITY_OR_SAFETY_REGRESSION")

    def test_owner_intervention_regression_hard_blocks(self):
        r=evaluate_matched_cohort(
            candidate_id="C5",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=pairs("REPEATED_OPERATIONAL_SCOPED",regress="owner"),cfbe_spec=GOV["cfbe_spec"])
        self.assertFalse(r.quality_nonnegative)
        self.assertFalse(r.matched_eval_proven)

    def test_insufficient_pairs_hold_even_if_operational(self):
        r=evaluate_matched_cohort(
            candidate_id="C6",incumbent_source_head=INC,challenger_source_head=CHA,
            pairs=pairs("REPEATED_OPERATIONAL_SCOPED",n=11),cfbe_spec=GOV["cfbe_spec"])
        self.assertFalse(r.matched_eval_proven)
        self.assertEqual(r.decision,"HOLD_INSUFFICIENT_MATCHED_PAIRS")

    def test_duplicate_pair_ids_fail_closed(self):
        ps=list(pairs("DETERMINISTIC_CI_BOUNDED_RUNTIME",n=2))
        ps.append(ps[0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PAIR_ID"):
            evaluate_matched_cohort(
                candidate_id="C7",incumbent_source_head=INC,challenger_source_head=CHA,
                pairs=tuple(ps),cfbe_spec=GOV["cfbe_spec"],minimum_matched_pairs=2,minimum_real_pairs_for_promotion=2)

    def test_source_mismatch_is_not_matched(self):
        p=pairs("REPEATED_OPERATIONAL_SCOPED",n=1)[0]
        r=evaluate_matched_cohort(
            candidate_id="C8",incumbent_source_head="3"*40,challenger_source_head=CHA,
            pairs=(p,),cfbe_spec=GOV["cfbe_spec"],minimum_matched_pairs=1,minimum_real_pairs_for_promotion=1)
        self.assertFalse(r.matched_conditions_pass)
        self.assertIn("MATCHED_EVAL_INCUMBENT_SOURCE_MISMATCH",r.blockers)

    def test_governance_keeps_value_and_promotion_separate(self):
        self.assertEqual(GOV["minimum_matched_pairs"],12)
        self.assertEqual(GOV["minimum_real_pairs_for_promotion"],20)
        m=GOV["maturity_boundary"]
        self.assertFalse(m["deterministic_ci_can_prove_matched_eval"])
        self.assertFalse(m["matched_eval_proves_owner_value"])
        self.assertFalse(m["matched_eval_proves_judge_ack"])
        self.assertFalse(m["matched_eval_authorizes_promotion"])

if __name__=="__main__":
    unittest.main()
