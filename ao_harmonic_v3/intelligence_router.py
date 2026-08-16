from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Mapping

from .cost_governor import (
    CostAction,
    CostClass,
    CostDecision,
    CostEnvelope,
    PreRevenueCostGovernor,
    WorkloadCostProfile,
)


class IntelligenceTier(str, Enum):
    INSTANT = "INSTANT"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTRA_HIGH = "EXTRA_HIGH"
    PRO = "PRO"


_TIER_ORDER = (
    IntelligenceTier.INSTANT,
    IntelligenceTier.MEDIUM,
    IntelligenceTier.HIGH,
    IntelligenceTier.EXTRA_HIGH,
    IntelligenceTier.PRO,
)
_TIER_INDEX = {tier: index for index, tier in enumerate(_TIER_ORDER)}


@dataclass(frozen=True)
class IntelligenceSignals:
    task_id: str
    complexity: float = 0.5
    consequence: float = 0.5
    uncertainty: float = 0.5
    dependency_density: float = 0.5
    adversarial_complexity: float = 0.5
    evidence_volume: float = 0.3
    ambiguity: float = 0.4
    irreversibility: float = 0.3
    long_horizon: float = 0.4
    required_accuracy: float = 0.8
    high_stakes: bool = False
    legal_or_regulatory: bool = False
    repeated_failures: int = 0
    unresolved_contradictions: int = 0
    requested_tier: IntelligenceTier | None = None


@dataclass(frozen=True)
class IntelligenceAssessment:
    router_id: str
    task_id: str
    score: float
    desired_tier: IntelligenceTier
    minimum_tier: IntelligenceTier
    horizon_pressure: float
    reasons: tuple[str, ...]
    escalation_triggers: tuple[str, ...]
    deescalation_allowed: bool
    truth_class: str = "ROUTING_CONTROL_STATE_NOT_QUALITY_FACT"


@dataclass(frozen=True)
class ProviderIntelligenceBinding:
    binding_id: str
    provider: str
    surface: str
    tier: IntelligenceTier
    model: str
    reasoning_effort: str | None = None
    reasoning_mode: str | None = None
    available: bool = True
    authorised: bool = True
    programmatic: bool = True
    cost_class: CostClass = CostClass.C2_CONTROLLED_PAID
    estimated_monthly_cost: float | None = None
    current_month_spend: float = 0.0
    already_paid_or_included: bool = False
    event_driven: bool = True
    scale_to_zero: bool = True
    hard_cap_or_quota_available: bool = False
    notes: str = ""


@dataclass(frozen=True)
class IntelligenceRouteDecision:
    router_id: str
    task_id: str
    assessment: IntelligenceAssessment
    selected_binding: ProviderIntelligenceBinding | None
    cost_decision: CostDecision | None
    state: str
    degraded_for_cost: bool
    owner_approval_required: bool
    execution_allowed: bool
    chatgpt_ui_recommendation: str
    provider_request: dict[str, object]
    reasons: tuple[str, ...]
    truth_class: str = "ROUTING_DECISION_NOT_EXECUTION_PROOF"


@dataclass(frozen=True)
class IntelligenceFeedback:
    quality_score: float | None = None
    success: bool | None = None
    unresolved_contradictions: int = 0
    repeated_failure: bool = False
    material_new_dependency: bool = False
    material_consequence_increase: bool = False
    stable_successes: int = 0


@dataclass(frozen=True)
class RouterOutcome:
    selected_tier: IntelligenceTier
    quality_score: float
    required_accuracy: float
    escalation_was_needed: bool = False
    lower_tier_would_have_sufficed: bool = False


class OpenAI56BindingCatalog:
    """Current GPT-5.6 control bindings, separated from logical routing.

    ChatGPT and API bindings deliberately remain distinct. ChatGPT tier choices
    are recommendation-only here because this library cannot mutate the user's
    visible model picker. Responses API bindings are executable only after the
    caller separately proves API authority and Cost Governor approval.
    """

    MODEL = "gpt-5.6"

    @classmethod
    def chatgpt(cls, tier: IntelligenceTier) -> ProviderIntelligenceBinding:
        return ProviderIntelligenceBinding(
            binding_id=f"OPENAI_CHATGPT_{tier.value}",
            provider="OPENAI",
            surface="CHATGPT_UI",
            tier=tier,
            model="GPT-5.5 Instant" if tier is IntelligenceTier.INSTANT else (
                "GPT-5.6 Sol Pro" if tier is IntelligenceTier.PRO else "GPT-5.6 Sol"
            ),
            reasoning_effort={
                IntelligenceTier.INSTANT: None,
                IntelligenceTier.MEDIUM: "medium",
                IntelligenceTier.HIGH: "high",
                IntelligenceTier.EXTRA_HIGH: "xhigh",
                IntelligenceTier.PRO: None,
            }[tier],
            reasoning_mode="pro" if tier is IntelligenceTier.PRO else None,
            programmatic=False,
            cost_class=CostClass.C0_INCLUDED_FREE,
            estimated_monthly_cost=0.0,
            already_paid_or_included=True,
            notes="Recommendation-only ChatGPT picker binding; availability remains plan/workspace dependent.",
        )

    @classmethod
    def responses_api(
        cls,
        tier: IntelligenceTier,
        *,
        estimated_monthly_cost: float | None = None,
        already_paid_or_included: bool = False,
        available: bool = True,
        authorised: bool = True,
    ) -> ProviderIntelligenceBinding:
        effort = {
            IntelligenceTier.INSTANT: "low",
            IntelligenceTier.MEDIUM: "medium",
            IntelligenceTier.HIGH: "high",
            IntelligenceTier.EXTRA_HIGH: "xhigh",
            IntelligenceTier.PRO: None,
        }[tier]
        return ProviderIntelligenceBinding(
            binding_id=f"OPENAI_RESPONSES_{tier.value}",
            provider="OPENAI",
            surface="RESPONSES_API",
            tier=tier,
            model=cls.MODEL,
            reasoning_effort=effort,
            reasoning_mode="pro" if tier is IntelligenceTier.PRO else None,
            available=available,
            authorised=authorised,
            programmatic=True,
            cost_class=CostClass.C2_CONTROLLED_PAID if tier in {IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO} else CostClass.C1_MICRO_SERVERLESS,
            estimated_monthly_cost=estimated_monthly_cost,
            already_paid_or_included=already_paid_or_included,
            event_driven=True,
            scale_to_zero=True,
            notes="Responses API binding; caller must supply live cost/authority state before execution.",
        )


class AdaptiveIntelligenceRouter:
    ROUTER_ID = "ADAPTIVE-INTELLIGENCE-ROUTER-V1"

    WEIGHTS = {
        "complexity": 0.18,
        "consequence": 0.17,
        "uncertainty": 0.12,
        "dependency_density": 0.11,
        "adversarial_complexity": 0.11,
        "evidence_volume": 0.08,
        "ambiguity": 0.08,
        "irreversibility": 0.07,
        "long_horizon": 0.05,
        "required_accuracy": 0.03,
    }

    def __init__(self, *, cost_governor: PreRevenueCostGovernor | None = None) -> None:
        self.cost = cost_governor or PreRevenueCostGovernor()

    @staticmethod
    def _unit(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _tier_max(a: IntelligenceTier, b: IntelligenceTier) -> IntelligenceTier:
        return a if _TIER_INDEX[a] >= _TIER_INDEX[b] else b

    @staticmethod
    def _tier_step(tier: IntelligenceTier, delta: int) -> IntelligenceTier:
        return _TIER_ORDER[max(0, min(len(_TIER_ORDER) - 1, _TIER_INDEX[tier] + delta))]

    def _score(self, signals: IntelligenceSignals) -> float:
        return sum(
            self.WEIGHTS[name] * self._unit(getattr(signals, name))
            for name in self.WEIGHTS
        )

    def _base_tier(self, score: float) -> IntelligenceTier:
        if score < 0.28:
            return IntelligenceTier.INSTANT
        if score < 0.46:
            return IntelligenceTier.MEDIUM
        if score < 0.65:
            return IntelligenceTier.HIGH
        if score < 0.80:
            return IntelligenceTier.EXTRA_HIGH
        return IntelligenceTier.PRO

    def assess(self, signals: IntelligenceSignals) -> IntelligenceAssessment:
        score = self._score(signals)
        desired = self._base_tier(score)
        minimum = IntelligenceTier.INSTANT
        reasons: list[str] = [f"weighted_task_pressure={score:.3f}"]

        if signals.high_stakes or signals.legal_or_regulatory:
            minimum = self._tier_max(minimum, IntelligenceTier.HIGH)
            reasons.append("high-stakes/legal floor=HIGH")
        if self._unit(signals.consequence) >= 0.85 and (
            self._unit(signals.uncertainty) >= 0.65
            or self._unit(signals.irreversibility) >= 0.70
            or self._unit(signals.adversarial_complexity) >= 0.75
        ):
            minimum = self._tier_max(minimum, IntelligenceTier.EXTRA_HIGH)
            reasons.append("high-consequence uncertainty/irreversibility/adversarial floor=EXTRA_HIGH")
        if (
            signals.repeated_failures >= 3
            and self._unit(signals.consequence) >= 0.60
        ) or (
            signals.unresolved_contradictions >= 3
            and (signals.high_stakes or self._unit(signals.consequence) >= 0.75)
        ):
            minimum = self._tier_max(minimum, IntelligenceTier.PRO)
            reasons.append("repeated-failure/contradiction floor=PRO")

        desired = self._tier_max(desired, minimum)
        if signals.requested_tier is not None:
            desired = self._tier_max(desired, signals.requested_tier)
            reasons.append(f"explicit_requested_floor={signals.requested_tier.value}")

        horizon_pressure = self._unit(
            0.35 * self._unit(signals.consequence)
            + 0.25 * self._unit(signals.uncertainty)
            + 0.20 * self._unit(signals.dependency_density)
            + 0.20 * self._unit(signals.adversarial_complexity)
        )
        escalation = (
            "QUALITY_BELOW_REQUIRED_ACCURACY",
            "UNRESOLVED_CONTRADICTION",
            "REPEATED_ROUTE_OR_MODEL_FAILURE",
            "MATERIAL_NEW_DEPENDENCY",
            "MATERIAL_CONSEQUENCE_INCREASE",
        )
        deescalation_allowed = not signals.high_stakes and self._unit(signals.consequence) < 0.70
        return IntelligenceAssessment(
            router_id=self.ROUTER_ID,
            task_id=signals.task_id,
            score=round(score, 6),
            desired_tier=desired,
            minimum_tier=minimum,
            horizon_pressure=round(horizon_pressure, 6),
            reasons=tuple(reasons),
            escalation_triggers=escalation,
            deescalation_allowed=deescalation_allowed,
        )

    def reassess(self, signals: IntelligenceSignals, feedback: IntelligenceFeedback) -> IntelligenceAssessment:
        current = self.assess(signals)
        desired = current.desired_tier
        reasons = list(current.reasons)
        quality = None if feedback.quality_score is None else self._unit(feedback.quality_score)
        required = self._unit(signals.required_accuracy)

        hard_escalate = bool(
            feedback.repeated_failure
            or feedback.unresolved_contradictions > 0
            or feedback.material_new_dependency
            or feedback.material_consequence_increase
            or (quality is not None and quality < required)
            or feedback.success is False
        )
        if hard_escalate:
            steps = 2 if (feedback.repeated_failure and feedback.unresolved_contradictions > 0) else 1
            desired = self._tier_step(desired, steps)
            reasons.append(f"feedback_escalation=+{steps}")
        elif feedback.stable_successes >= 3 and current.deescalation_allowed and quality is not None and quality >= max(required, 0.90):
            desired = self._tier_step(desired, -1)
            reasons.append("stable_high-quality_feedback_deescalation=-1")

        desired = self._tier_max(desired, current.minimum_tier)
        return IntelligenceAssessment(
            router_id=current.router_id,
            task_id=current.task_id,
            score=current.score,
            desired_tier=desired,
            minimum_tier=current.minimum_tier,
            horizon_pressure=current.horizon_pressure,
            reasons=tuple(reasons),
            escalation_triggers=current.escalation_triggers,
            deescalation_allowed=current.deescalation_allowed,
        )

    @staticmethod
    def provider_request(binding: ProviderIntelligenceBinding | None) -> dict[str, object]:
        if binding is None:
            return {}
        request: dict[str, object] = {"provider": binding.provider, "surface": binding.surface, "model": binding.model}
        if binding.reasoning_effort:
            request["reasoning"] = {"effort": binding.reasoning_effort}
        if binding.reasoning_mode:
            request["reasoning"] = {"mode": binding.reasoning_mode}
        return request

    def _cost_decision(self, binding: ProviderIntelligenceBinding, envelope: CostEnvelope | None) -> CostDecision:
        return self.cost.evaluate(
            WorkloadCostProfile(
                workload_id=f"AIR::{binding.binding_id}",
                cost_class=binding.cost_class,
                estimated_monthly_cost=binding.estimated_monthly_cost,
                current_month_spend=binding.current_month_spend,
                already_paid_or_included=binding.already_paid_or_included,
                event_driven=binding.event_driven,
                scale_to_zero=binding.scale_to_zero,
                hard_cap_or_quota_available=binding.hard_cap_or_quota_available,
                essential=False,
                owner_approved=False,
                notes=binding.notes,
            ),
            envelope,
        )

    def route(
        self,
        signals: IntelligenceSignals,
        bindings: Iterable[ProviderIntelligenceBinding],
        *,
        envelope: CostEnvelope | None = None,
        assessment: IntelligenceAssessment | None = None,
    ) -> IntelligenceRouteDecision:
        assessment = assessment or self.assess(signals)
        viable = [binding for binding in bindings if binding.available and binding.authorised]
        viable.sort(key=lambda binding: _TIER_INDEX[binding.tier], reverse=True)
        desired_index = _TIER_INDEX[assessment.desired_tier]
        minimum_index = _TIER_INDEX[assessment.minimum_tier]
        reasons = list(assessment.reasons)

        ordered = sorted(
            viable,
            key=lambda binding: (
                abs(_TIER_INDEX[binding.tier] - desired_index),
                0 if _TIER_INDEX[binding.tier] <= desired_index else 1,
                -_TIER_INDEX[binding.tier],
            ),
        )
        selected: ProviderIntelligenceBinding | None = None
        selected_cost: CostDecision | None = None
        held_cost: CostDecision | None = None

        for binding in ordered:
            index = _TIER_INDEX[binding.tier]
            if index < minimum_index:
                continue
            cost = self._cost_decision(binding, envelope)
            if cost.action in {CostAction.ALLOW, CostAction.OPTIMIZE, CostAction.DEGRADE}:
                selected = binding
                selected_cost = cost
                break
            if held_cost is None:
                held_cost = cost

        if selected is None:
            reasons.append("no cost-authorised binding satisfies minimum intelligence floor")
            return IntelligenceRouteDecision(
                router_id=self.ROUTER_ID,
                task_id=signals.task_id,
                assessment=assessment,
                selected_binding=None,
                cost_decision=held_cost,
                state="HOLD_OWNER_APPROVAL_OR_BINDING_REQUIRED",
                degraded_for_cost=False,
                owner_approval_required=True,
                execution_allowed=False,
                chatgpt_ui_recommendation=assessment.desired_tier.value,
                provider_request={},
                reasons=tuple(reasons),
            )

        degraded = _TIER_INDEX[selected.tier] < desired_index
        if degraded:
            reasons.append(f"cost/availability fallback={assessment.desired_tier.value}->{selected.tier.value}")
        if not selected.programmatic:
            reasons.append("selected surface is recommendation-only; visible ChatGPT model picker is not mutated by AIR")
        execution_allowed = bool(selected.programmatic and selected_cost and selected_cost.action in {CostAction.ALLOW, CostAction.OPTIMIZE, CostAction.DEGRADE})
        return IntelligenceRouteDecision(
            router_id=self.ROUTER_ID,
            task_id=signals.task_id,
            assessment=assessment,
            selected_binding=selected,
            cost_decision=selected_cost,
            state="ROUTED" if execution_allowed else "RECOMMENDATION_READY",
            degraded_for_cost=degraded,
            owner_approval_required=False,
            execution_allowed=execution_allowed,
            chatgpt_ui_recommendation=assessment.desired_tier.value,
            provider_request=self.provider_request(selected),
            reasons=tuple(reasons),
        )

    def calibration_proposal(self, outcomes: Iterable[RouterOutcome]) -> dict[str, object]:
        rows = list(outcomes)
        if len(rows) < 10:
            return {
                "state": "INSUFFICIENT_SAMPLE",
                "sample_size": len(rows),
                "automatic_policy_mutation": False,
                "proposal": None,
            }
        under = sum(1 for row in rows if row.escalation_was_needed) / len(rows)
        over = sum(1 for row in rows if row.lower_tier_would_have_sufficed) / len(rows)
        delta = 0.0
        if under >= 0.20:
            delta = -0.03
        elif over >= 0.30 and under < 0.10:
            delta = 0.03
        return {
            "state": "CALIBRATION_CANDIDATE" if delta else "NO_THRESHOLD_CHANGE_INDICATED",
            "sample_size": len(rows),
            "underprovision_rate": round(under, 4),
            "overprovision_rate": round(over, 4),
            "proposed_threshold_shift": delta,
            "maximum_absolute_shift": 0.05,
            "automatic_policy_mutation": False,
            "required_before_promotion": ["regression tests", "cost comparison", "quality comparison", "owner/governance promotion if material"],
        }

    @staticmethod
    def as_dict(value: object) -> dict[str, object]:
        raw = asdict(value)
        def convert(item: object) -> object:
            if isinstance(item, Enum):
                return item.value
            if isinstance(item, dict):
                return {key: convert(child) for key, child in item.items()}
            if isinstance(item, (list, tuple)):
                return [convert(child) for child in item]
            return item
        return convert(raw)  # type: ignore[return-value]


__all__ = [
    "AdaptiveIntelligenceRouter",
    "IntelligenceAssessment",
    "IntelligenceFeedback",
    "IntelligenceRouteDecision",
    "IntelligenceSignals",
    "IntelligenceTier",
    "OpenAI56BindingCatalog",
    "ProviderIntelligenceBinding",
    "RouterOutcome",
]
