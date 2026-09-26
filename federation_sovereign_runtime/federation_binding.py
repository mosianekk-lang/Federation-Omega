from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from ao_harmonic_v3.cost_governor import CostClass
from ao_harmonic_v3.intelligence_router import (
    AdaptiveIntelligenceRouter,
    IntelligenceRouteDecision,
    IntelligenceSignals,
    IntelligenceTier,
    ProviderIntelligenceBinding,
)
from ao_harmonic_v3.runtime import AOHarmonicV3

from .astra_profile import ASTRA_MODEL_ID
from .core import ReasoningEffort, SovereignRuntimeKernel


_TIER_TO_EFFORT = {
    IntelligenceTier.INSTANT: ReasoningEffort.LOW,
    IntelligenceTier.MEDIUM: ReasoningEffort.MEDIUM,
    IntelligenceTier.HIGH: ReasoningEffort.HIGH,
    IntelligenceTier.EXTRA_HIGH: ReasoningEffort.XHIGH,
    IntelligenceTier.PRO: ReasoningEffort.MAX,
}


def astra_air_binding(
    tier: IntelligenceTier,
    *,
    available: bool,
    authorised: bool,
    estimated_monthly_cost: float | None = None,
    current_month_spend: float = 0.0,
    already_paid_or_included: bool = False,
) -> ProviderIntelligenceBinding:
    """Create a GPT-6 Astra binding for the existing Adaptive Intelligence Router.

    This is a routing/source descriptor. It does not call OpenAI, prove access,
    or change the visible ChatGPT model picker.
    """
    effort = _TIER_TO_EFFORT[tier]
    return ProviderIntelligenceBinding(
        binding_id=f"OPENAI_ASTRA_RESPONSES_{tier.value}",
        provider="OPENAI",
        surface="RESPONSES_API",
        tier=tier,
        model=ASTRA_MODEL_ID,
        reasoning_effort=effort.value,
        reasoning_mode=None,
        available=bool(available),
        authorised=bool(authorised),
        programmatic=True,
        cost_class=(
            CostClass.C2_CONTROLLED_PAID
            if tier in {IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO}
            else CostClass.C1_MICRO_SERVERLESS
        ),
        estimated_monthly_cost=estimated_monthly_cost,
        current_month_spend=float(current_month_spend),
        already_paid_or_included=bool(already_paid_or_included),
        event_driven=True,
        scale_to_zero=True,
        hard_cap_or_quota_available=False,
        notes=(
            "GPT-6 Astra public Responses binding. Live model availability, API authority, "
            "price/cost envelope and provider acceptance must be revalidated at execution time."
        ),
    )


def astra_binding_catalog(
    *,
    available: bool,
    authorised: bool,
    estimated_monthly_cost: float | None = None,
    current_month_spend: float = 0.0,
    already_paid_or_included: bool = False,
) -> tuple[ProviderIntelligenceBinding, ...]:
    return tuple(
        astra_air_binding(
            tier,
            available=available,
            authorised=authorised,
            estimated_monthly_cost=estimated_monthly_cost,
            current_month_spend=current_month_spend,
            already_paid_or_included=already_paid_or_included,
        )
        for tier in IntelligenceTier
    )


class FederationSovereignRuntimeBinding:
    """Compose FSIR Ω1 with the existing AO-HARMONIC cognitive fabric.

    No sovereignty is duplicated: AO-HARMONIC/Forest/Horizon/SLOS remain the
    existing cognition/strategy organs; FSIR provides provider-neutral runtime
    coordination and processor-market semantics around them.
    """

    BINDING_ID = "FSIR-OMEGA1::AO-HARMONIC-V3"

    def __init__(self, ao_runtime: AOHarmonicV3 | None = None) -> None:
        self.ao = ao_runtime or AOHarmonicV3()
        self.fsir = SovereignRuntimeKernel()

    def route_astra(
        self,
        signals: IntelligenceSignals,
        *,
        available: bool,
        authorised: bool,
        estimated_monthly_cost: float | None = None,
        current_month_spend: float = 0.0,
        already_paid_or_included: bool = False,
        envelope: Any = None,
    ) -> IntelligenceRouteDecision:
        bindings = astra_binding_catalog(
            available=available,
            authorised=authorised,
            estimated_monthly_cost=estimated_monthly_cost,
            current_month_spend=current_month_spend,
            already_paid_or_included=already_paid_or_included,
        )
        return self.ao.intelligence.route(
            signals,
            bindings,
            envelope=envelope,
        )

    def prepare_astra_response(
        self,
        decision: IntelligenceRouteDecision,
        input_data: object,
        *,
        previous_response_id: str | None = None,
    ) -> dict[str, object]:
        """Prepare, but do not execute, a GPT-6 Astra Responses request."""
        binding = decision.selected_binding
        if binding is None or binding.model != ASTRA_MODEL_ID:
            raise ValueError("DECISION_IS_NOT_ASTRA_BOUND")
        return AdaptiveIntelligenceRouter.to_openai_responses_payload(
            decision,
            input_data,
            previous_response_id=previous_response_id,
        )

    def restore_acceptance_test(self) -> dict[str, Any]:
        ao = self.ao.restore_acceptance_test()
        fsir = self.fsir.bootstrap()
        return {
            "binding_id": self.BINDING_ID,
            "ao_harmonic": ao,
            "fsir": fsir,
            "required_composition": (
                "HUMAN_FIRST_OMEGA",
                "FOREST_FIRST_OMEGA",
                "HORIZON_OMEGA",
                "ADAPTIVE_INTELLIGENCE_ROUTER",
                "BUBBLES_CHATGOV",
                "SOVARA_EFFECT_AUTHORITY",
                "PROOF_AND_READBACK",
                "KDV_CONTINUITY",
            ),
            "truth_boundary": {
                "source_binding_present": True,
                "astra_provider_invoked": False,
                "api_credential_proved": False,
                "provider_acceptance_proved": False,
                "native_chatgpt_modified": False,
                "federation_outperforms_astra_proved": False,
            },
        }


__all__ = [
    "FederationSovereignRuntimeBinding",
    "astra_air_binding",
    "astra_binding_catalog",
]
