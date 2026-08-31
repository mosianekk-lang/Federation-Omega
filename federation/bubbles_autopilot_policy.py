"""Bubbles digital-twin autopilot policy.

This module reduces routine owner interruption without creating a second
scheduler, provider executor, or authority layer.

It answers two bounded questions:
1. Can a work step continue without asking the owner again?
2. How should a capability candidate be ranked using the canonical CFBE
   mission-impact/dependency-leverage/value/unblock/effort formula?

Execution remains with the existing Federation/CFBE/Bubbles work fabric.
Provider effects still require route-specific authority and readback.
High-consequence decisions always remain owner-gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


NO_EFFECT = "NO_EFFECT"
REVERSIBLE_INTERNAL = "REVERSIBLE_INTERNAL"
REVERSIBLE_EXTERNAL = "REVERSIBLE_EXTERNAL"
HIGH_CONSEQUENCE = "HIGH_CONSEQUENCE"

_ALLOWED_EFFECT_CLASSES = frozenset(
    {NO_EFFECT, REVERSIBLE_INTERNAL, REVERSIBLE_EXTERNAL, HIGH_CONSEQUENCE}
)


@dataclass(frozen=True, slots=True)
class AutopilotStep:
    step_id: str
    effect_class: str
    blocked: bool = False
    alternate_route_available: bool = False
    authority_proven: bool = False
    provider_readback_available: bool = False
    owner_choice_required: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.step_id.strip():
            raise ValueError("AUTOPILOT_STEP_ID_REQUIRED")
        if self.effect_class not in _ALLOWED_EFFECT_CLASSES:
            raise ValueError("AUTOPILOT_EFFECT_CLASS_INVALID")
        if self.alternate_route_available and not self.blocked:
            raise ValueError("AUTOPILOT_ALTERNATE_ROUTE_REQUIRES_BLOCKED_STEP")


@dataclass(frozen=True, slots=True)
class AutopilotDecision:
    state: str
    continue_without_owner: bool
    owner_interrupt_required: bool
    step_id: str
    reason: str
    proof_refs: tuple[str, ...]


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def decide_autopilot(step: AutopilotStep) -> AutopilotDecision:
    """Apply the Creative Focus Shield to one already-selected work step.

    This function does not select, allocate or execute work. The existing CFBE
    scheduler remains authoritative for mission ordering and Bubbles remains
    bounded by provider/owner authority.

    Routine safe work continues without an owner prompt. A blocked lane with a
    known alternate route is isolated and rerouted without interrupting the
    owner. External work can continue only when pre-existing authority and a
    provider-native readback route are both proven. High-consequence actions
    and irreducible owner choices always interrupt.
    """

    step.validate()
    refs = _clean_refs(step.proof_refs)

    if step.effect_class == HIGH_CONSEQUENCE:
        return AutopilotDecision(
            state="ESCALATE_OWNER_HIGH_CONSEQUENCE",
            continue_without_owner=False,
            owner_interrupt_required=True,
            step_id=step.step_id,
            reason="High-consequence actions remain explicitly owner-gated.",
            proof_refs=refs,
        )

    if step.owner_choice_required:
        return AutopilotDecision(
            state="ESCALATE_OWNER_IRREDUCIBLE_CHOICE",
            continue_without_owner=False,
            owner_interrupt_required=True,
            step_id=step.step_id,
            reason="The remaining decision is an irreducible owner choice, not routine orchestration.",
            proof_refs=refs,
        )

    if step.blocked and step.alternate_route_available:
        return AutopilotDecision(
            state="ISOLATE_BLOCKED_LANE_AND_REROUTE",
            continue_without_owner=True,
            owner_interrupt_required=False,
            step_id=step.step_id,
            reason="Anti-stall policy isolates the blocked lane and continues through a known alternate route.",
            proof_refs=refs,
        )

    if step.blocked:
        return AutopilotDecision(
            state="ESCALATE_OWNER_NO_EXECUTABLE_ROUTE",
            continue_without_owner=False,
            owner_interrupt_required=True,
            step_id=step.step_id,
            reason="No executable alternate route remains; owner input or new authority is materially required.",
            proof_refs=refs,
        )

    if step.effect_class in {NO_EFFECT, REVERSIBLE_INTERNAL}:
        return AutopilotDecision(
            state="CONTINUE_AUTONOMOUSLY",
            continue_without_owner=True,
            owner_interrupt_required=False,
            step_id=step.step_id,
            reason="Safe internal/reversible work may continue without routine owner approval.",
            proof_refs=refs,
        )

    if step.effect_class == REVERSIBLE_EXTERNAL:
        if step.authority_proven and step.provider_readback_available:
            return AutopilotDecision(
                state="CONTINUE_EXTERNAL_WITH_READBACK",
                continue_without_owner=True,
                owner_interrupt_required=False,
                step_id=step.step_id,
                reason="Existing authority and provider-native readback are both proven; continue within that bounded authority.",
                proof_refs=refs,
            )
        missing = []
        if not step.authority_proven:
            missing.append("authority")
        if not step.provider_readback_available:
            missing.append("provider readback")
        return AutopilotDecision(
            state="ESCALATE_OWNER_EXTERNAL_GATE",
            continue_without_owner=False,
            owner_interrupt_required=True,
            step_id=step.step_id,
            reason="Reversible external action is held because " + " and ".join(missing) + " are not proven.",
            proof_refs=refs,
        )

    raise AssertionError("UNREACHABLE_AUTOPILOT_EFFECT_CLASS")


@dataclass(frozen=True, slots=True)
class CFBECapabilityCandidate:
    capability_id: str
    mission_impact: float
    dependency_leverage: float
    expected_value: float
    unblock_value: float
    expected_effort: float

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("CFBE_CAPABILITY_ID_REQUIRED")
        for label, value in (
            ("MISSION_IMPACT", self.mission_impact),
            ("DEPENDENCY_LEVERAGE", self.dependency_leverage),
            ("EXPECTED_VALUE", self.expected_value),
            ("UNBLOCK_VALUE", self.unblock_value),
        ):
            if float(value) < 0.0:
                raise ValueError(f"CFBE_{label}_NON_NEGATIVE_REQUIRED")
        if float(self.expected_effort) <= 0.0:
            raise ValueError("CFBE_EXPECTED_EFFORT_POSITIVE_REQUIRED")


def cfbe_rank(candidate: CFBECapabilityCandidate) -> float:
    """Return the canonical CFBE priority score without granting promotion."""

    candidate.validate()
    return (
        float(candidate.mission_impact)
        * float(candidate.dependency_leverage)
        * float(candidate.expected_value)
        * float(candidate.unblock_value)
        / float(candidate.expected_effort)
    )


@dataclass(frozen=True, slots=True)
class CreativeFocusShield:
    """Owner-interruption policy for Bubbles' digital-twin direction."""

    routine_safe_work_requires_owner_prompt: bool = False
    blocked_lane_with_alternate_requires_owner_prompt: bool = False
    reversible_external_requires_proven_authority: bool = True
    reversible_external_requires_provider_readback: bool = True
    high_consequence_requires_owner_prompt: bool = True
    irreducible_owner_choice_requires_owner_prompt: bool = True

    @property
    def truth_boundary(self) -> str:
        return (
            "The shield reduces routine prompts; it does not create background execution, "
            "provider authority, irreversible-action authority, or AGI."
        )


DEFAULT_CREATIVE_FOCUS_SHIELD = CreativeFocusShield()
