from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


def _sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class EngineeringShape(str, Enum):
    DIRECT = "DIRECT"
    PLAN_ACT = "PLAN_ACT"
    FLEET = "FLEET"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class MissionProfile:
    mission_id: str
    changed_paths: tuple[str, ...] = ()
    subsystems: tuple[str, ...] = ()
    risk: str = "MEDIUM"
    unknown_count: int = 0
    estimated_tasks: int = 1
    external_effects: bool = False
    authority_ready: bool = True
    independent_verification_required: bool = True

    def validate(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if self.risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("MISSION_RISK_INVALID")
        if self.unknown_count < 0 or self.estimated_tasks < 1:
            raise ValueError("MISSION_COMPLEXITY_INVALID")


@dataclass(frozen=True, slots=True)
class ShapeDecision:
    mission_id: str
    shape: EngineeringShape
    reasons: tuple[str, ...]
    mutation_allowed_by_shape: bool
    decision_sha256: str


@dataclass(frozen=True, slots=True)
class EngineeringOpportunity:
    opportunity_id: str
    description: str
    expected_value: float
    urgency: float
    unlock_value: float
    proof_readiness: float
    risk: float
    owner_burden: float
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.opportunity_id.strip() or not self.description.strip():
            raise ValueError("OPPORTUNITY_IDENTITY_REQUIRED")
        for name in ("expected_value", "urgency", "unlock_value", "proof_readiness", "risk", "owner_burden"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name.upper()}_OUTSIDE_UNIT_INTERVAL")
        if self.proof_readiness > 0.0 and not self.evidence_refs:
            raise ValueError("PROOF_READY_OPPORTUNITY_REQUIRES_EVIDENCE")


@dataclass(frozen=True, slots=True)
class OpportunityRanking:
    opportunity_ids: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]
    ranking_sha256: str


class EngineeringOpportunityAdapter:
    """Chooses engineering shape and ranks the next bounded opportunity.

    This is a no-effect selection layer. It does not execute repository/provider
    mutations and does not grant authority. Missing authority therefore produces
    HOLD rather than an attempted side effect.
    """

    def choose_shape(self, profile: MissionProfile) -> ShapeDecision:
        profile.validate()
        paths = _clean(profile.changed_paths)
        subsystems = _clean(profile.subsystems)
        reasons: list[str] = []

        if profile.external_effects and not profile.authority_ready:
            shape = EngineeringShape.HOLD
            reasons.append("EXTERNAL_EFFECT_AUTHORITY_NOT_READY")
        elif (
            profile.risk == "CRITICAL"
            or profile.estimated_tasks >= 6
            or len(paths) >= 12
            or len(subsystems) >= 3
        ):
            shape = EngineeringShape.FLEET
            if profile.risk == "CRITICAL":
                reasons.append("CRITICAL_RISK")
            if profile.estimated_tasks >= 6:
                reasons.append("MULTI_TASK_MISSION")
            if len(paths) >= 12:
                reasons.append("WIDE_PATH_SURFACE")
            if len(subsystems) >= 3:
                reasons.append("MULTI_SUBSYSTEM_MISSION")
        elif (
            profile.risk in {"LOW", "MEDIUM"}
            and profile.estimated_tasks <= 2
            and len(paths) <= 3
            and len(subsystems) <= 1
            and profile.unknown_count == 0
            and not profile.external_effects
        ):
            shape = EngineeringShape.DIRECT
            reasons.append("SMALL_BOUNDED_KNOWN_CHANGE")
        else:
            shape = EngineeringShape.PLAN_ACT
            if profile.risk == "HIGH":
                reasons.append("HIGH_RISK_REQUIRES_PLAN")
            if profile.unknown_count:
                reasons.append("UNKNOWNS_REQUIRE_PLAN")
            if profile.independent_verification_required:
                reasons.append("INDEPENDENT_VERIFICATION_REQUIRED")
            if not reasons:
                reasons.append("BOUNDED_PLAN_ACT_DEFAULT")

        body = {
            "mission_id": profile.mission_id,
            "paths": paths,
            "subsystems": subsystems,
            "risk": profile.risk,
            "unknown_count": profile.unknown_count,
            "estimated_tasks": profile.estimated_tasks,
            "external_effects": profile.external_effects,
            "authority_ready": profile.authority_ready,
            "independent_verification_required": profile.independent_verification_required,
            "shape": shape.value,
            "reasons": tuple(sorted(set(reasons))),
        }
        return ShapeDecision(
            mission_id=profile.mission_id,
            shape=shape,
            reasons=tuple(sorted(set(reasons))),
            mutation_allowed_by_shape=shape != EngineeringShape.HOLD,
            decision_sha256=_sha(body),
        )

    @staticmethod
    def _opportunity_score(row: EngineeringOpportunity) -> float:
        row.validate()
        score = (
            0.32 * row.expected_value
            + 0.22 * row.urgency
            + 0.22 * row.unlock_value
            + 0.16 * row.proof_readiness
            - 0.05 * row.risk
            - 0.03 * row.owner_burden
        )
        return round(score, 8)

    def rank(self, opportunities: Sequence[EngineeringOpportunity], *, limit: int = 10) -> OpportunityRanking:
        if limit < 1:
            raise ValueError("OPPORTUNITY_LIMIT_INVALID")
        by_id: dict[str, EngineeringOpportunity] = {}
        for row in opportunities:
            row.validate()
            if row.opportunity_id in by_id:
                raise ValueError("DUPLICATE_OPPORTUNITY_ID")
            by_id[row.opportunity_id] = row
        ranked = sorted(
            ((row.opportunity_id, self._opportunity_score(row)) for row in opportunities),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
        body = {
            "ranked": ranked,
            "evidence": tuple(sorted((row.opportunity_id, _clean(row.evidence_refs)) for row in opportunities)),
        }
        return OpportunityRanking(
            opportunity_ids=tuple(item[0] for item in ranked),
            scores=tuple(ranked),
            ranking_sha256=_sha(body),
        )


__all__ = [
    "EngineeringOpportunity",
    "EngineeringOpportunityAdapter",
    "EngineeringShape",
    "MissionProfile",
    "OpportunityRanking",
    "ShapeDecision",
]
