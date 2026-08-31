from __future__ import annotations

"""Proof-bound owner-value mission ingress for Sentinel Ω.

This module bridges already-measured mission receipts into Sentinel observation
semantics and the existing Bubbles owner-value court input contract. It does not
measure owner time itself, infer missing metrics, call providers, write KDV, or
promote owner value. Unmeasured records remain explicitly ineligible for court
compilation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .observability_causal_fabric import NormalizedObservation, SignalKind

BASELINE = "BASELINE"
BUBBLES = "BUBBLES"
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
OBSERVED_OWNER_VALUE = "OBSERVED_OWNER_VALUE"
UNMEASURED_OWNER_VALUE = "UNMEASURED_OWNER_VALUE"


def _iso(value: str) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("OWNER_VALUE_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc).isoformat()


def _required(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _optional_float(value: Any, code: str) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if number < 0:
        raise ValueError(code)
    return number


def _optional_int(value: Any, code: str) -> int | None:
    if value in (None, ""):
        return None
    number = int(value)
    if number < 0:
        raise ValueError(code)
    return number


def _ratio(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if not 0 < number <= 1:
        raise ValueError("OWNER_VALUE_OUTPUT_RATIO_INVALID")
    return number


def _proof_refs(value: Any, proof_ref: str | None = None) -> tuple[str, ...]:
    refs: set[str] = set()
    if isinstance(value, str):
        refs.update(item.strip() for item in value.split(";") if item.strip())
    elif value:
        refs.update(str(item).strip() for item in value if str(item).strip())
    if proof_ref is not None and str(proof_ref).strip():
        refs.add(str(proof_ref).strip())
    if not refs:
        raise ValueError("OWNER_VALUE_PROOF_REF_REQUIRED")
    return tuple(sorted(refs))


@dataclass(frozen=True, slots=True)
class OwnerValueMissionRecord:
    observation_id: str
    pair_id: str
    variant: str
    mission_class: str
    mission_id: str
    task_signature: str
    oracle_id: str
    source_head_sha: str
    observed_at: str
    accepted: bool | None
    verified_output_ratio: float | None
    owner_intervention_seconds: float | None
    owner_intervention_count: int | None
    clarification_count: int | None
    correction_count: int | None
    elapsed_seconds: float | None
    independent_readback: bool
    proof_refs: tuple[str, ...]
    evidence_class: str
    measurement_state: str

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        proof_ref: str | None = None,
    ) -> "OwnerValueMissionRecord":
        accepted_raw = value.get("accepted")
        if accepted_raw in (None, ""):
            accepted: bool | None = None
        elif accepted_raw is True or accepted_raw is False:
            accepted = bool(accepted_raw)
        else:
            raise ValueError("OWNER_VALUE_ACCEPTED_BOOLEAN_REQUIRED")

        independent_raw = value.get("independent_readback", False)
        if independent_raw is not True and independent_raw is not False:
            raise ValueError("OWNER_VALUE_READBACK_BOOLEAN_REQUIRED")

        record = cls(
            observation_id=_required(value.get("observation_id"), "OWNER_VALUE_OBSERVATION_ID_REQUIRED"),
            pair_id=_required(value.get("pair_id"), "OWNER_VALUE_PAIR_ID_REQUIRED"),
            variant=_required(value.get("variant"), "OWNER_VALUE_VARIANT_REQUIRED").upper(),
            mission_class=_required(value.get("mission_class"), "OWNER_VALUE_MISSION_CLASS_REQUIRED"),
            mission_id=_required(value.get("mission_id"), "OWNER_VALUE_MISSION_ID_REQUIRED"),
            task_signature=_required(value.get("task_signature"), "OWNER_VALUE_TASK_SIGNATURE_REQUIRED"),
            oracle_id=_required(value.get("oracle_id"), "OWNER_VALUE_ORACLE_ID_REQUIRED"),
            source_head_sha=_required(value.get("source_head_sha"), "OWNER_VALUE_SOURCE_HEAD_REQUIRED").lower(),
            observed_at=_iso(_required(value.get("observed_at") or value.get("observed_at_sast"), "OWNER_VALUE_OBSERVED_AT_REQUIRED")),
            accepted=accepted,
            verified_output_ratio=_ratio(value.get("verified_output_ratio")),
            owner_intervention_seconds=_optional_float(value.get("owner_intervention_seconds"), "OWNER_VALUE_OWNER_SECONDS_NONNEGATIVE_REQUIRED"),
            owner_intervention_count=_optional_int(value.get("owner_intervention_count"), "OWNER_VALUE_INTERVENTION_COUNT_NONNEGATIVE_REQUIRED"),
            clarification_count=_optional_int(value.get("clarification_count"), "OWNER_VALUE_CLARIFICATION_COUNT_NONNEGATIVE_REQUIRED"),
            correction_count=_optional_int(value.get("correction_count"), "OWNER_VALUE_CORRECTION_COUNT_NONNEGATIVE_REQUIRED"),
            elapsed_seconds=_optional_float(value.get("elapsed_seconds"), "OWNER_VALUE_ELAPSED_NONNEGATIVE_REQUIRED"),
            independent_readback=bool(independent_raw),
            proof_refs=_proof_refs(value.get("proof_refs") or value.get("proof_refs_json"), proof_ref),
            evidence_class=_required(value.get("evidence_class"), "OWNER_VALUE_EVIDENCE_CLASS_REQUIRED"),
            measurement_state=_required(value.get("measurement_state"), "OWNER_VALUE_MEASUREMENT_STATE_REQUIRED").upper(),
        )
        return record.validate()

    @property
    def fully_measured(self) -> bool:
        required = (
            self.accepted,
            self.verified_output_ratio,
            self.owner_intervention_seconds,
            self.owner_intervention_count,
            self.clarification_count,
            self.correction_count,
            self.elapsed_seconds,
        )
        return all(value is not None for value in required)

    @property
    def court_eligible_single_observation(self) -> bool:
        return (
            self.measurement_state == MEASURED
            and self.evidence_class == OBSERVED_OWNER_VALUE
            and self.fully_measured
            and self.independent_readback
        )

    def validate(self) -> "OwnerValueMissionRecord":
        if self.variant not in {BASELINE, BUBBLES}:
            raise ValueError("OWNER_VALUE_VARIANT_INVALID")
        if not _is_sha(self.source_head_sha):
            raise ValueError("OWNER_VALUE_SOURCE_HEAD_SHA_INVALID")
        if self.measurement_state not in {MEASURED, UNMEASURED}:
            raise ValueError("OWNER_VALUE_MEASUREMENT_STATE_INVALID")
        if self.measurement_state == MEASURED:
            if self.evidence_class != OBSERVED_OWNER_VALUE:
                raise ValueError("OWNER_VALUE_MEASURED_EVIDENCE_CLASS_INVALID")
            if not self.fully_measured:
                raise ValueError("OWNER_VALUE_MEASURED_FIELDS_INCOMPLETE")
            if not self.independent_readback:
                raise ValueError("OWNER_VALUE_INDEPENDENT_READBACK_REQUIRED")
            if float(self.elapsed_seconds or 0) <= 0:
                raise ValueError("OWNER_VALUE_ELAPSED_POSITIVE_REQUIRED")
        else:
            if self.evidence_class == OBSERVED_OWNER_VALUE:
                raise ValueError("OWNER_VALUE_UNMEASURED_CANNOT_CLAIM_OBSERVED")
        return self

    def to_kdv_mapping(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "pair_id": self.pair_id,
            "variant": self.variant,
            "mission_class": self.mission_class,
            "mission_id": self.mission_id,
            "task_signature": self.task_signature,
            "oracle_id": self.oracle_id,
            "source_head_sha": self.source_head_sha,
            "observed_at_sast": self.observed_at,
            "accepted": self.accepted,
            "verified_output_ratio": self.verified_output_ratio,
            "owner_intervention_seconds": self.owner_intervention_seconds,
            "owner_intervention_count": self.owner_intervention_count,
            "clarification_count": self.clarification_count,
            "correction_count": self.correction_count,
            "elapsed_seconds": self.elapsed_seconds,
            "independent_readback": self.independent_readback,
            "proof_refs_json": list(self.proof_refs),
            "evidence_class": self.evidence_class,
            "measurement_state": self.measurement_state,
        }

    def to_sentinel_observation(self) -> NormalizedObservation:
        measured = self.court_eligible_single_observation
        return NormalizedObservation(
            observation_id=f"OWNER-VALUE-{self.observation_id}",
            source="BUBBLES_OWNER_VALUE",
            signal_kind=SignalKind.PROOF if measured else SignalKind.HEALTH,
            target_id=f"mission:{self.mission_id}",
            observed_at=self.observed_at,
            fingerprint=("OWNER_VALUE_MEASURED" if measured else "OWNER_VALUE_UNMEASURED") + f":{self.variant}",
            severity=0.02 if measured else 0.35,
            proof_refs=self.proof_refs,
            change_ref=self.source_head_sha,
            attributes={**asdict(self), "court_eligible_single_observation": measured},
        ).validate()


@dataclass(frozen=True, slots=True)
class CompiledOwnerValuePair:
    pair_id: str
    mission_class: str
    task_signature: str
    oracle_id: str
    source_head_sha: str
    baseline_observation_id: str
    candidate_observation_id: str
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
    baseline_elapsed_seconds: float
    candidate_elapsed_seconds: float
    independent_readback: bool
    proof_refs: tuple[str, ...]
    evidence_mode: str = OBSERVED_OWNER_VALUE

    def to_court_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("baseline_observation_id")
        payload.pop("candidate_observation_id")
        return payload


class OwnerValueMissionObservationAdapter:
    """Normalize one already-fetched mission-value record without inventing metrics."""

    @staticmethod
    def adapt(
        record: Mapping[str, Any],
        *,
        proof_ref: str | None = None,
    ) -> tuple[OwnerValueMissionRecord, NormalizedObservation]:
        item = OwnerValueMissionRecord.from_mapping(record, proof_ref=proof_ref)
        return item, item.to_sentinel_observation()


class OwnerValuePairCompiler:
    """Compile one measured BASELINE/BUBBLES pair for the existing value court."""

    @staticmethod
    def compile(
        first: OwnerValueMissionRecord,
        second: OwnerValueMissionRecord,
    ) -> CompiledOwnerValuePair:
        items = {first.variant: first, second.variant: second}
        if set(items) != {BASELINE, BUBBLES}:
            raise ValueError("OWNER_VALUE_BASELINE_AND_BUBBLES_REQUIRED")
        baseline = items[BASELINE]
        candidate = items[BUBBLES]
        if not baseline.court_eligible_single_observation or not candidate.court_eligible_single_observation:
            raise ValueError("OWNER_VALUE_PAIR_REQUIRES_TWO_MEASURED_OBSERVATIONS")
        identity = (
            "pair_id",
            "mission_class",
            "task_signature",
            "oracle_id",
            "source_head_sha",
        )
        for field in identity:
            if getattr(baseline, field) != getattr(candidate, field):
                raise ValueError(f"OWNER_VALUE_PAIR_{field.upper()}_MISMATCH")
        proof_refs = tuple(sorted(set(baseline.proof_refs + candidate.proof_refs)))
        if len(proof_refs) < 2:
            raise ValueError("OWNER_VALUE_PAIR_DISTINCT_PROOF_REFS_REQUIRED")
        if float(baseline.owner_intervention_seconds or 0) <= 0:
            raise ValueError("OWNER_VALUE_BASELINE_OWNER_TIME_POSITIVE_REQUIRED")
        return CompiledOwnerValuePair(
            pair_id=baseline.pair_id,
            mission_class=baseline.mission_class,
            task_signature=baseline.task_signature,
            oracle_id=baseline.oracle_id,
            source_head_sha=baseline.source_head_sha,
            baseline_observation_id=baseline.observation_id,
            candidate_observation_id=candidate.observation_id,
            baseline_owner_minutes=round(float(baseline.owner_intervention_seconds or 0) / 60.0, 6),
            candidate_owner_minutes=round(float(candidate.owner_intervention_seconds or 0) / 60.0, 6),
            baseline_owner_interventions=int(baseline.owner_intervention_count or 0),
            candidate_owner_interventions=int(candidate.owner_intervention_count or 0),
            baseline_clarification_count=int(baseline.clarification_count or 0),
            candidate_clarification_count=int(candidate.clarification_count or 0),
            baseline_correction_count=int(baseline.correction_count or 0),
            candidate_correction_count=int(candidate.correction_count or 0),
            baseline_verified_output_ratio=float(baseline.verified_output_ratio or 0),
            candidate_verified_output_ratio=float(candidate.verified_output_ratio or 0),
            baseline_elapsed_seconds=float(baseline.elapsed_seconds or 0),
            candidate_elapsed_seconds=float(candidate.elapsed_seconds or 0),
            independent_readback=baseline.independent_readback and candidate.independent_readback,
            proof_refs=proof_refs,
        )


__all__ = [
    "BASELINE",
    "BUBBLES",
    "CompiledOwnerValuePair",
    "MEASURED",
    "OBSERVED_OWNER_VALUE",
    "OwnerValueMissionObservationAdapter",
    "OwnerValueMissionRecord",
    "OwnerValuePairCompiler",
    "UNMEASURED",
    "UNMEASURED_OWNER_VALUE",
]
