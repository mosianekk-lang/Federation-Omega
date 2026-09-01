from __future__ import annotations

"""AutoPilot + Meta-Cognition observed-operational intake bridge v1.

This module converts already witnessed real operational episode telemetry into
the existing Meta-Cognition empirical court and owner-value court. It does not
create observations, call providers, authorize effects, or treat unit-test
fixtures as real evidence.

The trust boundary is explicit: witness envelopes must come from upstream
provider/runtime readback paths. This bridge verifies their schema, integrity
shape, source binding, timing, independence requirements, and cross-references;
it does not manufacture provider authenticity offline.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.autopilot_metacognition_empirical_court_v1 import (
    EvidenceMode,
    MetaCognitionPair,
    ResumeObservation,
    evaluate_empirical_court,
)
from evidenceops.caseforge.owner_value_deployment_court_v2 import (
    OWNER_VALUE_MODE,
    evaluate_proof_court,
)


SCHEMA = "CFBE-AUTOPILOT-METACOG-OBSERVED-OPERATIONAL-INTAKE-V1"
WITNESS_SCHEMA = "CFBE-OPERATIONAL-EVIDENCE-WITNESS-V1"
PAIR_SCHEMA = "CFBE-AUTOPILOT-OBSERVED-PAIR-V1"
RESUME_SCHEMA = "CFBE-AUTOPILOT-OBSERVED-RESUME-V1"
MEASUREMENT_ORIGIN = "REAL_OPERATIONAL_EPISODE"

WITNESS_KINDS = frozenset({"EXECUTION", "READBACK", "OUTCOME", "CHECKPOINT", "AUTHORITY"})
WITNESS_CLASSES = frozenset(
    {
        "IMMUTABLE_EXECUTION_RECEIPT",
        "PROVIDER_LIVE_INDEPENDENT_READBACK",
        "REPEATED_OPERATIONAL_SCOPED",
        "OWNER_ATTESTED_OPERATIONAL_OUTCOME",
        "PROVIDER_AUTHORITY_RECEIPT",
    }
)
INDEPENDENT_CLASSES = frozenset(
    {"PROVIDER_LIVE_INDEPENDENT_READBACK", "REPEATED_OPERATIONAL_SCOPED"}
)
FORBIDDEN_ENVIRONMENT_TOKENS = ("SYNTHETIC", "SHADOW", "FIXTURE", "TEST", "CANARY")

WITNESS_FIELDS = frozenset(
    {
        "schema",
        "ref",
        "kind",
        "evidence_class",
        "provider",
        "environment",
        "source_head_sha",
        "provider_object_id",
        "digest",
        "verified",
        "independent",
        "observed_at_utc",
    }
)
PAIR_FIELDS = frozenset(
    {
        "schema",
        "pair_id",
        "source_head_sha",
        "mission_class",
        "baseline_execution_id",
        "candidate_execution_id",
        "baseline_task_signature",
        "candidate_task_signature",
        "oracle_id",
        "measurement_origin",
        "baseline_quality",
        "candidate_quality",
        "baseline_elapsed_ms",
        "candidate_elapsed_ms",
        "baseline_owner_minutes",
        "candidate_owner_minutes",
        "baseline_owner_interventions",
        "candidate_owner_interventions",
        "baseline_clarification_count",
        "candidate_clarification_count",
        "baseline_correction_count",
        "candidate_correction_count",
        "baseline_verified_output_ratio",
        "candidate_verified_output_ratio",
        "candidate_reflection_used",
        "candidate_confidence",
        "candidate_outcome_correct",
        "confidence_recorded_at_utc",
        "outcome_resolved_at_utc",
        "independent_readback_ref",
        "proof_refs",
        "external_effect_observed",
        "effect_authority_ref",
    }
)
RESUME_FIELDS = frozenset(
    {
        "schema",
        "observation_id",
        "source_head_sha",
        "mission_class",
        "measurement_origin",
        "process_before",
        "process_after",
        "checkpoint_id",
        "resumed",
        "duplicate_effect_count",
        "state_drift",
        "independent_readback_ref",
        "proof_refs",
        "external_effect_observed",
        "effect_authority_ref",
    }
)


def canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _is_digest(value: str) -> bool:
    prefix, separator, digest = value.partition(":")
    return (
        separator == ":"
        and prefix == "sha256"
        and len(digest) == 64
        and all(c in "0123456789abcdef" for c in digest.lower())
    )


def _parse_utc(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(code) from exc
    _require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def _validate_environment(value: str, code: str) -> None:
    upper = value.upper()
    _require(bool(value.strip()), code)
    _require(not any(token in upper for token in FORBIDDEN_ENVIRONMENT_TOKENS), code)


def _source_ref(source_head_sha: str) -> str:
    return f"source:{source_head_sha}"


@dataclass(frozen=True, slots=True)
class EvidenceWitness:
    schema: str
    ref: str
    kind: str
    evidence_class: str
    provider: str
    environment: str
    source_head_sha: str
    provider_object_id: str
    digest: str
    verified: bool
    independent: bool
    observed_at_utc: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceWitness":
        _require(set(value).issubset(WITNESS_FIELDS), "WITNESS_UNKNOWN_FIELDS_REJECTED")
        return cls(
            schema=str(value.get("schema") or ""),
            ref=str(value.get("ref") or ""),
            kind=str(value.get("kind") or ""),
            evidence_class=str(value.get("evidence_class") or ""),
            provider=str(value.get("provider") or ""),
            environment=str(value.get("environment") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""),
            provider_object_id=str(value.get("provider_object_id") or ""),
            digest=str(value.get("digest") or ""),
            verified=value.get("verified") is True,
            independent=value.get("independent") is True,
            observed_at_utc=str(value.get("observed_at_utc") or ""),
        )

    def validate(self, *, expected_source_head_sha: str) -> "EvidenceWitness":
        _require(self.schema == WITNESS_SCHEMA, "WITNESS_SCHEMA_MISMATCH")
        _require(bool(self.ref.strip()), "WITNESS_REF_REQUIRED")
        _require(self.kind in WITNESS_KINDS, "WITNESS_KIND_INVALID")
        _require(self.evidence_class in WITNESS_CLASSES, "WITNESS_CLASS_INVALID")
        _require(bool(self.provider.strip()), "WITNESS_PROVIDER_REQUIRED")
        _validate_environment(self.environment, "WITNESS_NON_OPERATIONAL_ENVIRONMENT_REJECTED")
        _require(self.source_head_sha == expected_source_head_sha, "WITNESS_SOURCE_HEAD_MISMATCH")
        _require(bool(self.provider_object_id.strip()), "WITNESS_PROVIDER_OBJECT_ID_REQUIRED")
        _require(_is_digest(self.digest), "WITNESS_DIGEST_INVALID")
        _require(self.verified, "WITNESS_VERIFICATION_REQUIRED")
        _parse_utc(self.observed_at_utc, "WITNESS_OBSERVED_AT_INVALID")

        class_kind = {
            "IMMUTABLE_EXECUTION_RECEIPT": "EXECUTION",
            "OWNER_ATTESTED_OPERATIONAL_OUTCOME": "OUTCOME",
            "PROVIDER_AUTHORITY_RECEIPT": "AUTHORITY",
        }
        expected_kind = class_kind.get(self.evidence_class)
        if expected_kind:
            _require(self.kind == expected_kind, "WITNESS_CLASS_KIND_MISMATCH")
        if self.kind == "READBACK":
            _require(self.independent, "READBACK_WITNESS_MUST_BE_INDEPENDENT")
            _require(
                self.evidence_class in INDEPENDENT_CLASSES,
                "READBACK_WITNESS_CLASS_NOT_INDEPENDENT",
            )
        if self.evidence_class in INDEPENDENT_CLASSES:
            _require(self.independent, "INDEPENDENT_WITNESS_FLAG_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class ObservedPairRecord:
    schema: str
    pair_id: str
    source_head_sha: str
    mission_class: str
    baseline_execution_id: str
    candidate_execution_id: str
    baseline_task_signature: str
    candidate_task_signature: str
    oracle_id: str
    measurement_origin: str
    baseline_quality: float
    candidate_quality: float
    baseline_elapsed_ms: float
    candidate_elapsed_ms: float
    baseline_owner_minutes: float
    candidate_owner_minutes: float
    baseline_owner_interventions: int
    candidate_owner_interventions: int
    baseline_clarification_count: int
    candidate_clarification_count: int
    baseline_correction_count: int
    candidate_correction_count: int
    baseline_verified_output_ratio: float
    candidate_verified_output_ratio: float
    candidate_reflection_used: bool
    candidate_confidence: float
    candidate_outcome_correct: bool
    confidence_recorded_at_utc: str
    outcome_resolved_at_utc: str
    independent_readback_ref: str
    proof_refs: tuple[str, ...]
    external_effect_observed: bool
    effect_authority_ref: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ObservedPairRecord":
        _require(set(value).issubset(PAIR_FIELDS), "OBSERVED_PAIR_UNKNOWN_FIELDS_REJECTED")
        return cls(
            schema=str(value.get("schema") or ""),
            pair_id=str(value.get("pair_id") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""),
            mission_class=str(value.get("mission_class") or ""),
            baseline_execution_id=str(value.get("baseline_execution_id") or ""),
            candidate_execution_id=str(value.get("candidate_execution_id") or ""),
            baseline_task_signature=str(value.get("baseline_task_signature") or ""),
            candidate_task_signature=str(value.get("candidate_task_signature") or ""),
            oracle_id=str(value.get("oracle_id") or ""),
            measurement_origin=str(value.get("measurement_origin") or ""),
            baseline_quality=float(value.get("baseline_quality", -1)),
            candidate_quality=float(value.get("candidate_quality", -1)),
            baseline_elapsed_ms=float(value.get("baseline_elapsed_ms", -1)),
            candidate_elapsed_ms=float(value.get("candidate_elapsed_ms", -1)),
            baseline_owner_minutes=float(value.get("baseline_owner_minutes", -1)),
            candidate_owner_minutes=float(value.get("candidate_owner_minutes", -1)),
            baseline_owner_interventions=int(value.get("baseline_owner_interventions", -1)),
            candidate_owner_interventions=int(value.get("candidate_owner_interventions", -1)),
            baseline_clarification_count=int(value.get("baseline_clarification_count", -1)),
            candidate_clarification_count=int(value.get("candidate_clarification_count", -1)),
            baseline_correction_count=int(value.get("baseline_correction_count", -1)),
            candidate_correction_count=int(value.get("candidate_correction_count", -1)),
            baseline_verified_output_ratio=float(value.get("baseline_verified_output_ratio", -1)),
            candidate_verified_output_ratio=float(value.get("candidate_verified_output_ratio", -1)),
            candidate_reflection_used=value.get("candidate_reflection_used") is True,
            candidate_confidence=float(value.get("candidate_confidence", -1)),
            candidate_outcome_correct=value.get("candidate_outcome_correct") is True,
            confidence_recorded_at_utc=str(value.get("confidence_recorded_at_utc") or ""),
            outcome_resolved_at_utc=str(value.get("outcome_resolved_at_utc") or ""),
            independent_readback_ref=str(value.get("independent_readback_ref") or ""),
            proof_refs=tuple(str(x).strip() for x in value.get("proof_refs") or () if str(x).strip()),
            external_effect_observed=value.get("external_effect_observed") is True,
            effect_authority_ref=str(value.get("effect_authority_ref") or ""),
        )

    def validate(
        self,
        *,
        expected_source_head_sha: str,
        witnesses: Mapping[str, EvidenceWitness],
    ) -> "ObservedPairRecord":
        _require(self.schema == PAIR_SCHEMA, "OBSERVED_PAIR_SCHEMA_MISMATCH")
        _require(self.source_head_sha == expected_source_head_sha, "OBSERVED_PAIR_SOURCE_HEAD_MISMATCH")
        _require(bool(self.pair_id.strip() and self.mission_class.strip()), "OBSERVED_PAIR_IDENTITY_REQUIRED")
        _require(bool(self.oracle_id.strip()), "OBSERVED_PAIR_ORACLE_REQUIRED")
        _require(
            bool(self.baseline_execution_id.strip() and self.candidate_execution_id.strip()),
            "OBSERVED_PAIR_EXECUTION_IDS_REQUIRED",
        )
        _require(
            self.baseline_execution_id != self.candidate_execution_id,
            "OBSERVED_PAIR_EXECUTIONS_MUST_BE_DISTINCT",
        )
        _require(
            bool(self.baseline_task_signature.strip())
            and self.baseline_task_signature == self.candidate_task_signature,
            "OBSERVED_PAIR_TASK_SIGNATURE_MISMATCH",
        )
        _require(self.measurement_origin == MEASUREMENT_ORIGIN, "OBSERVED_PAIR_REAL_OPERATIONAL_ORIGIN_REQUIRED")
        _require(
            0 <= self.baseline_quality <= 1 and 0 <= self.candidate_quality <= 1,
            "OBSERVED_PAIR_QUALITY_INVALID",
        )
        _require(self.baseline_elapsed_ms > 0 and self.candidate_elapsed_ms > 0, "OBSERVED_PAIR_LATENCY_INVALID")
        _require(self.baseline_owner_minutes > 0 and self.candidate_owner_minutes >= 0, "OBSERVED_PAIR_OWNER_MINUTES_INVALID")
        counts = (
            self.baseline_owner_interventions,
            self.candidate_owner_interventions,
            self.baseline_clarification_count,
            self.candidate_clarification_count,
            self.baseline_correction_count,
            self.candidate_correction_count,
        )
        _require(all(x >= 0 for x in counts), "OBSERVED_PAIR_COUNTS_INVALID")
        _require(
            0 < self.baseline_verified_output_ratio <= 1
            and 0 < self.candidate_verified_output_ratio <= 1,
            "OBSERVED_PAIR_VERIFIED_OUTPUT_RATIO_INVALID",
        )
        _require(0 <= self.candidate_confidence <= 1, "OBSERVED_PAIR_CONFIDENCE_INVALID")
        predicted_at = _parse_utc(self.confidence_recorded_at_utc, "OBSERVED_PAIR_CONFIDENCE_TIME_INVALID")
        resolved_at = _parse_utc(self.outcome_resolved_at_utc, "OBSERVED_PAIR_OUTCOME_TIME_INVALID")
        _require(predicted_at < resolved_at, "OBSERVED_PAIR_CONFIDENCE_MUST_PREDATE_OUTCOME")

        unique_refs = set(self.proof_refs)
        _require(_source_ref(expected_source_head_sha) in unique_refs, "OBSERVED_PAIR_SOURCE_REF_REQUIRED")
        witness_refs = {ref for ref in unique_refs if ref != _source_ref(expected_source_head_sha)}
        _require(len(witness_refs) >= 4, "OBSERVED_PAIR_WITNESS_REFS_INCOMPLETE")
        _require(witness_refs.issubset(witnesses), "OBSERVED_PAIR_UNKNOWN_WITNESS_REF")
        _require(self.independent_readback_ref in witness_refs, "OBSERVED_PAIR_READBACK_REF_NOT_BOUND")
        readback = witnesses[self.independent_readback_ref]
        _require(readback.kind == "READBACK" and readback.independent, "OBSERVED_PAIR_READBACK_INVALID")
        kinds = [witnesses[ref].kind for ref in witness_refs]
        _require(kinds.count("EXECUTION") >= 2, "OBSERVED_PAIR_TWO_EXECUTION_WITNESSES_REQUIRED")
        _require("OUTCOME" in kinds, "OBSERVED_PAIR_OUTCOME_WITNESS_REQUIRED")
        _require("READBACK" in kinds, "OBSERVED_PAIR_READBACK_WITNESS_REQUIRED")

        if self.external_effect_observed:
            _require(bool(self.effect_authority_ref), "OBSERVED_PAIR_EFFECT_AUTHORITY_REF_REQUIRED")
            _require(self.effect_authority_ref in witness_refs, "OBSERVED_PAIR_EFFECT_AUTHORITY_NOT_BOUND")
            authority = witnesses[self.effect_authority_ref]
            _require(
                authority.kind == "AUTHORITY" and authority.evidence_class == "PROVIDER_AUTHORITY_RECEIPT",
                "OBSERVED_PAIR_EFFECT_AUTHORITY_INVALID",
            )
        else:
            _require(not self.effect_authority_ref, "OBSERVED_PAIR_UNUSED_AUTHORITY_REF_REJECTED")
        return self

    def to_metacognition_pair(self) -> MetaCognitionPair:
        return MetaCognitionPair(
            pair_id=self.pair_id,
            source_head_sha=self.source_head_sha,
            task_signature=self.baseline_task_signature,
            evidence_mode=EvidenceMode.OBSERVED_OPERATIONAL,
            baseline_quality=self.baseline_quality,
            candidate_quality=self.candidate_quality,
            baseline_elapsed_ms=self.baseline_elapsed_ms,
            candidate_elapsed_ms=self.candidate_elapsed_ms,
            baseline_owner_interventions=self.baseline_owner_interventions,
            candidate_owner_interventions=self.candidate_owner_interventions,
            candidate_reflection_used=self.candidate_reflection_used,
            candidate_confidence=self.candidate_confidence,
            candidate_outcome_correct=self.candidate_outcome_correct,
            independent_readback=True,
            proof_refs=self.proof_refs,
        )

    def to_owner_value_mapping(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "mission_class": self.mission_class,
            "task_signature": self.baseline_task_signature,
            "oracle_id": self.oracle_id,
            "source_head_sha": self.source_head_sha,
            "evidence_mode": OWNER_VALUE_MODE,
            "baseline_owner_minutes": self.baseline_owner_minutes,
            "candidate_owner_minutes": self.candidate_owner_minutes,
            "baseline_owner_interventions": self.baseline_owner_interventions,
            "candidate_owner_interventions": self.candidate_owner_interventions,
            "baseline_clarification_count": self.baseline_clarification_count,
            "candidate_clarification_count": self.candidate_clarification_count,
            "baseline_correction_count": self.baseline_correction_count,
            "candidate_correction_count": self.candidate_correction_count,
            "baseline_verified_output_ratio": self.baseline_verified_output_ratio,
            "candidate_verified_output_ratio": self.candidate_verified_output_ratio,
            "baseline_elapsed_seconds": self.baseline_elapsed_ms / 1000.0,
            "candidate_elapsed_seconds": self.candidate_elapsed_ms / 1000.0,
            "independent_readback": True,
            "proof_refs": list(self.proof_refs),
        }


@dataclass(frozen=True, slots=True)
class ObservedResumeRecord:
    schema: str
    observation_id: str
    source_head_sha: str
    mission_class: str
    measurement_origin: str
    process_before: str
    process_after: str
    checkpoint_id: str
    resumed: bool
    duplicate_effect_count: int
    state_drift: bool
    independent_readback_ref: str
    proof_refs: tuple[str, ...]
    external_effect_observed: bool
    effect_authority_ref: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ObservedResumeRecord":
        _require(set(value).issubset(RESUME_FIELDS), "OBSERVED_RESUME_UNKNOWN_FIELDS_REJECTED")
        return cls(
            schema=str(value.get("schema") or ""),
            observation_id=str(value.get("observation_id") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""),
            mission_class=str(value.get("mission_class") or ""),
            measurement_origin=str(value.get("measurement_origin") or ""),
            process_before=str(value.get("process_before") or ""),
            process_after=str(value.get("process_after") or ""),
            checkpoint_id=str(value.get("checkpoint_id") or ""),
            resumed=value.get("resumed") is True,
            duplicate_effect_count=int(value.get("duplicate_effect_count", -1)),
            state_drift=value.get("state_drift") is True,
            independent_readback_ref=str(value.get("independent_readback_ref") or ""),
            proof_refs=tuple(str(x).strip() for x in value.get("proof_refs") or () if str(x).strip()),
            external_effect_observed=value.get("external_effect_observed") is True,
            effect_authority_ref=str(value.get("effect_authority_ref") or ""),
        )

    def validate(
        self,
        *,
        expected_source_head_sha: str,
        witnesses: Mapping[str, EvidenceWitness],
    ) -> "ObservedResumeRecord":
        _require(self.schema == RESUME_SCHEMA, "OBSERVED_RESUME_SCHEMA_MISMATCH")
        _require(self.source_head_sha == expected_source_head_sha, "OBSERVED_RESUME_SOURCE_HEAD_MISMATCH")
        _require(bool(self.observation_id.strip() and self.mission_class.strip()), "OBSERVED_RESUME_IDENTITY_REQUIRED")
        _require(self.measurement_origin == MEASUREMENT_ORIGIN, "OBSERVED_RESUME_REAL_OPERATIONAL_ORIGIN_REQUIRED")
        _require(bool(self.process_before.strip() and self.process_after.strip()), "OBSERVED_RESUME_PROCESS_IDS_REQUIRED")
        _require(self.process_before != self.process_after, "OBSERVED_RESUME_PROCESS_REPLACEMENT_REQUIRED")
        _require(bool(self.checkpoint_id.strip()), "OBSERVED_RESUME_CHECKPOINT_REQUIRED")
        _require(self.duplicate_effect_count >= 0, "OBSERVED_RESUME_DUPLICATE_COUNT_INVALID")

        unique_refs = set(self.proof_refs)
        _require(_source_ref(expected_source_head_sha) in unique_refs, "OBSERVED_RESUME_SOURCE_REF_REQUIRED")
        witness_refs = {ref for ref in unique_refs if ref != _source_ref(expected_source_head_sha)}
        _require(len(witness_refs) >= 4, "OBSERVED_RESUME_WITNESS_REFS_INCOMPLETE")
        _require(witness_refs.issubset(witnesses), "OBSERVED_RESUME_UNKNOWN_WITNESS_REF")
        _require(self.independent_readback_ref in witness_refs, "OBSERVED_RESUME_READBACK_REF_NOT_BOUND")
        readback = witnesses[self.independent_readback_ref]
        _require(readback.kind == "READBACK" and readback.independent, "OBSERVED_RESUME_READBACK_INVALID")
        kinds = [witnesses[ref].kind for ref in witness_refs]
        _require(kinds.count("EXECUTION") >= 2, "OBSERVED_RESUME_TWO_EXECUTION_WITNESSES_REQUIRED")
        _require("CHECKPOINT" in kinds, "OBSERVED_RESUME_CHECKPOINT_WITNESS_REQUIRED")
        _require("READBACK" in kinds, "OBSERVED_RESUME_READBACK_WITNESS_REQUIRED")

        if self.external_effect_observed:
            _require(bool(self.effect_authority_ref), "OBSERVED_RESUME_EFFECT_AUTHORITY_REF_REQUIRED")
            _require(self.effect_authority_ref in witness_refs, "OBSERVED_RESUME_EFFECT_AUTHORITY_NOT_BOUND")
            authority = witnesses[self.effect_authority_ref]
            _require(
                authority.kind == "AUTHORITY" and authority.evidence_class == "PROVIDER_AUTHORITY_RECEIPT",
                "OBSERVED_RESUME_EFFECT_AUTHORITY_INVALID",
            )
        else:
            _require(not self.effect_authority_ref, "OBSERVED_RESUME_UNUSED_AUTHORITY_REF_REJECTED")
        return self

    def to_resume_observation(self) -> ResumeObservation:
        return ResumeObservation(
            observation_id=self.observation_id,
            source_head_sha=self.source_head_sha,
            evidence_mode=EvidenceMode.OBSERVED_OPERATIONAL,
            process_before=self.process_before,
            process_after=self.process_after,
            checkpoint_id=self.checkpoint_id,
            resumed=self.resumed,
            duplicate_effect_count=self.duplicate_effect_count,
            state_drift=self.state_drift,
            independent_readback=True,
            proof_refs=self.proof_refs,
        )


@dataclass(frozen=True, slots=True)
class ObservedOperationalAdmissionReceipt:
    schema: str
    source_head_sha: str
    candidate_id: str
    witness_count: int
    pair_record_count: int
    resume_record_count: int
    empirical_court: dict[str, Any]
    owner_value_court: dict[str, Any]
    observed_empirical_candidate: bool
    owner_value_proven: bool
    provider_runtime_candidate: bool
    full_autopilot_runtime_proven: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    decision: str
    next_gate: str
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_observed_operational_intake(
    *,
    candidate_id: str,
    source_head_sha: str,
    witness_records: Sequence[Mapping[str, Any]],
    pair_records: Sequence[Mapping[str, Any]],
    resume_records: Sequence[Mapping[str, Any]],
) -> ObservedOperationalAdmissionReceipt:
    _require(bool(candidate_id.strip()), "OBSERVED_INTAKE_CANDIDATE_ID_REQUIRED")
    _require(_is_sha(source_head_sha), "OBSERVED_INTAKE_SOURCE_SHA_INVALID")

    witness_items = tuple(
        EvidenceWitness.from_mapping(item).validate(expected_source_head_sha=source_head_sha)
        for item in witness_records
    )
    witness_refs = [item.ref for item in witness_items]
    _require(len(set(witness_refs)) == len(witness_refs), "WITNESS_REFS_MUST_BE_UNIQUE")
    witnesses = {item.ref: item for item in witness_items}

    pair_items = tuple(
        ObservedPairRecord.from_mapping(item).validate(
            expected_source_head_sha=source_head_sha,
            witnesses=witnesses,
        )
        for item in pair_records
    )
    resume_items = tuple(
        ObservedResumeRecord.from_mapping(item).validate(
            expected_source_head_sha=source_head_sha,
            witnesses=witnesses,
        )
        for item in resume_records
    )
    pair_ids = [item.pair_id for item in pair_items]
    resume_ids = [item.observation_id for item in resume_items]
    _require(len(set(pair_ids)) == len(pair_ids), "OBSERVED_PAIR_IDS_MUST_BE_UNIQUE")
    _require(len(set(resume_ids)) == len(resume_ids), "OBSERVED_RESUME_IDS_MUST_BE_UNIQUE")

    empirical = evaluate_empirical_court(
        source_head_sha=source_head_sha,
        paired_cases=[item.to_metacognition_pair() for item in pair_items],
        resume_cases=[item.to_resume_observation() for item in resume_items],
    )
    owner_value = evaluate_proof_court(
        candidate_id=candidate_id,
        source_head_sha=source_head_sha,
        owner_value_observations=[item.to_owner_value_mapping() for item in pair_items],
        runtime_or_deployment_evidence=(),
    )

    observed_empirical_candidate = empirical.observed_empirical_candidate
    owner_value_proven = owner_value.owner_value_proven
    if observed_empirical_candidate and owner_value_proven:
        decision = "OBSERVED_OPERATIONAL_METACOG_AND_OWNER_VALUE_CANDIDATE"
        next_gate = "PROVIDER_NATIVE_ALWAYS_ON_EVENT_INTAKE_AND_DURABLE_RUNTIME"
    elif observed_empirical_candidate:
        decision = "OBSERVED_OPERATIONAL_METACOG_CANDIDATE_OWNER_VALUE_GATE_OPEN"
        next_gate = "CLOSE_OWNER_VALUE_GATE_WITH_MATCHED_REAL_EPISODES"
    else:
        decision = "OBSERVED_OPERATIONAL_INTAKE_ADMITTED_MORE_EPISODES_REQUIRED"
        next_gate = "COLLECT_MATCHED_REAL_EPISODES_UNTIL_EMPIRICAL_GATES_CLOSE"

    payload = {
        "schema": SCHEMA,
        "source_head_sha": source_head_sha,
        "candidate_id": candidate_id,
        "witness_count": len(witness_items),
        "pair_record_count": len(pair_items),
        "resume_record_count": len(resume_items),
        "empirical_court": empirical.to_dict(),
        "owner_value_court": owner_value.to_dict(),
        "observed_empirical_candidate": observed_empirical_candidate,
        "owner_value_proven": owner_value_proven,
        "provider_runtime_candidate": False,
        "full_autopilot_runtime_proven": False,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
        "decision": decision,
        "next_gate": next_gate,
        "truth_boundary": (
            "Only minimal telemetry from already witnessed real operational episodes is accepted; raw prompts, transcripts, message bodies, secret values, and private content are outside this schema.",
            "Unit tests and hand-constructed fixtures validate code paths only and never establish OBSERVED_OPERATIONAL evidence.",
            "The bridge verifies witness structure, source binding, timing, integrity shape, and independence requirements but cannot manufacture upstream provider authenticity offline.",
            "Past external effects may be measured only when an authority witness is bound; this bridge never grants effect authority.",
            "OBSERVED_OPERATIONAL evidence cannot prove provider-native always-on intake or durable provider runtime.",
            "No stable promotion or full-autopilot claim is authorized by this bridge.",
        ),
    }
    return ObservedOperationalAdmissionReceipt(**payload, receipt_sha256=canonical_hash(payload))
