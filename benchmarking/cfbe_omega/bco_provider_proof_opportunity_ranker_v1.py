from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.bco_provider_identity_gap_compiler_v1 import (
    GapFinding,
    ProviderIdentityGapReport,
)

_SCHEMA = "BCO-PROVIDER-PROOF-OPPORTUNITY-RANKING-V1"


class OpportunityClass(str, Enum):
    SAFE_READ_ONLY_PROOF = "SAFE_READ_ONLY_PROOF"
    WAIT_FOR_NATURAL_PROVIDER_PROOF = "WAIT_FOR_NATURAL_PROVIDER_PROOF"
    AUTHORITY_GATED_CHANGE = "AUTHORITY_GATED_CHANGE"
    PROHIBITED_AUTOFIX = "PROHIBITED_AUTOFIX"


@dataclass(frozen=True, slots=True)
class ProofOpportunity:
    opportunity_id: str
    gap_id: str
    action: str
    opportunity_class: OpportunityClass
    expected_proof_gain: float
    closure_leverage: float
    reuse_value: float
    reversibility: float
    cost: float
    risk: float
    owner_burden: float
    dependencies: tuple[str, ...] = ()
    reason: str = ""
    auto_execute: bool = False

    @property
    def score(self) -> float:
        numerator = (
            max(self.expected_proof_gain, 0.0)
            * max(self.closure_leverage, 0.0)
            * max(self.reuse_value, 0.0)
            * max(self.reversibility, 0.0)
        )
        denominator = (
            max(self.cost, 0.1)
            * max(self.risk, 0.1)
            * (1.0 + max(self.owner_burden, 0.0))
            * (1.0 + len(self.dependencies))
        )
        return numerator / denominator


@dataclass(frozen=True, slots=True)
class RankedProofOpportunity:
    rank: int
    score: float
    opportunity: ProofOpportunity


@dataclass(frozen=True, slots=True)
class ProviderProofOpportunityPlan:
    schema: str
    state: str
    ranked: tuple[RankedProofOpportunity, ...]
    safe_autonomous: tuple[str, ...]
    wait_for_natural_proof: tuple[str, ...]
    authority_gated: tuple[str, ...]
    prohibited_autofix: tuple[str, ...]
    next_safe_action: str
    provider_effect_authorized: bool = False
    credential_change_authorized: bool = False
    iam_change_authorized: bool = False
    workflow_identity_change_authorized: bool = False

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)


def _gap(report: ProviderIdentityGapReport, gap_id: str) -> GapFinding | None:
    return next((item for item in report.gaps if item.gap_id == gap_id), None)


def _opportunity_for_gap(gap: GapFinding) -> ProofOpportunity:
    gap_id = gap.gap_id

    if gap_id == "CANONICAL_WIF_FRESHNESS_UNPROVEN":
        return ProofOpportunity(
            opportunity_id="BCO-PROOF-WIF-FRESHNESS",
            gap_id=gap_id,
            action="Observe the next naturally triggered admitted canonical read-only WIF verification receipt; do not dispatch solely to manufacture freshness.",
            opportunity_class=OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            expected_proof_gain=0.95,
            closure_leverage=0.85,
            reuse_value=0.90,
            reversibility=1.0,
            cost=0.2,
            risk=0.1,
            owner_burden=0.0,
            reason="Fresh WIF proof is valuable, but provider identity exchange should not be triggered merely to improve a score.",
        )

    if gap_id == "ACTION_SPECIFIC_AUTHENTICATED_READ_UNPROVEN":
        return ProofOpportunity(
            opportunity_id="BCO-PROOF-ACTION-READBACK",
            gap_id=gap_id,
            action="Consume the next naturally produced Bubbles provider receipt through the admitted BCΩ proof-floor workflow and promote only if the action-specific authenticated-read floor is actually met.",
            opportunity_class=OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            expected_proof_gain=1.0,
            closure_leverage=1.0,
            reuse_value=1.0,
            reversibility=1.0,
            cost=0.1,
            risk=0.05,
            owner_burden=0.0,
            reason="The existing workflow already observes natural Bubbles receipts without a duplicate provider call.",
        )

    if gap_id == "SECRET_MANAGER_TOKEN_RECOVERY_UNPROVEN":
        return ProofOpportunity(
            opportunity_id="BCO-PROOF-SECRET-MANAGER-RECOVERY",
            gap_id=gap_id,
            action="Keep Secret Manager token recovery held until an already-authorized Google machine identity exists; then require read-only recovery proof before any token use.",
            opportunity_class=OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
            expected_proof_gain=0.75,
            closure_leverage=0.70,
            reuse_value=0.80,
            reversibility=1.0,
            cost=0.2,
            risk=0.25,
            owner_burden=0.0,
            dependencies=("GOOGLE_MACHINE_AUTH",),
            reason="Secret recovery is not safe to probe by inventing or expanding machine identity authority.",
        )

    if gap.authority_required_to_change:
        if gap_id == "REQUESTING_WORKFLOW_NOT_MATCHING_WIF_ATTRIBUTE_CONDITION":
            action = "Do not modify the WIF provider condition automatically. Any expansion of workflow identity eligibility requires explicit authority and a separate least-privilege review."
        elif gap_id == "RUNTIME_GOOGLE_ADC_UNVERIFIED":
            action = "Keep Gemini runtime ADC held. Creating the runtime service account or adding IAM roles is an authority-gated change, not an autonomous repair."
        elif gap_id == "DIRECT_OPERATOR_TOKEN_UNAVAILABLE":
            action = "Do not create, copy, recover, or bind an operator token automatically. Token provisioning/binding requires explicit authority."
        elif gap_id == "STATIC_GOOGLE_MACHINE_CREDENTIAL_UNAVAILABLE":
            action = "Do not introduce a static Google credential to close the gap. Prefer already-admitted keyless identity routes; any credential provisioning is authority-gated."
        else:
            action = "Hold this gap for explicit authority because closing it changes identity, credential, IAM, or provider trust state."
        return ProofOpportunity(
            opportunity_id=f"BCO-AUTH-{gap_id}",
            gap_id=gap_id,
            action=action,
            opportunity_class=OpportunityClass.AUTHORITY_GATED_CHANGE,
            expected_proof_gain=0.90,
            closure_leverage=0.90,
            reuse_value=0.75,
            reversibility=0.35,
            cost=0.8,
            risk=1.0,
            owner_burden=1.0,
            reason=gap.reason,
        )

    return ProofOpportunity(
        opportunity_id=f"BCO-HOLD-{gap_id}",
        gap_id=gap_id,
        action="Preserve the hold and gather stronger evidence through an existing read-only route; do not infer or manufacture provider authority.",
        opportunity_class=OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF,
        expected_proof_gain=0.60,
        closure_leverage=0.55,
        reuse_value=0.60,
        reversibility=1.0,
        cost=0.2,
        risk=0.1,
        owner_burden=0.0,
        reason=gap.reason,
    )


def rank_provider_proof_opportunities(report: ProviderIdentityGapReport) -> ProviderProofOpportunityPlan:
    opportunities: list[ProofOpportunity] = []

    # This is the one always-safe autonomous action: recompile/rank evidence that is
    # already present. It does not call a provider and cannot change trust state.
    opportunities.append(
        ProofOpportunity(
            opportunity_id="BCO-SAFE-RECOMPILE-EVIDENCE",
            gap_id="EVIDENCE_STATE",
            action="Recompile the provider identity gap graph from already available immutable/redacted receipts and update only the derived ranking.",
            opportunity_class=OpportunityClass.SAFE_READ_ONLY_PROOF,
            expected_proof_gain=0.35,
            closure_leverage=0.40,
            reuse_value=1.0,
            reversibility=1.0,
            cost=0.05,
            risk=0.01,
            owner_burden=0.0,
            reason="Derived-state refresh is safe because primary provider evidence remains unchanged.",
            auto_execute=True,
        )
    )

    for gap in report.gaps:
        opportunities.append(_opportunity_for_gap(gap))

    # Explicit negative opportunity: never solve provider proof gaps by weakening
    # proof floors or treating workflow success/public reachability as auth proof.
    opportunities.append(
        ProofOpportunity(
            opportunity_id="BCO-PROHIBIT-PROOF-FLOOR-WEAKENING",
            gap_id="PROOF_POLICY",
            action="Never downgrade the required provider readback floor or relabel public reachability/workflow success as authenticated readback to manufacture closure.",
            opportunity_class=OpportunityClass.PROHIBITED_AUTOFIX,
            expected_proof_gain=0.0,
            closure_leverage=0.0,
            reuse_value=1.0,
            reversibility=0.0,
            cost=1.0,
            risk=10.0,
            owner_burden=10.0,
            reason="This would create false proof rather than close a real gap.",
        )
    )

    ranked_raw = sorted(
        opportunities,
        key=lambda item: (
            item.opportunity_class != OpportunityClass.SAFE_READ_ONLY_PROOF,
            -item.score,
            item.opportunity_id,
        ),
    )
    ranked = tuple(
        RankedProofOpportunity(rank=index, score=item.score, opportunity=item)
        for index, item in enumerate(ranked_raw, start=1)
    )
    safe = tuple(item.opportunity_id for item in opportunities if item.opportunity_class == OpportunityClass.SAFE_READ_ONLY_PROOF)
    waiting = tuple(item.opportunity_id for item in opportunities if item.opportunity_class == OpportunityClass.WAIT_FOR_NATURAL_PROVIDER_PROOF)
    gated = tuple(item.opportunity_id for item in opportunities if item.opportunity_class == OpportunityClass.AUTHORITY_GATED_CHANGE)
    prohibited = tuple(item.opportunity_id for item in opportunities if item.opportunity_class == OpportunityClass.PROHIBITED_AUTOFIX)
    next_safe = safe[0] if safe else "NONE"
    return ProviderProofOpportunityPlan(
        schema=_SCHEMA,
        state="SAFE_PROOF_WORK_AVAILABLE" if safe else "NO_SAFE_AUTONOMOUS_PROVIDER_PROOF_ACTION",
        ranked=ranked,
        safe_autonomous=safe,
        wait_for_natural_proof=waiting,
        authority_gated=gated,
        prohibited_autofix=prohibited,
        next_safe_action=next_safe,
    )
