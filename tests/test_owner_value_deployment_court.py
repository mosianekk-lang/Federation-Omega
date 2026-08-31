from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evidenceops.caseforge.owner_value_deployment_court import evaluate_proof_court

HEAD = "85cc814de482eadec84d9aac5f33eccda2fb8cad"


def candidate() -> dict[str, object]:
    return {"status":"CANDIDATE_EMPIRICAL_GATE_ASSURED_NO_PROMOTION","provider_disabled":True,"external_effect":False,
            "candidate_manifest":{"candidate_id":"sl-candidate-test","source_head_sha":HEAD,"observed_pair_count":30,"empirical_gate_satisfied":True,"stable_promotion_authorized":False},
            "assurance":{"decision":"EMPIRICAL_GATE_SATISFIED_NO_PROMOTION"}}


def owner_pair(index: int, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {"pair_id":f"owner-{index}","mission_class":"CURRENT_STATE_READ","source_head_sha":HEAD,"evidence_mode":"OBSERVED_OWNER_VALUE",
        "baseline_owner_minutes":10,"candidate_owner_minutes":5,"baseline_owner_interventions":2,"candidate_owner_interventions":1,
        "baseline_verified_output_ratio":0.9,"candidate_verified_output_ratio":1.0,"baseline_elapsed_seconds":100,"candidate_elapsed_seconds":50,
        "independent_readback":True,"proof_refs":[f"baseline:{index}",f"candidate:{index}"]}
    value.update(changes); return value


def internal_runtime(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {"evidence_id":"runtime-1","source_head_sha":HEAD,"evidence_mode":"INTERNAL_RUNTIME_QUALIFICATION","environment":"ci-container",
        "image_digest":"sha256:"+"a"*64,"revision_id":"","provider_registration_verified":False,"workload_identity_verified":False,
        "health_readback_verified":True,"rollback_verified":True,"deployment_observed":False,"independent_readback":True,
        "provider_effect_authorized":False,"proof_refs":["health:1","rollback:1"]}
    value.update(changes); return value


def live_deployment(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {"evidence_id":"deploy-1","source_head_sha":HEAD,"evidence_mode":"LIVE_PROVIDER_DEPLOYMENT","environment":"bounded-canary",
        "image_digest":"sha256:"+"b"*64,"revision_id":"revision-1","provider_registration_verified":True,"workload_identity_verified":True,
        "health_readback_verified":True,"rollback_verified":True,"deployment_observed":True,"independent_readback":True,
        "provider_effect_authorized":True,"proof_refs":["provider:registration","runtime:health","runtime:rollback"]}
    value.update(changes); return value


class OwnerValueDeploymentCourtTests(unittest.TestCase):
    def test_exact_candidate_without_new_evidence_holds(self) -> None:
        receipt=evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD)
        self.assertEqual("HOLD_NO_PROMOTION",receipt.decision); self.assertFalse(receipt.owner_value_proven); self.assertFalse(receipt.provider_deployment_proven)
        self.assertFalse(receipt.stable_promotion_authorized); self.assertFalse(receipt.external_effect)

    def test_internal_runtime_never_counts_as_provider_deployment(self) -> None:
        receipt=evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD,owner_value_observations=[owner_pair(i) for i in range(5)],runtime_or_deployment_evidence=[internal_runtime()])
        self.assertTrue(receipt.internal_runtime_qualified); self.assertFalse(receipt.provider_deployment_proven)
        self.assertIn("LIVE_PROVIDER_DEPLOYMENT_EVIDENCE_REQUIRED",receipt.blockers)

    def test_hosted_shadow_cannot_count_as_owner_value(self) -> None:
        receipt=evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD,owner_value_observations=[owner_pair(i,evidence_mode="HOSTED_SHADOW") for i in range(5)])
        self.assertFalse(receipt.owner_value_proven); self.assertIn("OWNER_VALUE_EVIDENCE_MODE_INVALID",receipt.blockers)

    def test_owner_value_regression_holds(self) -> None:
        observations=[owner_pair(i) for i in range(5)]; observations[0]=owner_pair(0,candidate_owner_minutes=11)
        receipt=evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD,owner_value_observations=observations)
        self.assertFalse(receipt.owner_value_proven); self.assertIn("OWNER_VALUE_MINUTES_NOT_IMPROVED",receipt.blockers)

    def test_complete_typed_evidence_reaches_review_but_never_promotes(self) -> None:
        receipt=evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD,owner_value_observations=[owner_pair(i) for i in range(5)],runtime_or_deployment_evidence=[internal_runtime(),live_deployment()])
        self.assertEqual("OWNER_VALUE_AND_DEPLOYMENT_PROOF_SATISFIED_PROMOTION_REVIEW_REQUIRED",receipt.decision)
        self.assertTrue(receipt.owner_value_proven); self.assertTrue(receipt.internal_runtime_qualified); self.assertTrue(receipt.provider_deployment_proven)
        self.assertFalse(receipt.stable_promotion_authorized); self.assertFalse(receipt.effect_authorized)

    def test_source_mismatch_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError,"SOURCE_HEAD_MISMATCH"): evaluate_proof_court(candidate_receipt=candidate(),source_head_sha="1"*40)

    def test_candidate_with_promotion_enabled_rejected(self) -> None:
        value=deepcopy(candidate()); value["candidate_manifest"]["stable_promotion_authorized"]=True
        with self.assertRaisesRegex(ValueError,"PROMOTION_MUST_BE_FALSE"): evaluate_proof_court(candidate_receipt=value,source_head_sha=HEAD)

    def test_receipt_is_deterministic(self) -> None:
        self.assertEqual(evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD).receipt_sha256,evaluate_proof_court(candidate_receipt=candidate(),source_head_sha=HEAD).receipt_sha256)

    def test_cli_writes_hold_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root=Path(temp_dir); candidate_path=root/"candidate.json"; output=root/"court.json"; candidate_path.write_text(json.dumps(candidate()))
            result=subprocess.run([sys.executable,"-m","evidenceops.caseforge.owner_value_deployment_court","--candidate-receipt",str(candidate_path),"--source-head-sha",HEAD,"--output",str(output)],text=True,capture_output=True,check=False)
            self.assertEqual(0,result.returncode,msg=result.stderr); self.assertEqual("HOLD_NO_PROMOTION",json.loads(output.read_text())["decision"])


if __name__ == "__main__": unittest.main()
