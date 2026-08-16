from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CostClass(str, Enum):
    C0_INCLUDED_FREE = "C0_INCLUDED_FREE"
    C1_MICRO_SERVERLESS = "C1_MICRO_SERVERLESS"
    C2_CONTROLLED_PAID = "C2_CONTROLLED_PAID"
    C3_EXPENSIVE_COMPUTE = "C3_EXPENSIVE_COMPUTE"


class CostAction(str, Enum):
    ALLOW = "ALLOW"
    OPTIMIZE = "OPTIMIZE"
    DEGRADE = "DEGRADE"
    HOLD_OWNER_APPROVAL = "HOLD_OWNER_APPROVAL"
    DENY_UNKNOWN_COST = "DENY_UNKNOWN_COST"
    STOP_NONESSENTIAL = "STOP_NONESSENTIAL"


@dataclass(frozen=True)
class CostEnvelope:
    posture: str = "PRE_REVENUE_ZERO_BASE"
    currency: str = "ZAR"
    incremental_monthly_budget: float = 0.0
    owner_approved: bool = False
    observe_ratio: float = 0.50
    optimize_ratio: float = 0.70
    degrade_ratio: float = 0.85
    critical_only_ratio: float = 0.95
    stop_ratio: float = 1.00


@dataclass(frozen=True)
class WorkloadCostProfile:
    workload_id: str
    cost_class: CostClass
    estimated_monthly_cost: float | None
    current_month_spend: float = 0.0
    already_paid_or_included: bool = False
    event_driven: bool = True
    scale_to_zero: bool = True
    hard_cap_or_quota_available: bool = False
    essential: bool = False
    revenue_linked: bool = False
    owner_approved: bool = False
    cheaper_route_available: bool = False
    notes: str = ""


@dataclass(frozen=True)
class CostDecision:
    workload_id: str
    action: CostAction
    reason: str
    permitted_incremental_cost: float
    required_controls: tuple[str, ...]
    degradation_actions: tuple[str, ...]
    owner_interrupt_required: bool


class PreRevenueCostGovernor:
    """Fail-closed cost control for a pre-revenue Federation.

    The governor protects the owner from silent recurring cost growth. It does
    not manage provider billing by itself and does not claim that a provider
    budget alert is a hard spending cap. Runtime/provider-specific stop controls
    remain separate execution bindings.
    """

    DEFAULT_DEGRADATION = (
        "prefer event-driven trigger over polling",
        "batch low-priority work",
        "reuse cached or previously verified results",
        "reduce nonessential inference frequency",
        "switch to cheaper authorised route where equivalent",
        "defer low-value background analysis",
        "suspend nonessential recurring jobs before buying more capacity",
    )

    def evaluate(self, profile: WorkloadCostProfile, envelope: CostEnvelope | None = None) -> CostDecision:
        envelope = envelope or CostEnvelope()
        controls: list[str] = [
            "COST_IDENTITY_REQUIRED",
            "CHEAPEST_VIABLE_ROUTE_CHECK",
            "NO_SILENT_SCALE_UP",
            "READBACK_REQUIRED_FOR_COST_CONTROL_CLAIMS",
        ]

        if profile.estimated_monthly_cost is None and not profile.already_paid_or_included:
            return CostDecision(
                profile.workload_id,
                CostAction.DENY_UNKNOWN_COST,
                "Unknown incremental recurring cost fails closed in pre-revenue posture.",
                0.0,
                tuple(controls + ["ESTIMATE_COST_BEFORE_DEPLOYMENT"]),
                self.DEFAULT_DEGRADATION,
                False,
            )

        estimate = max(0.0, float(profile.estimated_monthly_cost or 0.0))
        if profile.already_paid_or_included or profile.cost_class is CostClass.C0_INCLUDED_FREE or estimate == 0.0:
            if profile.cheaper_route_available:
                controls.append("REUSE_CHEAPER_EQUIVALENT_ROUTE")
            return CostDecision(
                profile.workload_id,
                CostAction.ALLOW,
                "Workload is zero incremental cost or already included, subject to normal authority and proof controls.",
                0.0,
                tuple(controls),
                (),
                False,
            )

        if profile.cost_class in {CostClass.C2_CONTROLLED_PAID, CostClass.C3_EXPENSIVE_COMPUTE}:
            return CostDecision(
                profile.workload_id,
                CostAction.HOLD_OWNER_APPROVAL,
                "Controlled or expensive paid compute remains owner-reserved while pre-revenue.",
                0.0,
                tuple(controls + ["OWNER_APPROVED_FINITE_ENVELOPE_REQUIRED"]),
                self.DEFAULT_DEGRADATION,
                True,
            )

        if envelope.incremental_monthly_budget <= 0.0 or not envelope.owner_approved:
            return CostDecision(
                profile.workload_id,
                CostAction.HOLD_OWNER_APPROVAL,
                "Pre-revenue incremental paid budget is zero until the owner approves a finite envelope.",
                0.0,
                tuple(controls + ["OWNER_APPROVED_FINITE_ENVELOPE_REQUIRED"]),
                self.DEFAULT_DEGRADATION,
                True,
            )

        projected = max(0.0, profile.current_month_spend) + estimate
        ratio = projected / envelope.incremental_monthly_budget
        controls.extend(["BOUNDED_RUNTIME", "MAX_CONCURRENCY_OR_INSTANCE_CAP", "TIMEOUT", "USAGE_TELEMETRY"])
        if not profile.event_driven:
            controls.append("EVENT_DRIVEN_MIGRATION_PREFERRED")
        if not profile.scale_to_zero:
            controls.append("SCALE_TO_ZERO_OR_JUSTIFY_ALWAYS_ON")
        if profile.hard_cap_or_quota_available:
            controls.append("PROVIDER_NATIVE_CAP_OR_QUOTA_REQUIRED")

        if ratio >= envelope.stop_ratio:
            return CostDecision(profile.workload_id, CostAction.STOP_NONESSENTIAL,
                                "Projected spend reaches or exceeds the approved envelope.", 0.0,
                                tuple(controls), self.DEFAULT_DEGRADATION, profile.essential)
        if ratio >= envelope.critical_only_ratio:
            return CostDecision(profile.workload_id, CostAction.DEGRADE,
                                "Cost pressure is at critical-only threshold.", estimate if profile.essential else 0.0,
                                tuple(controls), self.DEFAULT_DEGRADATION, False)
        if ratio >= envelope.degrade_ratio:
            return CostDecision(profile.workload_id, CostAction.DEGRADE,
                                "Cost pressure requires automatic degradation before additional spend.", estimate,
                                tuple(controls), self.DEFAULT_DEGRADATION, False)
        if ratio >= envelope.optimize_ratio:
            return CostDecision(profile.workload_id, CostAction.OPTIMIZE,
                                "Cost pressure requires batching, caching and cheaper-route optimization.", estimate,
                                tuple(controls), self.DEFAULT_DEGRADATION, False)
        return CostDecision(profile.workload_id, CostAction.ALLOW,
                            "Paid micro-workload is within an explicit owner-approved finite envelope.", estimate,
                            tuple(controls), (), False)

    def rank_routes(self, routes: Iterable[dict]) -> dict | None:
        """Prefer equivalent zero/included-cost routes before paid routes."""
        viable = [r for r in routes if r.get("available", False) and r.get("authorised", True)]
        if not viable:
            return None
        return max(
            viable,
            key=lambda r: (
                1 if r.get("included_or_free", False) else 0,
                -float(r.get("estimated_incremental_cost", 0.0)),
                float(r.get("proof_strength", 0.0)),
                float(r.get("information_gain", 0.0)),
                -float(r.get("owner_burden", 0.0)),
            ),
        )


__all__ = [
    "CostAction",
    "CostClass",
    "CostDecision",
    "CostEnvelope",
    "PreRevenueCostGovernor",
    "WorkloadCostProfile",
]
