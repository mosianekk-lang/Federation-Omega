from __future__ import annotations

"""CHARGE Ω commercial capability court — converged thin layer.

Unique responsibility:
    convert an already-qualified CFBE Ω-HARVEST capability into a pay-last
    commercial route decision.

This module deliberately does *not* perform frontier discovery, mechanism
archaeology, license/IP analysis, benchmark comparability, empirical advantage
measurement, provider execution, procurement, or spend authorization. Those
remain owned by existing CFBE/Federation components.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json

SCHEMA = "CHARGE-OMEGA-COMMERCIAL-COURT-V1.3"
SOURCE_BASE = "64c06a68fd717bed28836a220d25b4d94fe8645c"
HARVEST_AUTHORITY = "benchmarking.cfbe_omega.omega_harvest_max_v2"
FRONTIER_AUTHORITY = "benchmarking.cfbe_omega.federation_frontier_refresh_v2"
VALUE_AUTHORITY = "benchmarking.cfbe_omega.value_foundry_v1"

HARVEST_ELIGIBLE = frozenset({
    "GENE_FORMED",
    "CANDIDATE_EXECUTABLE",
    "EMPIRICAL_ADVANTAGE_PROVEN",
    "VALUE_PROVEN",
})
HARVEST_EMPIRICAL = frozenset({"EMPIRICAL_ADVANTAGE_PROVEN", "VALUE_PROVEN"})


class CommercialRoute(str, Enum):
    REUSE = "REUSE"
    OPEN_SUBSTITUTE = "OPEN_SUBSTITUTE"
    COMPOSE = "COMPOSE"
    EXTEND = "EXTEND"
    BUILD = "BUILD"
    TRIAL = "TRIAL"
    HOLD = "HOLD"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class HarvestQualification:
    """Narrow adapter over CFBE Ω-HARVEST MAX v2 completion readback.

    The field names intentionally align with HarvestCompletionReceipt without
    copying its internal archaeology logic.
    """

    candidate_id: str
    state: str
    blockers: tuple[str, ...]
    completed_stage_count: int
    independent_source_groups: int
    source_family_count: int
    receiver_adoption_authorized: bool = False
    provider_effect_authorized: bool = False

    def valid_for_commercial_court(self) -> bool:
        return (
            bool(self.candidate_id)
            and self.state in HARVEST_ELIGIBLE
            and not self.blockers
            and self.completed_stage_count > 0
            and self.independent_source_groups > 0
            and self.source_family_count > 0
            and not self.provider_effect_authorized
        )


@dataclass(frozen=True, slots=True)
class CommercialCapability:
    capability_id: str
    canonical_name: str
    outcome: str
    official_sources: tuple[str, ...]
    commercial_or_gated: bool
    provider_native_edge: bool
    estimated_monthly_cost: float = 0.0
    lock_in: float = 0.0
    privacy_risk: float = 0.0
    regulatory_risk: float = 0.0


@dataclass(frozen=True, slots=True)
class FederationAlternative:
    capability_id: str
    existing_fit: float
    open_fit: float
    compose_fit: float
    build_feasibility: float
    proof_strength: float
    operational_strength: float
    provider_native_strength: float
    exit_path_strength: float


@dataclass(frozen=True, slots=True)
class CommercialDecision:
    schema: str
    capability_id: str
    harvest_candidate_id: str
    route: CommercialRoute
    score: float
    reasons: tuple[str, ...]
    next_experiment: str
    purchase_candidate: bool = False
    purchase_authorized: bool = False


@dataclass(frozen=True, slots=True)
class CommercialTrialReceipt:
    """Commercial-only evidence after CFBE has already proven H9/H10 quality.

    Same-task benchmarking, sample-size adequacy, regression checks, calibration,
    contamination, counterfactuals and empirical advantage are not reimplemented
    here; Ω-HARVEST MAX v2 owns those courts.
    """

    capability_id: str
    open_and_internal_alternatives_exhausted: bool
    provider_native_readback: bool
    exit_path_proven: bool
    cost_observed: bool
    evidence_refs: tuple[str, ...]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


class CommercialCourt:
    """Pay-last decision court. It never authorizes spend."""

    def decide(
        self,
        capability: CommercialCapability,
        alternative: FederationAlternative,
        harvest: HarvestQualification,
    ) -> CommercialDecision:
        if harvest.candidate_id != capability.capability_id:
            return self._hold(capability, harvest, "harvest_capability_identity_mismatch")
        if not harvest.valid_for_commercial_court():
            return self._hold(capability, harvest, "omega_harvest_not_qualified")
        if not capability.official_sources:
            return self._hold(capability, harvest, "official_source_missing")
        if not capability.commercial_or_gated:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.REUSE,
                1.0,
                ("not_a_commercial_dependency", "route_through_existing_capability_fabric"),
                "exit CHARGE commercial lane",
            )

        risk = (
            0.34 * _clamp(capability.lock_in)
            + 0.33 * _clamp(capability.privacy_risk)
            + 0.33 * _clamp(capability.regulatory_risk)
        )
        if risk >= 0.78:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.REJECT,
                -round(risk, 6),
                ("commercial_dependency_risk_too_high", "retain_provider_neutral_gene"),
                "preserve abstract capability; do not purchase",
            )

        if alternative.existing_fit >= 0.82 and alternative.proof_strength >= 0.70:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.REUSE,
                round(alternative.existing_fit, 6),
                ("strong_current_federation_equivalent", "pay_last"),
                "harvest only the proven missing delta",
            )
        if alternative.open_fit >= 0.78:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.OPEN_SUBSTITUTE,
                round(alternative.open_fit, 6),
                ("strong_open_substitute", "avoid_vendor_dependency"),
                "qualify open substitute under existing security/license courts",
            )
        if alternative.compose_fit >= 0.76:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.COMPOSE,
                round(alternative.compose_fit, 6),
                ("existing_primitives_compose", "avoid_new_system"),
                "compile the minimum composition and test it",
            )
        if alternative.existing_fit >= 0.62:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.EXTEND,
                round(alternative.existing_fit, 6),
                ("material_existing_coverage", "delta_only_extension"),
                "implement only the missing commercial-neutral delta",
            )
        if alternative.build_feasibility >= 0.72 and not capability.provider_native_edge:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.BUILD,
                round(alternative.build_feasibility, 6),
                ("provider_neutral_build_feasible", "reversible_before_purchase"),
                "build the smallest gene and send results back to CFBE Value Foundry",
            )
        if capability.provider_native_edge:
            score = (
                0.35 * _clamp(alternative.provider_native_strength)
                + 0.25 * _clamp(alternative.proof_strength)
                + 0.20 * _clamp(alternative.exit_path_strength)
                + 0.20 * (1 - risk)
            )
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.TRIAL,
                round(score, 6),
                ("irreducible_provider_native_edge_possible", "commercial_value_unproved", "purchase_unapproved"),
                "bounded zero/low-cost trial; return empirical results to Ω-HARVEST MAX v2",
            )
        return self._hold(capability, harvest, "no_evidence_backed_route")

    def after_trial(
        self,
        capability: CommercialCapability,
        alternative: FederationAlternative,
        harvest: HarvestQualification,
        trial: CommercialTrialReceipt,
    ) -> CommercialDecision:
        pre = self.decide(capability, alternative, harvest)
        failures: list[str] = []
        if pre.route is not CommercialRoute.TRIAL:
            failures.append("not_trial_route")
        if harvest.state not in HARVEST_EMPIRICAL or harvest.blockers:
            failures.append("omega_harvest_h9_or_h10_required")
        if not trial.open_and_internal_alternatives_exhausted:
            failures.append("alternatives_not_exhausted")
        if not trial.provider_native_readback:
            failures.append("provider_readback_missing")
        if not trial.exit_path_proven:
            failures.append("exit_path_missing")
        if not trial.cost_observed:
            failures.append("cost_not_observed")
        if not trial.evidence_refs:
            failures.append("evidence_refs_missing")
        if failures:
            return CommercialDecision(
                SCHEMA,
                capability.capability_id,
                harvest.candidate_id,
                CommercialRoute.HOLD,
                0.0,
                tuple(sorted(set(failures))),
                "do not purchase; close commercial evidence gaps through existing courts",
            )

        # This is deliberately only a candidate extraction. Spending authority is
        # never encoded in CHARGE and cannot be inherited from CFBE/provider proof.
        return CommercialDecision(
            SCHEMA,
            capability.capability_id,
            harvest.candidate_id,
            CommercialRoute.TRIAL,
            1.0,
            ("omega_harvest_empirical_advantage_proven", "commercial_exit_and_cost_proven", "owner_decision_required"),
            "prepare owner-facing ROI/exit-path decision packet",
            purchase_candidate=True,
            purchase_authorized=False,
        )

    @staticmethod
    def _hold(
        capability: CommercialCapability,
        harvest: HarvestQualification,
        reason: str,
    ) -> CommercialDecision:
        return CommercialDecision(
            SCHEMA,
            capability.capability_id,
            harvest.candidate_id,
            CommercialRoute.HOLD,
            0.0,
            (reason,),
            "return to CFBE Ω-HARVEST / frontier / evidence court; do not purchase",
        )


def decision_receipt(decision: CommercialDecision) -> dict[str, object]:
    payload = asdict(decision)
    payload["route"] = decision.route.value
    payload["purchase_authorized"] = False
    payload["sha256"] = _digest(payload)
    return payload
