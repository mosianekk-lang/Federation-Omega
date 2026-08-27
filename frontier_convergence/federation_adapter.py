"""Bindings from Frontier Convergence to existing Formation Omega MCE/FCI primitives."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

from formation_omega.autonomic_fabric import AuthorityCeiling
from formation_omega.institutional_cognition import (
    CouncilMember,
    EvidenceWeightedCouncil,
    InstitutionalRole,
    PolicyCandidate,
    PolicyEvolutionLab,
    PolicyStage,
    RobustScenarioPlanner,
    ScenarioOption,
)
from formation_omega.mission_convergence import ConvergenceLedger, MissionSpec

from .core import digest


@dataclass(frozen=True)
class IndependentObservation:
    observer_id: str
    independence_domain: str
    evidence_quality: float
    calibration: float
    confidence: float
    vote: float
    critical_veto: bool = False
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class FederationQuorumReceipt:
    outcome: str
    independent_domains: int
    support: float
    opposition: float
    critical_vetoes: tuple[str, ...]
    receipt_sha256: str


class FederationConvergenceAdapter:
    """Thin adapter: reuse MCE/FCI rather than creating a parallel mission institution."""

    def __init__(self, ledger: ConvergenceLedger | None = None) -> None:
        self.council = EvidenceWeightedCouncil()
        self.scenarios = RobustScenarioPlanner()
        self.policy_lab = PolicyEvolutionLab()
        self.ledger = ledger or ConvergenceLedger()

    @staticmethod
    def mission_spec(
        *,
        mission_id: str,
        objective: str,
        success_criteria: Iterable[str],
        constraints: Iterable[str] = (),
        authority_ceiling: str = "A1",
    ) -> MissionSpec:
        return MissionSpec.create(
            mission_id=mission_id,
            objective=objective,
            success_criteria=success_criteria,
            constraints=constraints,
            authority_ceiling=authority_ceiling,
            rollback_required=True,
        )

    def independent_quorum(
        self,
        observations: Sequence[IndependentObservation],
        *,
        minimum_independent_domains: int = 3,
        support_threshold: float = 0.67,
    ) -> FederationQuorumReceipt:
        members = [
            CouncilMember(
                member_id=o.observer_id,
                role=InstitutionalRole.VERIFIER,
                independence_domain=o.independence_domain,
                evidence_quality=o.evidence_quality,
                calibration=o.calibration,
                confidence=o.confidence,
                vote=o.vote,
                critical_veto=o.critical_veto,
                evidence_refs=o.evidence_refs,
            )
            for o in observations
        ]
        decision = self.council.decide(
            members,
            minimum_independent_domains=minimum_independent_domains,
            support_threshold=support_threshold,
        )
        body = {
            "decision_sha256": decision.decision_sha256,
            "outcome": decision.outcome,
            "independent_domains": decision.independent_domains,
            "support": decision.support,
            "opposition": decision.opposition,
            "critical_vetoes": decision.critical_vetoes,
        }
        return FederationQuorumReceipt(
            outcome=decision.outcome,
            independent_domains=decision.independent_domains,
            support=decision.support,
            opposition=decision.opposition,
            critical_vetoes=decision.critical_vetoes,
            receipt_sha256=digest(body),
        )

    def choose_scenario(self, options: Sequence[Mapping[str, object]]) -> dict[str, object]:
        candidates = [
            ScenarioOption(
                option_id=str(item["option_id"]),
                outcomes={str(k): float(v) for k, v in dict(item["outcomes"]).items()},
                irreversible_risk=float(item.get("irreversible_risk", 0.0)),
                evidence_strength=float(item.get("evidence_strength", 0.0)),
            )
            for item in options
        ]
        return asdict(self.scenarios.choose(candidates))

    def policy_transition(
        self,
        *,
        policy_id: str,
        from_stage: str,
        to_stage: str,
        measured_gain: float,
        regression_score: float,
        independent_replications: int,
        rollback_verified: bool,
        consequential: bool = False,
        owner_approved: bool = False,
        evidence_refs: Iterable[str] = (),
    ) -> dict[str, object]:
        candidate = PolicyCandidate(
            policy_id=policy_id,
            stage=PolicyStage(from_stage),
            measured_gain=float(measured_gain),
            regression_score=float(regression_score),
            independent_replications=int(independent_replications),
            rollback_verified=bool(rollback_verified),
            consequential=bool(consequential),
            owner_approved=bool(owner_approved),
            evidence_refs=tuple(sorted(set(evidence_refs))),
        )
        return asdict(self.policy_lab.promote(candidate, PolicyStage(to_stage)))

    def record_terminal_event(
        self,
        *,
        mission_id: str,
        event_type: str,
        payload: Mapping[str, object],
        idempotency_key: str,
    ) -> dict[str, object]:
        if event_type not in {
            "SUCCESS", "FAILURE", "CONSTRAINT", "CORRECTION", "RECOVERY",
            "INNOVATION_CANDIDATE", "EXPERIMENT_RESULT", "NEGATIVE_RESULT",
        }:
            raise ValueError("UNSUPPORTED_FEDERATION_EVENT_TYPE")
        return self.ledger.append(
            mission_id=mission_id,
            event_type=event_type,
            payload=payload,
            idempotency_key=idempotency_key,
        ).to_dict()

    @staticmethod
    def ceiling_for_internal_suite() -> AuthorityCeiling:
        return AuthorityCeiling.A1_INTERNAL
