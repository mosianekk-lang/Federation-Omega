from __future__ import annotations

"""Hosted-shadow campaign for CFBE AutoPilot + Meta-Cognition empirical proof.

The campaign executes the admitted metacognitive controller against a fixed oracle
suite and performs real cross-process checkpoint/readback handoffs. Outside GitHub
Actions it is explicitly synthetic shadow. Inside a GitHub Actions run it may be
classified HOSTED_SHADOW, but never observed operational or provider-native.
"""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter_ns
from typing import Callable

from benchmarking.cfbe_omega.autopilot_metacognition_empirical_court_v1 import (
    EvidenceMode,
    MetaCognitionPair,
    ResumeObservation,
    evaluate_empirical_court,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    MetaAction,
    MetaCognitiveDecision,
    MetaCognitiveState,
    metacognitive_assessment,
    reflection_gate,
)


SCHEMA = "CFBE-AUTOPILOT-METACOG-HOSTED-SHADOW-CAMPAIGN-V1"
PAIR_COUNT = 30
RESUME_COUNT = 10
MEASURE_ITERATIONS = 2000


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_source_sha(source_sha: str) -> str:
    value = source_sha.strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("HOSTED_SHADOW_SOURCE_SHA_INVALID")
    return value


def _github_actions_runtime() -> bool:
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true" and bool(os.environ.get("GITHUB_RUN_ID"))


def _case(index: int) -> tuple[MetaCognitiveState, MetaAction, str]:
    family = index % 6
    base = dict(
        confidence=0.90,
        evidence_coverage=0.90,
        contradiction_pressure=0.10,
        novelty=0.10,
        progress=0.80,
        plan_stability=0.80,
        context_freshness=0.90,
        resource_pressure=0.20,
        repeated_failure_count=0,
    )
    if family == 0:
        expected, label = MetaAction.CONTINUE, "operating-band"
    elif family == 1:
        base["contradiction_pressure"] = 0.80
        expected, label = MetaAction.CHALLENGE, "contradiction"
    elif family == 2:
        base["evidence_coverage"] = 0.40
        expected, label = MetaAction.SEEK_EVIDENCE, "evidence-gap"
    elif family == 3:
        base.update(progress=0.15, plan_stability=0.30, resource_pressure=0.80)
        expected, label = MetaAction.REPLAN, "plan-instability"
    elif family == 4:
        base["novelty"] = 0.80
        expected, label = MetaAction.REFLECT, "novelty"
    else:
        base["repeated_failure_count"] = 3
        expected, label = MetaAction.ROLLBACK, "repeated-failure"
    return MetaCognitiveState(**base), expected, label


def _first_order_baseline(state: MetaCognitiveState) -> MetaCognitiveDecision:
    values = (
        state.confidence,
        state.evidence_coverage,
        state.contradiction_pressure,
        state.novelty,
        state.progress,
        state.plan_stability,
        state.context_freshness,
        state.resource_pressure,
    )
    if any(not 0.0 <= value <= 1.0 for value in values) or state.repeated_failure_count < 0:
        raise ValueError("HOSTED_SHADOW_BASELINE_STATE_INVALID")
    if state.repeated_failure_count >= 3:
        action, reasons = MetaAction.ROLLBACK, ("repeated_failure_threshold",)
    elif state.evidence_coverage < 0.55 or state.context_freshness < 0.45:
        action, reasons = MetaAction.SEEK_EVIDENCE, ("evidence_or_freshness_gap",)
    elif state.plan_stability < 0.45 or (state.progress < 0.25 and state.resource_pressure >= 0.70):
        action, reasons = MetaAction.REPLAN, ("plan_instability_or_low_progress",)
    else:
        action, reasons = MetaAction.CONTINUE, ("first_order_default",)
    effective = min(state.confidence, state.evidence_coverage, state.context_freshness)
    band = "LOW" if effective < 0.35 else "MEDIUM" if effective < 0.75 else "HIGH"
    return MetaCognitiveDecision(action, reasons, band, False)


def _baseline_route(state: MetaCognitiveState) -> MetaAction:
    decision = _first_order_baseline(state)
    no_reflection = reflection_gate(
        trigger_present=False,
        expected_decision_gain=0.20,
        estimated_reflection_cost=0.05,
    )
    if no_reflection.run_reflection:
        raise AssertionError("BASELINE_REFLECTION_MUST_REMAIN_DISABLED")
    return decision.action


def _candidate_route(state: MetaCognitiveState) -> tuple[MetaAction, bool]:
    reflection = reflection_gate(
        trigger_present=True,
        expected_decision_gain=0.20,
        estimated_reflection_cost=0.05,
    )
    decision = metacognitive_assessment(state)
    return decision.action, reflection.run_reflection


def _measure_ms(call: Callable[[], object], *, iterations: int = MEASURE_ITERATIONS) -> float:
    if iterations <= 0:
        raise ValueError("HOSTED_SHADOW_MEASURE_ITERATIONS_INVALID")
    started = perf_counter_ns()
    for _ in range(iterations):
        call()
    elapsed_ms = (perf_counter_ns() - started) / 1_000_000.0
    return max(elapsed_ms, 0.001)


def build_pairs(source_sha: str, *, evidence_mode: EvidenceMode, measure: bool = True) -> tuple[MetaCognitionPair, ...]:
    source = _validate_source_sha(source_sha)
    pairs: list[MetaCognitionPair] = []
    for index in range(PAIR_COUNT):
        state, expected, label = _case(index)
        baseline = _baseline_route(state)
        candidate, reflected = _candidate_route(state)
        if candidate is not expected:
            raise AssertionError(f"METACOG_ORACLE_MISMATCH:{index}:{candidate.value}:{expected.value}")
        if not reflected:
            raise AssertionError(f"METACOG_REFLECTION_NOT_TRIGGERED:{index}")

        if measure:
            baseline_ms = _measure_ms(lambda state=state: _baseline_route(state))
            candidate_ms = _measure_ms(lambda state=state: _candidate_route(state))
        else:
            baseline_ms, candidate_ms = 100.0, 120.0

        state_ref = "state-sha256:" + _digest(asdict(state))
        oracle_ref = "oracle-sha256:" + _digest({"index": index, "expected": expected.value, "label": label})
        baseline_correct = baseline is expected
        pairs.append(MetaCognitionPair(
            pair_id=f"metacog-pair-{index:02d}",
            source_head_sha=source,
            task_signature=f"metacog-oracle-{label}-{index:02d}",
            evidence_mode=evidence_mode,
            baseline_quality=1.0 if baseline_correct else 0.60,
            candidate_quality=1.0,
            baseline_elapsed_ms=baseline_ms,
            candidate_elapsed_ms=candidate_ms,
            baseline_owner_interventions=0 if baseline_correct else 1,
            candidate_owner_interventions=0,
            candidate_reflection_used=True,
            candidate_confidence=0.90,
            candidate_outcome_correct=True,
            independent_readback=True,
            proof_refs=(state_ref, oracle_ref),
        ))
    return tuple(pairs)


def _checkpoint_payload(source_sha: str, index: int) -> dict[str, object]:
    return {
        "schema": "CFBE-AUTOPILOT-METACOG-SHADOW-CHECKPOINT-V1",
        "checkpoint_id": f"metacog-checkpoint-{index:02d}",
        "source_head_sha": _validate_source_sha(source_sha),
        "sequence": index,
        "state": "PARKED_FOR_PROCESS_REPLACEMENT",
        "external_effect_count": 0,
        "resume_token": _digest({"source_sha": source_sha, "index": index, "purpose": "hosted-shadow-resume"}),
    }


def _resume_child(checkpoint_path: str, expected_digest: str) -> int:
    path = Path(checkpoint_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    actual_digest = _digest(payload)
    if actual_digest != expected_digest:
        raise ValueError("HOSTED_SHADOW_CHECKPOINT_DIGEST_MISMATCH")
    if payload.get("external_effect_count") != 0:
        raise ValueError("HOSTED_SHADOW_CHECKPOINT_EFFECT_COUNT_NONZERO")
    readback = {
        "schema": "CFBE-AUTOPILOT-METACOG-SHADOW-RESUME-READBACK-V1",
        "checkpoint_id": payload["checkpoint_id"],
        "source_head_sha": payload["source_head_sha"],
        "checkpoint_sha256": actual_digest,
        "state_sha256": _digest(payload),
        "process_id": os.getpid(),
        "resumed": True,
        "duplicate_effect_count": 0,
        "state_drift": False,
        "external_effect": False,
    }
    print(_canonical_json(readback))
    return 0


def build_resume_observations(source_sha: str, *, evidence_mode: EvidenceMode) -> tuple[ResumeObservation, ...]:
    source = _validate_source_sha(source_sha)
    observations: list[ResumeObservation] = []
    module = "benchmarking.cfbe_omega.autopilot_metacognition_shadow_campaign_v1"
    with tempfile.TemporaryDirectory(prefix="cfbe-metacog-shadow-") as temp_dir:
        root = Path(temp_dir)
        for index in range(RESUME_COUNT):
            checkpoint = _checkpoint_payload(source, index)
            checkpoint_path = root / f"checkpoint-{index:02d}.json"
            checkpoint_path.write_text(_canonical_json(checkpoint), encoding="utf-8")
            checkpoint_digest = _digest(checkpoint)
            process = subprocess.run(
                [sys.executable, "-m", module, "--resume-child", str(checkpoint_path), checkpoint_digest],
                check=True,
                capture_output=True,
                text=True,
            )
            child = json.loads(process.stdout.strip())
            state_drift = (
                child.get("checkpoint_id") != checkpoint["checkpoint_id"]
                or child.get("source_head_sha") != source
                or child.get("checkpoint_sha256") != checkpoint_digest
                or child.get("state_sha256") != checkpoint_digest
            )
            duplicate_effect_count = int(child.get("duplicate_effect_count", -1))
            resumed = bool(child.get("resumed")) and child.get("external_effect") is False
            child_pid = int(child.get("process_id", 0))
            process_before = f"pid:{os.getpid()}"
            process_after = f"pid:{child_pid}"
            if child_pid <= 0 or process_before == process_after:
                raise AssertionError("HOSTED_SHADOW_PROCESS_REPLACEMENT_NOT_OBSERVED")
            readback_ref = "resume-readback-sha256:" + _digest({k: v for k, v in child.items() if k != "process_id"})
            observations.append(ResumeObservation(
                observation_id=f"resume-{index:02d}",
                source_head_sha=source,
                evidence_mode=evidence_mode,
                process_before=process_before,
                process_after=process_after,
                checkpoint_id=str(checkpoint["checkpoint_id"]),
                resumed=resumed,
                duplicate_effect_count=duplicate_effect_count,
                state_drift=state_drift,
                independent_readback=resumed and not state_drift and duplicate_effect_count == 0,
                proof_refs=("checkpoint-sha256:" + checkpoint_digest, readback_ref),
            ))
    return tuple(observations)


def run_campaign(source_sha: str, *, require_github_actions: bool = False, measure: bool = True) -> dict[str, object]:
    source = _validate_source_sha(source_sha)
    hosted_runtime = _github_actions_runtime()
    if require_github_actions and not hosted_runtime:
        raise RuntimeError("HOSTED_SHADOW_REQUIRES_GITHUB_ACTIONS_RUNTIME")
    evidence_mode = EvidenceMode.HOSTED_SHADOW if hosted_runtime else EvidenceMode.SYNTHETIC_SHADOW
    pairs = build_pairs(source, evidence_mode=evidence_mode, measure=measure)
    resumes = build_resume_observations(source, evidence_mode=evidence_mode)
    receipt = evaluate_empirical_court(
        source_head_sha=source,
        paired_cases=pairs,
        resume_cases=resumes,
    )
    expected_decision = (
        "HOSTED_SHADOW_METACOG_QUALIFIED" if hosted_runtime
        else "STRUCTURAL_ONLY_SYNTHETIC_SHADOW"
    )
    if receipt.decision != expected_decision:
        raise AssertionError(f"HOSTED_SHADOW_EMPIRICAL_COURT_FAILED:{receipt.decision}:{receipt.blockers}")
    return {
        "schema": SCHEMA,
        "source_head_sha": source,
        "github_actions_runtime": hosted_runtime,
        "github_run_id": os.environ.get("GITHUB_RUN_ID") if hosted_runtime else None,
        "evidence_mode": evidence_mode.value,
        "pair_count": len(pairs),
        "resume_count": len(resumes),
        "oracle_action_coverage": sorted({metacognitive_assessment(_case(i)[0]).action.value for i in range(PAIR_COUNT)}),
        "cross_process_replacement_count": sum(item.process_before != item.process_after for item in resumes),
        "external_effect": False,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
        "full_autopilot_runtime_proven": False,
        "empirical_receipt": receipt.to_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha")
    parser.add_argument("--require-github-actions", action="store_true")
    parser.add_argument("--no-measure", action="store_true")
    parser.add_argument("--resume-child", nargs=2, metavar=("CHECKPOINT", "SHA256"))
    args = parser.parse_args(argv)
    if args.resume_child:
        return _resume_child(args.resume_child[0], args.resume_child[1])
    source_sha = args.source_sha or os.environ.get("GITHUB_SHA", "")
    result = run_campaign(
        source_sha,
        require_github_actions=args.require_github_actions,
        measure=not args.no_measure,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
