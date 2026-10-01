"""Prospective real-observation adapter for Self-Hosting R&D v1.

This is a thin binding layer over the admitted CFBE passive observation
collector. It does not watch, schedule, measure, infer, deploy, call a provider,
or promote a candidate. Callers supply real governed mission events, measured
observations, trusted evidence receipts, and the current source epoch.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from benchmarking.cfbe_omega.passive_observation_collector_v1 import (
    CollectedObservation,
    CollectorActionReceipt,
    CollectorState,
    DirectiveBinding,
    bind_eligible_directive,
    ingest_owner_value_observation,
    initialize_collector,
)
from benchmarking.cfbe_omega.prospective_observation_cohort_v1 import (
    initialize_prospective_cohort,
    validate_cohort_manifest,
)
from proofos_omega.cfbe import EVIDENCE_FACTORS
from federation.self_hosting_rd_matched_eval_v1 import (
    EngineeringObservation,
    MatchedPair,
)

SCHEMA = "FUSE-SELF-HOSTING-RD-PROSPECTIVE-OBSERVATION-ADAPTER-V1"
VERSION = "1.0.0"
CHAMPION_ID = "FUSE-DEV-INCUMBENT"
CANDIDATE_ID = "SELF-HOSTING-RD-CHALLENGER-V1"

_COHORT_TASKS: dict[int, tuple[tuple[str, str], ...]] = {
    1: (
        ("SHRD-ORACLE-01", "REQUIREMENT_COMPILATION"),
        ("SHRD-ORACLE-02", "REUSE_BEFORE_BUILD"),
        ("SHRD-ORACLE-03", "SOURCE_IMPLEMENTATION"),
        ("SHRD-ORACLE-04", "REGRESSION_REPAIR"),
        ("SHRD-ORACLE-05", "BUILD_TEST_EXECUTION"),
        ("SHRD-ORACLE-06", "DEPENDENCY_REDUCTION"),
        ("SHRD-ORACLE-07", "REFACTOR_SIMPLIFICATION"),
        ("SHRD-ORACLE-08", "ARCHITECTURE_CHALLENGE"),
        ("SHRD-ORACLE-09", "MIGRATION_PACKAGING"),
        ("SHRD-ORACLE-10", "ROLLBACK_RECOVERY"),
    ),
    2: (
        ("SHRD-ORACLE-11", "OBSERVABILITY_INSTRUMENTATION"),
        ("SHRD-ORACLE-12", "SECURITY_HARDENING"),
        ("SHRD-ORACLE-13", "TEST_SYNTHESIS"),
        ("SHRD-ORACLE-14", "PERFORMANCE_OPTIMIZATION"),
        ("SHRD-ORACLE-15", "DOCUMENTATION_RUNBOOK"),
        ("SHRD-ORACLE-16", "SOURCE_CURRENTNESS_RECOVERY"),
        ("SHRD-ORACLE-17", "PROOF_COURT_INTEGRATION"),
        ("SHRD-ORACLE-18", "PROVIDER_NEUTRALIZATION"),
        ("SHRD-ORACLE-19", "DISCONNECTED_REBUILD"),
        ("SHRD-ORACLE-20", "OWNER_VALUE_CLOSURE"),
    ),
}
_REQUIRED_ENGINEERING_METRICS = (
    "tool_calls",
    "unintended_writes",
    "safety_regressions",
    "external_runtime_dependencies",
    "reproducibility_ratio",
    "rollback_success_ratio",
)


def _required(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _is_digest(value: str) -> bool:
    prefix, sep, digest = str(value).partition(":")
    return sep == ":" and prefix == "sha256" and len(digest) == 64 and all(
        c in "0123456789abcdef" for c in digest.lower()
    )


def _boolean(value: Any, code: str) -> bool:
    if value is not True and value is not False:
        raise ValueError(code)
    return bool(value)


def _nonnegative(value: Any, code: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if number < 0:
        raise ValueError(code)
    return number


@dataclass(frozen=True, slots=True)
class ProspectiveProgramme:
    schema: str
    version: str
    source_head_sha: str
    cohort_manifests: tuple[Mapping[str, Any], ...]
    collector_states: tuple[CollectorState, ...]
    total_slots: int
    owner_value_proven: bool
    matched_eval_proven: bool
    provider_effect_authorized: bool
    external_effect: bool


def build_engineering_cohort_manifest(
    *,
    source_head_sha: str,
    registered_at: str,
    cohort_number: int,
) -> dict[str, Any]:
    source_head_sha = source_head_sha.strip().lower()
    if not _is_sha(source_head_sha):
        raise ValueError("SHRD_COHORT_SOURCE_HEAD_INVALID")
    tasks = _COHORT_TASKS.get(int(cohort_number))
    if tasks is None:
        raise ValueError("SHRD_COHORT_NUMBER_INVALID")
    manifest = initialize_prospective_cohort(
        cohort_id=f"SELF-HOSTING-RD-COHORT-{cohort_number:03d}",
        champion_id=CHAMPION_ID,
        candidate_id=CANDIDATE_ID,
        source_head_sha=source_head_sha,
        registered_at=registered_at,
        task_oracles=tuple(
            {"task_oracle_id": oracle_id, "task_class": task_class}
            for oracle_id, task_class in tasks
        ),
    ).to_dict()
    validate_cohort_manifest(manifest)
    return manifest


def initialize_prospective_programme(
    *,
    source_head_sha: str,
    registered_at: str,
) -> ProspectiveProgramme:
    manifests = tuple(
        build_engineering_cohort_manifest(
            source_head_sha=source_head_sha,
            registered_at=registered_at,
            cohort_number=index,
        )
        for index in (1, 2)
    )
    states = tuple(
        initialize_collector(manifest, source_base_sha=source_head_sha)
        for manifest in manifests
    )
    return ProspectiveProgramme(
        schema=SCHEMA,
        version=VERSION,
        source_head_sha=source_head_sha.lower(),
        cohort_manifests=manifests,
        collector_states=states,
        total_slots=sum(len(manifest["slots"]) for manifest in manifests),
        owner_value_proven=False,
        matched_eval_proven=False,
        provider_effect_authorized=False,
        external_effect=False,
    )


def compile_real_mission_directive(mission: Mapping[str, Any]) -> dict[str, Any]:
    if mission.get("real_mission") is not True:
        raise ValueError("SHRD_REAL_MISSION_REQUIRED")
    for field in ("synthetic", "shadow", "replayed"):
        if mission.get(field) is not False:
            raise ValueError("SHRD_" + field.upper() + "_MISSION_PROHIBITED")
    source_head = _required(mission.get("source_head_sha"), "SHRD_MISSION_SOURCE_HEAD_REQUIRED").lower()
    if not _is_sha(source_head):
        raise ValueError("SHRD_MISSION_SOURCE_HEAD_INVALID")
    task_class = _required(mission.get("task_class"), "SHRD_MISSION_TASK_CLASS_REQUIRED")
    valid_classes = {task for items in _COHORT_TASKS.values() for _, task in items}
    if task_class not in valid_classes:
        raise ValueError("SHRD_MISSION_TASK_CLASS_UNREGISTERED")
    event = {
        "directive_id": _required(mission.get("mission_id"), "SHRD_MISSION_ID_REQUIRED"),
        "task_class": task_class,
        "source_head_sha": source_head,
        "observed_at": _required(mission.get("observed_at"), "SHRD_MISSION_OBSERVED_AT_REQUIRED"),
        "real_directive": True,
        "synthetic": False,
        "shadow": False,
        "replayed": False,
        "proof_refs": tuple(str(x).strip() for x in mission.get("proof_refs") or () if str(x).strip()),
        "task_signature": _required(mission.get("task_signature"), "SHRD_MISSION_TASK_SIGNATURE_REQUIRED"),
        "input_digest": _required(mission.get("input_digest"), "SHRD_MISSION_INPUT_DIGEST_REQUIRED"),
        "environment_digest": _required(mission.get("environment_digest"), "SHRD_MISSION_ENV_DIGEST_REQUIRED"),
        "owner_goal_digest": _required(mission.get("owner_goal_digest"), "SHRD_MISSION_OWNER_GOAL_DIGEST_REQUIRED"),
    }
    if not event["proof_refs"]:
        raise ValueError("SHRD_MISSION_PROOF_REFS_REQUIRED")
    for key in ("input_digest", "environment_digest", "owner_goal_digest"):
        if not _is_digest(event[key]):
            raise ValueError("SHRD_MISSION_DIGEST_INVALID:" + key)
    return event


def bind_compiled_mission(
    state: CollectorState,
    cohort_manifest: Mapping[str, Any],
    directive_event: Mapping[str, Any],
    *,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    trusted_verifiers: Iterable[str],
) -> tuple[CollectorState, CollectorActionReceipt]:
    return bind_eligible_directive(
        state,
        cohort_manifest,
        directive_event,
        evidence_registry=evidence_registry,
        trusted_verifiers=trusted_verifiers,
    )


def compile_measured_observation(
    binding: DirectiveBinding,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    arm = _required(observation.get("arm"), "SHRD_OBSERVATION_ARM_REQUIRED").upper()
    if arm not in {"INCUMBENT", "CHALLENGER"}:
        raise ValueError("SHRD_OBSERVATION_ARM_INVALID")
    if observation.get("real_observation") is not True:
        raise ValueError("SHRD_REAL_OBSERVATION_REQUIRED")
    for field in ("synthetic", "shadow", "replayed"):
        if observation.get(field) is not False:
            raise ValueError("SHRD_" + field.upper() + "_OBSERVATION_PROHIBITED")

    arm_source = _required(
        observation.get("arm_source_head_sha"), "SHRD_ARM_SOURCE_HEAD_REQUIRED"
    ).lower()
    if not _is_sha(arm_source):
        raise ValueError("SHRD_ARM_SOURCE_HEAD_INVALID")
    input_digest = _required(observation.get("input_digest"), "SHRD_OBSERVATION_INPUT_DIGEST_REQUIRED")
    environment_digest = _required(
        observation.get("environment_digest"), "SHRD_OBSERVATION_ENV_DIGEST_REQUIRED"
    )
    if not _is_digest(input_digest) or not _is_digest(environment_digest):
        raise ValueError("SHRD_OBSERVATION_MATCH_DIGEST_INVALID")

    evidence_state = _required(
        observation.get("engineering_evidence_state"), "SHRD_ENGINEERING_EVIDENCE_STATE_REQUIRED"
    )
    if evidence_state not in EVIDENCE_FACTORS:
        raise ValueError("SHRD_ENGINEERING_EVIDENCE_STATE_INVALID")

    metrics: dict[str, float] = {}
    for key in _REQUIRED_ENGINEERING_METRICS:
        metrics[key] = _nonnegative(observation.get(key), "SHRD_ENGINEERING_METRIC_INVALID:" + key)

    proof_refs = tuple(
        str(x).strip() for x in observation.get("proof_refs") or () if str(x).strip()
    )
    if not proof_refs:
        raise ValueError("SHRD_OBSERVATION_PROOF_REFS_REQUIRED")

    variant = "BASELINE" if arm == "INCUMBENT" else "BUBBLES"
    observation_id = (
        binding.baseline_observation_id if arm == "INCUMBENT" else binding.candidate_observation_id
    )
    return {
        "observation_id": observation_id,
        "pair_id": binding.pair_id,
        "variant": variant,
        "mission_class": binding.task_class,
        "mission_id": binding.directive_id,
        "task_signature": _required(
            observation.get("task_signature"), "SHRD_OBSERVATION_TASK_SIGNATURE_REQUIRED"
        ),
        "oracle_id": binding.task_oracle_id,
        "source_head_sha": binding.source_head_sha,
        "observed_at": _required(
            observation.get("observed_at"), "SHRD_OBSERVATION_OBSERVED_AT_REQUIRED"
        ),
        "accepted": _boolean(observation.get("accepted"), "SHRD_OBSERVATION_ACCEPTED_BOOLEAN_REQUIRED"),
        "verified_output_ratio": _nonnegative(
            observation.get("verified_output_ratio"), "SHRD_VERIFIED_OUTPUT_RATIO_INVALID"
        ),
        "owner_intervention_seconds": _nonnegative(
            observation.get("owner_intervention_seconds"), "SHRD_OWNER_SECONDS_INVALID"
        ),
        "owner_intervention_count": int(
            _nonnegative(observation.get("owner_intervention_count"), "SHRD_OWNER_INTERVENTIONS_INVALID")
        ),
        "clarification_count": int(
            _nonnegative(observation.get("clarification_count"), "SHRD_CLARIFICATIONS_INVALID")
        ),
        "correction_count": int(
            _nonnegative(observation.get("correction_count"), "SHRD_CORRECTIONS_INVALID")
        ),
        "elapsed_seconds": _nonnegative(
            observation.get("elapsed_seconds"), "SHRD_ELAPSED_INVALID"
        ),
        "independent_readback": _boolean(
            observation.get("independent_readback"), "SHRD_INDEPENDENT_READBACK_BOOLEAN_REQUIRED"
        ),
        "proof_refs": proof_refs,
        "evidence_class": "OBSERVED_OWNER_VALUE",
        "measurement_state": "MEASURED",
        "real_observation": True,
        "synthetic": False,
        "shadow": False,
        "replayed": False,
        "arm": arm,
        "arm_source_head_sha": arm_source,
        "input_digest": input_digest,
        "environment_digest": environment_digest,
        "engineering_evidence_state": evidence_state,
        **metrics,
    }


def ingest_compiled_observation(
    state: CollectorState,
    observation_event: Mapping[str, Any],
    *,
    evidence_registry: Mapping[str, Mapping[str, Any]],
    trusted_verifiers: Iterable[str],
) -> tuple[CollectorState, CollectorActionReceipt]:
    return ingest_owner_value_observation(
        state,
        observation_event,
        evidence_registry=evidence_registry,
        trusted_verifiers=trusted_verifiers,
    )


def _engineering_observation(item: CollectedObservation) -> EngineeringObservation:
    raw = json.loads(item.canonical_record_json)
    arm = _required(raw.get("arm"), "SHRD_COLLECTED_ARM_REQUIRED").upper()
    if arm not in {"INCUMBENT", "CHALLENGER"}:
        raise ValueError("SHRD_COLLECTED_ARM_INVALID")
    metrics = {
        "verified_output_ratio": float(raw["verified_output_ratio"]),
        "elapsed_seconds": float(raw["elapsed_seconds"]),
        "tool_calls": float(raw["tool_calls"]),
        "owner_interventions": float(raw["owner_intervention_count"]),
        "unintended_writes": float(raw["unintended_writes"]),
        "safety_regressions": float(raw["safety_regressions"]),
        "external_runtime_dependencies": float(raw["external_runtime_dependencies"]),
        "reproducibility_ratio": float(raw["reproducibility_ratio"]),
        "rollback_success_ratio": float(raw["rollback_success_ratio"]),
    }
    proof_refs = tuple(sorted(set(item.proof_refs + item.resolved_receipt_sha256s)))
    result = EngineeringObservation(
        arm=arm,
        pair_id=item.pair_id,
        mission_class=_required(raw.get("mission_class"), "SHRD_COLLECTED_MISSION_CLASS_REQUIRED"),
        task_signature=_required(raw.get("task_signature"), "SHRD_COLLECTED_TASK_SIGNATURE_REQUIRED"),
        oracle_id=_required(raw.get("oracle_id"), "SHRD_COLLECTED_ORACLE_REQUIRED"),
        input_digest=_required(raw.get("input_digest"), "SHRD_COLLECTED_INPUT_DIGEST_REQUIRED"),
        environment_digest=_required(
            raw.get("environment_digest"), "SHRD_COLLECTED_ENV_DIGEST_REQUIRED"
        ),
        source_head_sha=_required(
            raw.get("arm_source_head_sha"), "SHRD_COLLECTED_ARM_SOURCE_REQUIRED"
        ).lower(),
        evidence_state=_required(
            raw.get("engineering_evidence_state"), "SHRD_COLLECTED_EVIDENCE_STATE_REQUIRED"
        ),
        metrics=metrics,
        proof_refs=proof_refs,
    )
    result.validate()
    return result


def compile_collected_matched_pair(
    state: CollectorState,
    pair_id: str,
) -> MatchedPair:
    items = tuple(x for x in state.observations if x.pair_id == pair_id)
    if len(items) != 2:
        raise ValueError("SHRD_COLLECTED_PAIR_REQUIRES_TWO_OBSERVATIONS")
    mapped_items = tuple(_engineering_observation(item) for item in items)
    mapped = {item.arm: item for item in mapped_items}
    if set(mapped) != {"INCUMBENT", "CHALLENGER"}:
        raise ValueError("SHRD_COLLECTED_PAIR_REQUIRES_INCUMBENT_AND_CHALLENGER")
    return MatchedPair(mapped["INCUMBENT"], mapped["CHALLENGER"])


__all__ = [
    "CANDIDATE_ID",
    "CHAMPION_ID",
    "ProspectiveProgramme",
    "bind_compiled_mission",
    "build_engineering_cohort_manifest",
    "compile_collected_matched_pair",
    "compile_measured_observation",
    "compile_real_mission_directive",
    "ingest_compiled_observation",
    "initialize_prospective_programme",
]
