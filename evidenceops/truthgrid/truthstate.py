from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .vnext import DecisionReadiness, TruthState


SOURCE_CONFIDENCE_CEILINGS: Mapping[str, float] = {
    "PROVIDER_NATIVE_ORIGINAL": 1.00,
    "AUTHENTICATED_INSTITUTIONAL_RECORD": 0.95,
    "ARCHIVED_NATIVE_COPY": 0.90,
    "EXTRACTED_PRIMARY_ADJACENT_TEXT": 0.84,
    "DERIVATIVE_SUMMARY": 0.75,
    "PARTY_GENERATED_ANALYSIS": 0.60,
    "AI_INFERENCE": 0.40,
}


@dataclass(frozen=True)
class EvidenceSignal:
    source_id: str
    source_class: str
    supports: bool
    quality: float
    independence: float
    authority_ok: bool = True
    temporal_ok: bool = True
    attribution_ok: bool = True
    superseded: bool = False
    invalidated: bool = False

    def strength(self) -> float:
        if self.superseded or self.invalidated:
            return 0.0
        value = max(0.0, min(self.quality, 1.0)) * max(0.0, min(self.independence, 1.0))
        value *= 1.0 if self.authority_ok else 0.55
        value *= 1.0 if self.temporal_ok else 0.45
        value *= 1.0 if self.attribution_ok else 0.35
        return value


@dataclass(frozen=True)
class Proposition:
    proposition_id: str
    evidence: tuple[EvidenceSignal, ...] = ()
    missing_dependencies: tuple[str, ...] = ()
    external_production_required: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    search_exhausted: bool = False
    superseded_by: str | None = None


@dataclass(frozen=True)
class Assessment:
    state: TruthState
    confidence: float
    ceiling: float
    readiness: DecisionReadiness
    supporting_sources: tuple[str, ...]
    adverse_sources: tuple[str, ...]


def assess(prop: Proposition) -> Assessment:
    if prop.superseded_by:
        return Assessment(TruthState.SUPERSEDED, 0.0, 0.0, DecisionReadiness.NOT_READY, (), ())
    valid = tuple(s for s in prop.evidence if not s.invalidated and not s.superseded)
    support = tuple(s for s in valid if s.supports)
    adverse = tuple(s for s in valid if not s.supports)
    ceiling = max((SOURCE_CONFIDENCE_CEILINGS.get(s.source_class, 0.50) for s in valid), default=0.0)
    support_strength = max((s.strength() for s in support), default=0.0)
    adverse_strength = max((s.strength() for s in adverse), default=0.0)
    confidence = min(max(0.0, support_strength - 0.70 * adverse_strength), ceiling)
    limited = bool(prop.missing_dependencies or prop.external_production_required or prop.contradiction_ids)
    if not valid and prop.external_production_required:
        state = TruthState.PRODUCTION_REQUIRED
    elif not valid and prop.search_exhausted:
        state = TruthState.NOT_LOCATED
    elif adverse_strength > support_strength and adverse_strength > 0.45:
        state = TruthState.CONTRADICTED
    elif support_strength > 0.80 and not limited:
        state = TruthState.PROVED
    elif support_strength > 0.65:
        state = TruthState.PROVED_WITH_LIMITATION if limited else TruthState.SUPPORTED
    elif support and adverse:
        state = TruthState.CONTESTED
    elif support:
        state = TruthState.SUPPORTED
    else:
        state = TruthState.UNRESOLVED
    if state == TruthState.PROVED:
        readiness = DecisionReadiness.READY
    elif state in {TruthState.PROVED_WITH_LIMITATION, TruthState.SUPPORTED, TruthState.CONTESTED}:
        readiness = DecisionReadiness.CONDITIONAL
    else:
        readiness = DecisionReadiness.NOT_READY
    return Assessment(state, round(confidence, 6), ceiling, readiness, tuple(s.source_id for s in support), tuple(s.source_id for s in adverse))
