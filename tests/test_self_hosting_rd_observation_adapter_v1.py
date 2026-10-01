from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import unittest

from benchmarking.cfbe_omega.value_foundry_v1 import (
    EVIDENCE_SCHEMA,
    canonical_hash,
    record_hash,
)
from federation.self_hosting_rd_observation_adapter_v1 import (
    bind_compiled_mission,
    compile_collected_matched_pair,
    compile_measured_observation,
    compile_real_mission_directive,
    ingest_compiled_observation,
    initialize_prospective_programme,
)

ROOT=Path(__file__).resolve().parents[1]
HEAD="e84281149c326bee60f637ed638d9bc01d72a673"
INC="1"*40
CHA="2"*40
VERIFIER="realityguard:self-hosting-rd-independent-readback-v1"


def dig(text: str) -> str:
    return "sha256:"+sha256(text.encode()).hexdigest()


def evidence_receipt(reference: str, subject: str, source_head: str, raw: dict[str, object]) -> dict[str, object]:
    unsigned={
        "schema":EVIDENCE_SCHEMA,
        "evidence_id":reference,
        "subject":subject,
        "evidence_class":"INDEPENDENT_SEMANTIC_READBACK",
        "source_head_sha":source_head,
        "record_sha256":record_hash(raw),
        "payload_sha256":canonical_hash({"semantic":"verified","reference":reference}),
        "verifier_id":VERIFIER,
        "verified_at":"2026-09-19T00:00:00Z",
        "independent_readback":True,
        "status":"VERIFIED",
    }
    return {**unsigned,"receipt_sha256":canonical_hash(unsigned)}


def mission(task_class: str) -> dict[str, object]:
    return {
        "mission_id":"mission-real-001",
        "task_class":task_class,
        "source_head_sha":HEAD,
        "observed_at":"2026-09-19T00:01:00Z",
        "real_mission":True,
        "synthetic":False,
        "shadow":False,
        "replayed":False,
        "proof_refs":["proof:mission:001"],
        "task_signature":"self-hosting-task-v1",
        "input_digest":dig("input"),
        "environment_digest":dig("environment"),
        "owner_goal_digest":dig("owner-goal"),
    }


def measurement(arm: str, binding, *, state: str="REPEATED_OPERATIONAL_SCOPED") -> dict[str, object]:
    challenger=arm=="CHALLENGER"
    return {
        "arm":arm,
        "arm_source_head_sha":CHA if challenger else INC,
        "observed_at":"2026-09-19T00:02:00Z" if not challenger else "2026-09-19T00:03:00Z",
        "real_observation":True,
        "synthetic":False,
        "shadow":False,
        "replayed":False,
        "task_signature":"self-hosting-task-v1",
        "input_digest":dig("input"),
        "environment_digest":dig("environment"),
        "accepted":True,
        "verified_output_ratio":1.0,
        "owner_intervention_seconds":600.0 if not challenger else 300.0,
        "owner_intervention_count":2 if not challenger else 1,
        "clarification_count":1 if not challenger else 0,
        "correction_count":1 if not challenger else 0,
        "elapsed_seconds":20.0 if not challenger else 15.0,
        "independent_readback":True,
        "proof_refs":[f"proof:{arm.lower()}:001"],
        "engineering_evidence_state":state,
        "tool_calls":10.0 if not challenger else 8.0,
        "unintended_writes":0.0,
        "safety_regressions":0.0,
        "external_runtime_dependencies":1.0 if not challenger else 0.0,
        "reproducibility_ratio":1.0,
        "rollback_success_ratio":1.0,
    }


class SelfHostingRDObservationAdapterV1Tests(unittest.TestCase):
    def _bound(self):
        programme=initialize_prospective_programme(source_head_sha=HEAD,registered_at="2026-09-19T00:00:00Z")
        manifest=programme.cohort_manifests[0]
        state=programme.collector_states[0]
        task_class=manifest["slots"][0]["task_class"]
        event=compile_real_mission_directive(mission(task_class))
        ref=event["proof_refs"][0]
        registry={ref:evidence_receipt(ref,f"directive:{event['directive_id']}",HEAD,event)}
        state,receipt=bind_compiled_mission(
            state,manifest,event,evidence_registry=registry,trusted_verifiers=(VERIFIER,))
        self.assertFalse(receipt.pair_ready)
        return programme,manifest,state,registry,state.bindings[0]

    def test_programme_opens_twenty_real_only_slots_without_effect(self):
        p=initialize_prospective_programme(source_head_sha=HEAD,registered_at="2026-09-19T00:00:00Z")
        self.assertEqual(len(p.cohort_manifests),2)
        self.assertEqual(p.total_slots,20)
        self.assertEqual(sum(len(x["slots"]) for x in p.cohort_manifests),20)
        self.assertFalse(p.owner_value_proven)
        self.assertFalse(p.matched_eval_proven)
        self.assertFalse(p.provider_effect_authorized)
        self.assertFalse(p.external_effect)
        for manifest in p.cohort_manifests:
            self.assertTrue(all(x["real_observation_required"] for x in manifest["slots"]))
            self.assertTrue(all(not x["synthetic_observation_allowed"] for x in manifest["slots"]))

    def test_synthetic_mission_is_rejected_before_collector(self):
        p=initialize_prospective_programme(source_head_sha=HEAD,registered_at="2026-09-19T00:00:00Z")
        item=mission(p.cohort_manifests[0]["slots"][0]["task_class"])
        item["synthetic"]=True
        with self.assertRaisesRegex(ValueError,"SYNTHETIC_MISSION_PROHIBITED"):
            compile_real_mission_directive(item)

    def test_two_trusted_real_observations_compile_to_arm_specific_matched_pair(self):
        _,manifest,state,registry,binding=self._bound()
        for arm in ("INCUMBENT","CHALLENGER"):
            event=compile_measured_observation(binding,measurement(arm,binding))
            ref=event["proof_refs"][0]
            registry[ref]=evidence_receipt(ref,f"owner-value:{event['observation_id']}",HEAD,event)
            state,receipt=ingest_compiled_observation(
                state,event,evidence_registry=registry,trusted_verifiers=(VERIFIER,))
        self.assertTrue(receipt.pair_ready)
        pair=compile_collected_matched_pair(state,binding.pair_id)
        self.assertEqual(pair.incumbent.source_head_sha,INC)
        self.assertEqual(pair.challenger.source_head_sha,CHA)
        self.assertEqual(pair.incumbent.input_digest,pair.challenger.input_digest)
        self.assertEqual(pair.incumbent.environment_digest,pair.challenger.environment_digest)
        self.assertEqual(pair.incumbent.metrics["tool_calls"],10.0)
        self.assertEqual(pair.challenger.metrics["tool_calls"],8.0)
        self.assertTrue(pair.operational_and_independent)

    def test_ci_evidence_can_be_collected_but_does_not_become_operational_pair(self):
        _,manifest,state,registry,binding=self._bound()
        for arm in ("INCUMBENT","CHALLENGER"):
            event=compile_measured_observation(
                binding,measurement(arm,binding,state="DETERMINISTIC_CI_BOUNDED_RUNTIME"))
            ref=event["proof_refs"][0]
            registry[ref]=evidence_receipt(ref,f"owner-value:{event['observation_id']}",HEAD,event)
            state,_=ingest_compiled_observation(
                state,event,evidence_registry=registry,trusted_verifiers=(VERIFIER,))
        pair=compile_collected_matched_pair(state,binding.pair_id)
        self.assertFalse(pair.operational_and_independent)

    def test_shadow_observation_is_rejected(self):
        _,_,_,_,binding=self._bound()
        item=measurement("INCUMBENT",binding)
        item["shadow"]=True
        with self.assertRaisesRegex(ValueError,"SHADOW_OBSERVATION_PROHIBITED"):
            compile_measured_observation(binding,item)

    def test_arm_source_identity_is_required_and_separate_from_collector_epoch(self):
        _,_,_,_,binding=self._bound()
        item=measurement("INCUMBENT",binding)
        item["arm_source_head_sha"]="not-a-sha"
        with self.assertRaisesRegex(ValueError,"ARM_SOURCE_HEAD_INVALID"):
            compile_measured_observation(binding,item)
        good=compile_measured_observation(binding,measurement("INCUMBENT",binding))
        self.assertEqual(good["source_head_sha"],HEAD)
        self.assertEqual(good["arm_source_head_sha"],INC)

    def test_missing_engineering_metric_fails_closed(self):
        _,_,_,_,binding=self._bound()
        item=measurement("CHALLENGER",binding)
        item.pop("rollback_success_ratio")
        with self.assertRaisesRegex(ValueError,"SHRD_ENGINEERING_METRIC_INVALID"):
            compile_measured_observation(binding,item)

    def test_governance_declares_reuse_and_no_watcher_or_promotion(self):
        g=json.loads((ROOT/"governance/self_hosting_rd_observation_adapter_v1.json").read_text())
        self.assertIn("CFBE-PASSIVE-OBSERVATION-COLLECTOR-V1",g["reuse"])
        self.assertEqual(g["cohorts"]["total_prospective_capacity"],20)
        self.assertFalse(g["effects"]["watcher_created"])
        self.assertFalse(g["effects"]["scheduler_created"])
        self.assertFalse(g["effects"]["provider_effect_authorized"])
        self.assertFalse(g["effects"]["stable_promotion_allowed"])
        self.assertTrue(g["maturity_boundary"]["source_adapter_is_not_deployed_collector"])

if __name__=="__main__":
    unittest.main()
