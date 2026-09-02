from __future__ import annotations

"""Read-only EDPF predictor evidence/profile projection.

Profiles are reconstructed from genuinely prospective, later-resolved Living
State prediction/outcome events. The projection is isolated by EDPF source head,
matter scope, predictor id, domain, source-family fingerprint and predictor
version. It persists nothing and grants no dispatch/effect authority.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    PredictorProfile,
    update_predictor,
)
from .edpf_prediction_adapter import (
    OPEN_STATE,
    RESOLVED_FALSE_STATE,
    RESOLVED_TRUE_STATE,
    SCHEMA as INTAKE_SCHEMA,
    compile_real_shadow_pairs,
)
from .edpf_prediction_request import PredictorCandidate
from .types import NodeKind

SCHEMA = "SOVARA_EDPF_PREDICTOR_EVIDENCE_PROJECTION_V1"
THIN_SAMPLE_FLOOR = 10
SHADOW_COUNT_FLOOR = 30


class EvidenceState(str, Enum):
    NEUTRAL_UNSEEN = "NEUTRAL_UNSEEN"
    THIN_PROSPECTIVE = "THIN_PROSPECTIVE"
    OBSERVED_PROSPECTIVE = "OBSERVED_PROSPECTIVE"
    SHADOW_COUNT_ELIGIBLE = "SHADOW_COUNT_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class PredictorDefinition:
    predictor_id: str
    source_fingerprint: str
    predictor_version: str
    provider_backed: bool
    supported_domains: tuple[str, ...]

    def validate(self) -> "PredictorDefinition":
        if not self.predictor_id.strip() or not self.source_fingerprint.strip() or not self.predictor_version.strip():
            raise ValueError("EDPF_PROJECTION_PREDICTOR_IDENTITY_REQUIRED")
        if not self.supported_domains or any(not item.strip() for item in self.supported_domains):
            raise ValueError("EDPF_PROJECTION_SUPPORTED_DOMAIN_REQUIRED")
        if len(set(self.supported_domains)) != len(self.supported_domains):
            raise ValueError("EDPF_PROJECTION_DUPLICATE_SUPPORTED_DOMAIN")
        return self


@dataclass(frozen=True, slots=True)
class MissionPredictorFit:
    predictor_id: str
    domain: str
    relevance: float
    independence: float
    expected_information_gain: float
    cost: float
    latency: float

    def validate(self) -> "MissionPredictorFit":
        if not self.predictor_id.strip() or not self.domain.strip():
            raise ValueError("EDPF_PROJECTION_MISSION_FIT_IDENTITY_REQUIRED")
        for name in ("relevance", "independence", "expected_information_gain", "cost", "latency"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_PROJECTION_{name.upper()}_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class PredictorEvidenceProfile:
    schema: str
    system_source_head_sha: str
    matter_scope: str
    predictor_id: str
    domain: str
    source_fingerprint: str
    predictor_version: str
    resolved_samples: int
    evidence_state: EvidenceState
    profile: PredictorProfile
    empirical_trust_weight: float
    empirical_accuracy: float
    empirical_calibration_error: float
    empirical_brier_score: float
    provider_backed: bool
    calibration_positive_proven: bool
    owner_value_proven: bool
    live_weight_change_authorized: bool


@dataclass(frozen=True, slots=True)
class ProjectedPredictorCandidate:
    definition: PredictorDefinition
    fit: MissionPredictorFit
    evidence: PredictorEvidenceProfile
    candidate: PredictorCandidate
    neutral_fallback_used: bool
    dispatch_authorized: bool = False
    external_effect_authorized: bool = False
    stable_self_promotion_allowed: bool = False


def _kind(value: object) -> str:
    return value.value if isinstance(value, NodeKind) else str(value)


def _sha40(value: str) -> str:
    candidate = str(value).lower().strip()
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError("EDPF_PROJECTION_SOURCE_HEAD_INVALID")
    return candidate


def _resolved_metadata(events: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    """Return immutable prediction metadata after validating open->resolved shape."""
    open_meta: dict[str, dict[str, str]] = {}
    resolved: dict[str, dict[str, str]] = {}
    for raw_event in events:
        if str(raw_event.get("event_type")) != "NODE_OBSERVED":
            continue
        node = dict(dict(raw_event.get("payload", {})).get("node", {}))
        if _kind(node.get("kind")) not in (NodeKind.EXPERIMENT.value, str(NodeKind.EXPERIMENT)):
            continue
        payload = dict(node.get("payload", {}))
        if payload.get("schema") != INTAKE_SCHEMA or not payload.get("prospective_capture"):
            continue
        prediction = dict(payload.get("prediction", {}))
        prediction_id = str(prediction.get("prediction_id", ""))
        if not prediction_id:
            raise ValueError("EDPF_PROJECTION_PREDICTION_ID_REQUIRED")
        provenance = dict(node.get("provenance", {}))
        metadata = {
            "system_source_head_sha": _sha40(str(payload.get("system_source_head_sha", ""))),
            "matter_scope": str(provenance.get("matter_scope", "GLOBAL")),
            "predictor_id": str(prediction.get("predictor_id", "")),
            "domain": str(prediction.get("domain", "")),
            "source_fingerprint": str(payload.get("predictor_source_fingerprint", "")),
            "predictor_version": str(payload.get("predictor_version", "")),
        }
        if any(not value.strip() for value in metadata.values()):
            raise ValueError("EDPF_PROJECTION_METADATA_REQUIRED")
        state = str(node.get("state", ""))
        if state == OPEN_STATE:
            if prediction_id in open_meta:
                raise ValueError("EDPF_PROJECTION_DUPLICATE_OPEN_PREDICTION")
            open_meta[prediction_id] = metadata
        elif state in (RESOLVED_TRUE_STATE, RESOLVED_FALSE_STATE):
            if prediction_id not in open_meta:
                raise ValueError("EDPF_PROJECTION_RESOLUTION_WITHOUT_OPEN")
            if metadata != open_meta[prediction_id]:
                raise ValueError("EDPF_PROJECTION_METADATA_MUTATED_AFTER_CUTOFF")
            resolved[prediction_id] = metadata
    return resolved


def _state(samples: int) -> EvidenceState:
    if samples <= 0:
        return EvidenceState.NEUTRAL_UNSEEN
    if samples < THIN_SAMPLE_FLOOR:
        return EvidenceState.THIN_PROSPECTIVE
    if samples < SHADOW_COUNT_FLOOR:
        return EvidenceState.OBSERVED_PROSPECTIVE
    return EvidenceState.SHADOW_COUNT_ELIGIBLE


def project_empirical_profiles(
    events: Sequence[Mapping[str, Any]],
    definitions: Sequence[PredictorDefinition],
) -> tuple[PredictorEvidenceProfile, ...]:
    """Project only resolved prospective evidence; unseen definitions are omitted.

    ``compile_real_shadow_pairs`` is called first so chronology, immutable
    prediction and evidence-separation rules remain single-sourced.
    """
    definitions = tuple(item.validate() for item in definitions)
    identity_map = {(item.predictor_id, item.source_fingerprint, item.predictor_version): item for item in definitions}
    if len(identity_map) != len(definitions):
        raise ValueError("EDPF_PROJECTION_DUPLICATE_DEFINITION")
    pairs = compile_real_shadow_pairs(events)
    metadata = _resolved_metadata(events)
    grouped: dict[tuple[str, str, str, str, str, str], list[Any]] = {}
    for pair in pairs:
        meta = metadata.get(pair.prediction.prediction_id)
        if meta is None:
            raise ValueError("EDPF_PROJECTION_PAIR_METADATA_MISSING")
        if pair.source_head_sha != meta["system_source_head_sha"]:
            raise ValueError("EDPF_PROJECTION_SOURCE_HEAD_MISMATCH")
        if pair.predictor_source_fingerprint != meta["source_fingerprint"]:
            raise ValueError("EDPF_PROJECTION_SOURCE_FINGERPRINT_MISMATCH")
        key = (
            meta["system_source_head_sha"], meta["matter_scope"], meta["predictor_id"],
            meta["domain"], meta["source_fingerprint"], meta["predictor_version"],
        )
        grouped.setdefault(key, []).append(pair)

    results: list[PredictorEvidenceProfile] = []
    for key, group in sorted(grouped.items()):
        head, matter, predictor_id, domain, fingerprint, version = key
        definition = identity_map.get((predictor_id, fingerprint, version))
        if definition is None or domain not in definition.supported_domains:
            continue
        profile = PredictorProfile(predictor_id=predictor_id, domain=domain)
        for pair in sorted(group, key=lambda item: (item.prediction_cutoff_epoch, item.pair_id)):
            profile = update_predictor(profile, pair.prediction, pair.outcome)
        samples = profile.attempts
        results.append(PredictorEvidenceProfile(
            schema=SCHEMA,
            system_source_head_sha=head,
            matter_scope=matter,
            predictor_id=predictor_id,
            domain=domain,
            source_fingerprint=fingerprint,
            predictor_version=version,
            resolved_samples=samples,
            evidence_state=_state(samples),
            profile=profile,
            empirical_trust_weight=profile.trust_weight,
            empirical_accuracy=profile.empirical_accuracy,
            empirical_calibration_error=profile.calibration_error,
            empirical_brier_score=profile.brier_score,
            provider_backed=definition.provider_backed,
            calibration_positive_proven=False,
            owner_value_proven=False,
            live_weight_change_authorized=False,
        ))
    return tuple(results)


def project_request_candidates(
    *,
    events: Sequence[Mapping[str, Any]],
    definitions: Sequence[PredictorDefinition],
    fits: Sequence[MissionPredictorFit],
    system_source_head_sha: str,
    matter_scope: str,
    domain: str,
) -> tuple[ProjectedPredictorCandidate, ...]:
    """Build request candidates using exact-epoch evidence or a neutral profile.

    Historical evidence from another source head, matter, version or source
    family never transfers implicitly. Unseen predictors receive the EDPF neutral
    ``PredictorProfile`` prior (trust weight 0.5), not a guessed competence score.
    """
    head = _sha40(system_source_head_sha)
    if not matter_scope.strip() or not domain.strip():
        raise ValueError("EDPF_PROJECTION_SCOPE_DOMAIN_REQUIRED")
    definitions = tuple(item.validate() for item in definitions)
    fits = tuple(item.validate() for item in fits)
    fit_map = {(item.predictor_id, item.domain): item for item in fits}
    if len(fit_map) != len(fits):
        raise ValueError("EDPF_PROJECTION_DUPLICATE_MISSION_FIT")
    empirical = project_empirical_profiles(events, definitions)
    evidence_map = {
        (item.system_source_head_sha, item.matter_scope, item.predictor_id, item.domain, item.source_fingerprint, item.predictor_version): item
        for item in empirical
    }
    projected: list[ProjectedPredictorCandidate] = []
    for definition in definitions:
        if domain not in definition.supported_domains:
            continue
        fit = fit_map.get((definition.predictor_id, domain))
        if fit is None:
            continue
        key = (head, matter_scope, definition.predictor_id, domain, definition.source_fingerprint, definition.predictor_version)
        evidence = evidence_map.get(key)
        neutral = evidence is None
        if neutral:
            profile = PredictorProfile(predictor_id=definition.predictor_id, domain=domain)
            evidence = PredictorEvidenceProfile(
                schema=SCHEMA,
                system_source_head_sha=head,
                matter_scope=matter_scope,
                predictor_id=definition.predictor_id,
                domain=domain,
                source_fingerprint=definition.source_fingerprint,
                predictor_version=definition.predictor_version,
                resolved_samples=0,
                evidence_state=EvidenceState.NEUTRAL_UNSEEN,
                profile=profile,
                empirical_trust_weight=profile.trust_weight,
                empirical_accuracy=profile.empirical_accuracy,
                empirical_calibration_error=profile.calibration_error,
                empirical_brier_score=profile.brier_score,
                provider_backed=definition.provider_backed,
                calibration_positive_proven=False,
                owner_value_proven=False,
                live_weight_change_authorized=False,
            )
        candidate = PredictorCandidate(
            predictor_id=definition.predictor_id,
            source_fingerprint=definition.source_fingerprint,
            predictor_version=definition.predictor_version,
            profile=evidence.profile,
            relevance=fit.relevance,
            independence=fit.independence,
            expected_information_gain=fit.expected_information_gain,
            cost=fit.cost,
            latency=fit.latency,
            provider_backed=definition.provider_backed,
        ).validate(domain=domain)
        projected.append(ProjectedPredictorCandidate(
            definition=definition,
            fit=fit,
            evidence=evidence,
            candidate=candidate,
            neutral_fallback_used=neutral,
        ))
    return tuple(sorted(projected, key=lambda item: (-item.candidate.allocation_weight(), item.definition.predictor_id)))


__all__ = [
    "SCHEMA", "EvidenceState", "PredictorDefinition", "MissionPredictorFit",
    "PredictorEvidenceProfile", "ProjectedPredictorCandidate",
    "project_empirical_profiles", "project_request_candidates",
]
