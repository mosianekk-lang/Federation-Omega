"""Provider-neutral multi-intelligence formation compiler for FUSE V2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Sequence

from .core import digest


class FormationMode(str, Enum):
    FAST = "FAST"
    FUSION = "FUSION"
    ADVERSARIAL = "ADVERSARIAL"
    FORMATION = "FORMATION"
    DEEP = "DEEP"
    LIVE = "LIVE"
    CHAMPION_TOURNAMENT = "CHAMPION_TOURNAMENT"


@dataclass(frozen=True)
class IntelligenceCandidate:
    cell_id: str
    provider: str
    model_ref: str
    capabilities: tuple[str, ...]
    correlation_domains: tuple[str, ...]
    authority_pass: bool
    privacy_pass: bool
    currentness_pass: bool
    capability_pass: bool
    budget_pass: bool
    proof_floor_pass: bool
    recovery_pass: bool
    quality: float = 0.0
    reliability: float = 0.0
    latency_ms: float = 0.0
    cost: float = 0.0
    owner_burden: float = 0.0

    @property
    def hard_gates_pass(self) -> bool:
        return all(
            (
                self.authority_pass,
                self.privacy_pass,
                self.currentness_pass,
                self.capability_pass,
                self.budget_pass,
                self.proof_floor_pass,
                self.recovery_pass,
            )
        )

    def supports(self, required: Iterable[str]) -> bool:
        need = set(required)
        return need.issubset(set(self.capabilities))


@dataclass(frozen=True)
class IntelligenceFormationPlan:
    plan_id: str
    mission_id: str
    mode: str
    required_capabilities: tuple[str, ...]
    selected_cell_ids: tuple[str, ...]
    independence_pass: bool
    judge_required: bool
    truth_boundary: str

    def to_dict(self) -> dict:
        return asdict(self)


class IntelligenceFormationCompiler:
    TRUTH_BOUNDARY = (
        "FORMATION_COMPILED!=PROVIDERS_EXECUTED!=SEMANTIC_READBACK"
        "!=INDEPENDENT_JUDGE!=OWNER_VALUE!=COMPLETE"
    )

    @staticmethod
    def _score(c: IntelligenceCandidate) -> tuple[float, float, float, float, str]:
        # Deterministic lexicographic preference. No single scalar can erase
        # a hard quality or recovery floor.
        return (
            c.quality,
            c.reliability,
            -c.latency_ms,
            -(c.cost + c.owner_burden),
            c.cell_id,
        )

    @classmethod
    def compile(
        cls,
        *,
        mission_id: str,
        mode: FormationMode | str,
        required_capabilities: Iterable[str],
        candidates: Sequence[IntelligenceCandidate],
        judge_required: bool = True,
    ) -> IntelligenceFormationPlan:
        if not mission_id.strip():
            raise ValueError("FORMATION_MISSION_ID_REQUIRED")
        try:
            normalized_mode = FormationMode(mode)
        except ValueError as exc:
            raise ValueError("FORMATION_MODE_UNSUPPORTED") from exc

        required = tuple(sorted(set(required_capabilities)))
        eligible = [
            c
            for c in candidates
            if c.hard_gates_pass and c.supports(required)
        ]
        if not eligible:
            raise ValueError("NO_ELIGIBLE_INTELLIGENCE_CANDIDATE")

        eligible = sorted(eligible, key=cls._score, reverse=True)

        if normalized_mode is FormationMode.FAST:
            selected = eligible[:1]
        elif normalized_mode in {
            FormationMode.FUSION,
            FormationMode.ADVERSARIAL,
            FormationMode.CHAMPION_TOURNAMENT,
        }:
            if len(eligible) < 2:
                raise ValueError("FORMATION_REQUIRES_TWO_CANDIDATES")
            selected = []
            seen_domains: set[tuple[str, ...]] = set()
            seen_providers: set[str] = set()
            for candidate in eligible:
                domains = tuple(sorted(candidate.correlation_domains))
                if not selected:
                    selected.append(candidate)
                    seen_domains.add(domains)
                    seen_providers.add(candidate.provider)
                    continue
                if domains not in seen_domains or candidate.provider not in seen_providers:
                    selected.append(candidate)
                    break
            if len(selected) < 2:
                raise ValueError("FORMATION_INDEPENDENCE_NOT_PROVEN")
        else:
            selected = eligible

        independence_pass = True
        if len(selected) > 1:
            signatures = {
                (c.provider, tuple(sorted(c.correlation_domains))) for c in selected
            }
            independence_pass = len(signatures) == len(selected)

        if normalized_mode in {
            FormationMode.FUSION,
            FormationMode.ADVERSARIAL,
            FormationMode.CHAMPION_TOURNAMENT,
        } and not independence_pass:
            raise ValueError("FORMATION_INDEPENDENCE_NOT_PROVEN")

        stable = {
            "mission_id": mission_id.strip(),
            "mode": normalized_mode.value,
            "required_capabilities": required,
            "selected": [c.cell_id for c in selected],
            "independence_pass": independence_pass,
            "judge_required": bool(judge_required),
        }
        return IntelligenceFormationPlan(
            plan_id=f"FUSE-FORMATION-V2-{digest(stable)[:24].upper()}",
            mission_id=mission_id.strip(),
            mode=normalized_mode.value,
            required_capabilities=required,
            selected_cell_ids=tuple(c.cell_id for c in selected),
            independence_pass=independence_pass,
            judge_required=bool(judge_required),
            truth_boundary=cls.TRUTH_BOUNDARY,
        )
