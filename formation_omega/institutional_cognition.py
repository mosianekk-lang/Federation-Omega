"""Federated Cognitive Institution (FCI Omega) v1.

A public-safe institutional coordination layer above MCE/AMCF/SOE. It provides
constitutional invariants, evidence-weighted councils, multi-timescale planning,
robust scenario choice, policy evolution, recursive-improvement gates,
institutional memory, anomaly containment and authority-narrowing delegation.

FCI produces deterministic institutional decisions and receipts. It does not
create credentials, execute provider effects, spend money, change owner intent,
or self-certify provider/runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Iterable, Mapping, Sequence

from .autonomic_fabric import AuthorityCeiling


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


_AUTHORITY_RANK = {
    AuthorityCeiling.A0_OBSERVE: 0,
    AuthorityCeiling.A1_INTERNAL: 1,
    AuthorityCeiling.A2_BOUNDED_EFFECT: 2,
    AuthorityCeiling.A3_CONSEQUENTIAL: 3,
}


class Horizon(str, Enum):
    TACTICAL = "TACTICAL"
    OPERATIONAL = "OPERATIONAL"
    STRATEGIC = "STRATEGIC"
    GENERATIONAL = "GENERATIONAL"


class InstitutionalRole(str, Enum):
    PROPOSER = "PROPOSER"
    BUILDER = "BUILDER"
    FALSIFIER = "FALSIFIER"
    VERIFIER = "VERIFIER"
    AUDITOR = "AUDITOR"
    STEWARD = "STEWARD"


class PolicyStage(str, Enum):
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    ADOPTED = "ADOPTED"
    HELD = "HELD"
    RETIRED = "RETIRED"


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ConstitutionalInvariant:
    invariant_id: str
    statement: str
    owner_amendable: bool = False
    hard_veto: bool = True

    def __post_init__(self) -> None:
        if not self.invariant_id.strip() or not self.statement.strip():
            raise ValueError("invariant id and statement are required")


DEFAULT_INVARIANTS: tuple[ConstitutionalInvariant, ...] = (
    ConstitutionalInvariant("INV-PROOF", "Proof must not be promoted beyond the surface and state actually verified."),
    ConstitutionalInvariant("INV-AUTH", "Delegated authority may narrow but may never silently expand."),
    ConstitutionalInvariant("INV-OWNER", "Consequential owner intent may not be rewritten without explicit owner authority."),
    ConstitutionalInvariant("INV-SELF-CERT", "A proposer, builder or executor may not independently certify its own consequential completion."),
    ConstitutionalInvariant("INV-ROLLBACK", "Consequential change requires a bounded rollback or an explicit owner-approved irreversibility decision."),
    ConstitutionalInvariant("INV-HISTORY", "Correction, supersession and consolidation preserve prior institutional history."),
)


@dataclass(frozen=True)
class InstitutionalProposal:
    proposal_id: str
    objective: str
    authority_ceiling: AuthorityCeiling
    external_effect: bool = False
    consequential: bool = False
    rollback_defined: bool = True
    self_certified: bool = False
    owner_intent_change: bool = False
    requested_invariant_waivers: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstitutionDecision:
    admitted: bool
    vetoes: tuple[str, ...]
    owner_gate_required: bool
    decision_sha256: str


class ConstitutionKernel:
    """Hard constitutional preflight for institutional proposals."""

    def __init__(self, invariants: Iterable[ConstitutionalInvariant] = DEFAULT_INVARIANTS) -> None:
        self.invariants = {item.invariant_id: item for item in invariants}
        if not self.invariants:
            raise ValueError("at least one constitutional invariant is required")

    def evaluate(
        self,
        proposal: InstitutionalProposal,
        *,
        institutional_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
        owner_approval: bool = False,
    ) -> ConstitutionDecision:
        vetoes: list[str] = []
        owner_gate = False
        if _AUTHORITY_RANK[proposal.authority_ceiling] > _AUTHORITY_RANK[institutional_ceiling]:
            vetoes.append("AUTHORITY_CEILING_EXCEEDED")
        if proposal.self_certified:
            vetoes.append("SELF_CERTIFICATION_PROHIBITED")
        if proposal.consequential and not proposal.rollback_defined:
            if not owner_approval:
                vetoes.append("ROLLBACK_OR_OWNER_IRREVERSIBILITY_DECISION_REQUIRED")
            owner_gate = True
        if proposal.owner_intent_change:
            owner_gate = True
            if not owner_approval:
                vetoes.append("OWNER_INTENT_CHANGE_REQUIRES_OWNER")
        for invariant_id in proposal.requested_invariant_waivers:
            invariant = self.invariants.get(invariant_id)
            if invariant is None:
                vetoes.append(f"UNKNOWN_INVARIANT:{invariant_id}")
            elif not invariant.owner_amendable:
                vetoes.append(f"NON_AMENDABLE_INVARIANT:{invariant_id}")
            elif not owner_approval:
                vetoes.append(f"OWNER_APPROVAL_REQUIRED:{invariant_id}")
                owner_gate = True
        body = {
            "proposal": asdict(proposal),
            "institutional_ceiling": institutional_ceiling.value,
            "owner_approval": bool(owner_approval),
            "vetoes": sorted(set(vetoes)),
            "owner_gate_required": owner_gate,
        }
        return ConstitutionDecision(
            admitted=not vetoes,
            vetoes=tuple(sorted(set(vetoes))),
            owner_gate_required=owner_gate,
            decision_sha256=_digest(body),
        )


@dataclass(frozen=True)
class CouncilMember:
    member_id: str
    role: InstitutionalRole
    independence_domain: str
    evidence_quality: float
    calibration: float
    confidence: float
    vote: float
    critical_veto: bool = False
    evidence_refs: tuple[str, ...] = ()

    @property
    def bounded_weight(self) -> float:
        # confidence alone cannot create authority; quality/calibration dominate.
        return max(0.01, _clip(self.evidence_quality) * _clip(self.calibration) * (0.5 + 0.5 * _clip(self.confidence)))


@dataclass(frozen=True)
class CouncilDecision:
    outcome: str
    support: float
    opposition: float
    independent_domains: int
    critical_vetoes: tuple[str, ...]
    dissent: tuple[str, ...]
    decision_sha256: str


class EvidenceWeightedCouncil:
    """Quorum where evidence quality and independence matter more than raw vote count."""

    def decide(
        self,
        members: Iterable[CouncilMember],
        *,
        support_threshold: float = 0.67,
        minimum_independent_domains: int = 3,
    ) -> CouncilDecision:
        member_list = tuple(members)
        if not member_list:
            raise ValueError("council requires members")
        domains = {item.independence_domain for item in member_list if item.independence_domain.strip()}
        vetoes = tuple(sorted(item.member_id for item in member_list if item.critical_veto))
        domain_counts: dict[str, int] = {}
        for item in member_list:
            domain_counts[item.independence_domain] = domain_counts.get(item.independence_domain, 0) + 1
        support = 0.0
        opposition = 0.0
        dissent: list[str] = []
        for item in member_list:
            diversity_discount = 1.0 / max(1, domain_counts.get(item.independence_domain, 1))
            weight = item.bounded_weight * diversity_discount
            signed = max(-1.0, min(1.0, float(item.vote)))
            if signed >= 0:
                support += signed * weight
            else:
                opposition += (-signed) * weight
                dissent.append(item.member_id)
        total = support + opposition
        ratio = support / total if total else 0.0
        if vetoes:
            outcome = "HELD_CRITICAL_VETO"
        elif len(domains) < minimum_independent_domains:
            outcome = "HELD_INSUFFICIENT_INDEPENDENCE"
        elif ratio >= support_threshold:
            outcome = "ADMIT"
        else:
            outcome = "HELD_NO_EVIDENCE_QUORUM"
        body = {
            "members": [asdict(item) for item in member_list],
            "ratio": ratio,
            "domains": sorted(domains),
            "vetoes": vetoes,
            "outcome": outcome,
        }
        return CouncilDecision(
            outcome=outcome,
            support=support,
            opposition=opposition,
            independent_domains=len(domains),
            critical_vetoes=vetoes,
            dissent=tuple(sorted(dissent)),
            decision_sha256=_digest(body),
        )


@dataclass(frozen=True)
class HorizonObjective:
    objective_id: str
    horizon: Horizon
    value: float
    urgency: float
    option_value: float
    dependency_centrality: float
    age_cycles: int = 0

    @property
    def priority(self) -> float:
        ageing = 1.0 + min(1.0, max(0, self.age_cycles) / 20.0)
        return ageing * (
            0.40 * _clip(self.value)
            + 0.25 * _clip(self.urgency)
            + 0.20 * _clip(self.option_value)
            + 0.15 * _clip(self.dependency_centrality)
        )


class MultiTimescalePlanner:
    """Selects across horizons while preventing long-horizon starvation."""

    _RESERVE = {
        Horizon.TACTICAL: 0.30,
        Horizon.OPERATIONAL: 0.30,
        Horizon.STRATEGIC: 0.25,
        Horizon.GENERATIONAL: 0.15,
    }

    def select(self, objectives: Iterable[HorizonObjective], *, slots: int) -> tuple[HorizonObjective, ...]:
        if slots < 1:
            raise ValueError("slots must be positive")
        items = tuple(objectives)
        by_horizon = {horizon: [] for horizon in Horizon}
        for item in items:
            by_horizon[item.horizon].append(item)
        for values in by_horizon.values():
            values.sort(key=lambda item: (-item.priority, item.objective_id))
        selected: list[HorizonObjective] = []
        selected_ids: set[str] = set()
        # reserve at least one slot for a non-empty horizon when capacity permits.
        nonempty = [h for h in Horizon if by_horizon[h]]
        if slots >= len(nonempty):
            for horizon in nonempty:
                chosen = by_horizon[horizon][0]
                selected.append(chosen)
                selected_ids.add(chosen.objective_id)
        remainder = sorted(
            (item for item in items if item.objective_id not in selected_ids),
            key=lambda item: (-item.priority * self._RESERVE[item.horizon], item.objective_id),
        )
        for item in remainder:
            if len(selected) >= slots:
                break
            selected.append(item)
        return tuple(selected[:slots])


@dataclass(frozen=True)
class ScenarioOption:
    option_id: str
    outcomes: Mapping[str, float]
    irreversible_risk: float = 0.0
    evidence_strength: float = 0.0


@dataclass(frozen=True)
class RobustChoice:
    option_id: str
    maximum_regret: float
    mean_regret: float
    adjusted_regret: float
    choice_sha256: str


class RobustScenarioPlanner:
    """Minimax-regret choice with bounded irreversibility/evidence adjustment."""

    def choose(self, options: Iterable[ScenarioOption]) -> RobustChoice:
        items = tuple(options)
        if not items:
            raise ValueError("scenario planner requires options")
        scenarios = sorted({key for item in items for key in item.outcomes})
        if not scenarios:
            raise ValueError("at least one scenario outcome is required")
        best_by_scenario = {scenario: max(float(item.outcomes.get(scenario, 0.0)) for item in items) for scenario in scenarios}
        ranked = []
        for item in items:
            regrets = [best_by_scenario[scenario] - float(item.outcomes.get(scenario, 0.0)) for scenario in scenarios]
            max_regret = max(regrets)
            mean_regret = sum(regrets) / len(regrets)
            adjusted = (
                max_regret
                + 0.25 * mean_regret
                + 0.50 * _clip(item.irreversible_risk)
                + 0.20 * (1.0 - _clip(item.evidence_strength))
            )
            ranked.append((adjusted, max_regret, mean_regret, item.option_id))
        ranked.sort()
        adjusted, max_regret, mean_regret, option_id = ranked[0]
        body = {"options": [asdict(item) for item in items], "scenarios": scenarios, "selected": option_id}
        return RobustChoice(option_id, max_regret, mean_regret, adjusted, _digest(body))


@dataclass(frozen=True)
class PolicyCandidate:
    policy_id: str
    stage: PolicyStage
    measured_gain: float = 0.0
    regression_score: float = 0.0
    independent_replications: int = 0
    rollback_verified: bool = False
    consequential: bool = False
    owner_approved: bool = False
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyTransition:
    admitted: bool
    from_stage: PolicyStage
    to_stage: PolicyStage
    blockers: tuple[str, ...]
    transition_sha256: str


class PolicyEvolutionLab:
    ORDER = (PolicyStage.CANDIDATE, PolicyStage.SHADOW, PolicyStage.CANARY, PolicyStage.ADOPTED)

    def promote(self, policy: PolicyCandidate, target: PolicyStage) -> PolicyTransition:
        blockers: list[str] = []
        if policy.stage not in self.ORDER or target not in self.ORDER:
            blockers.append("NON_PROMOTABLE_STAGE")
        else:
            current = self.ORDER.index(policy.stage)
            desired = self.ORDER.index(target)
            if desired != current + 1:
                blockers.append("STAGE_SKIP_PROHIBITED")
        if target in {PolicyStage.CANARY, PolicyStage.ADOPTED}:
            if policy.measured_gain <= 0:
                blockers.append("MEASURED_GAIN_REQUIRED")
            if policy.regression_score > 0:
                blockers.append("REGRESSION_PRESENT")
            if not policy.rollback_verified:
                blockers.append("ROLLBACK_PROOF_REQUIRED")
        if target == PolicyStage.ADOPTED and policy.independent_replications < 2:
            blockers.append("TWO_INDEPENDENT_REPLICATIONS_REQUIRED")
        if target == PolicyStage.ADOPTED and policy.consequential and not policy.owner_approved:
            blockers.append("OWNER_APPROVAL_REQUIRED")
        body = {"policy": asdict(policy), "target": target.value, "blockers": sorted(set(blockers))}
        return PolicyTransition(not blockers, policy.stage, target, tuple(sorted(set(blockers))), _digest(body))


@dataclass(frozen=True)
class ImprovementCandidate:
    improvement_id: str
    baseline_score: float
    candidate_score: float
    hard_regression: bool
    independent_reproduction: bool
    rollback_verified: bool
    authority_change: bool = False
    owner_approved: bool = False


class RecursiveImprovementGate:
    def evaluate(self, item: ImprovementCandidate) -> tuple[bool, tuple[str, ...], str]:
        blockers = []
        if item.candidate_score <= item.baseline_score:
            blockers.append("NO_MEASURED_GAIN")
        if item.hard_regression:
            blockers.append("HARD_REGRESSION")
        if not item.independent_reproduction:
            blockers.append("INDEPENDENT_REPRODUCTION_REQUIRED")
        if not item.rollback_verified:
            blockers.append("ROLLBACK_REQUIRED")
        if item.authority_change and not item.owner_approved:
            blockers.append("AUTHORITY_CHANGE_REQUIRES_OWNER")
        body = {"candidate": asdict(item), "blockers": sorted(blockers)}
        return (not blockers, tuple(sorted(blockers)), _digest(body))


@dataclass(frozen=True)
class Delegation:
    parent_id: str
    child_id: str
    parent_ceiling: AuthorityCeiling
    child_ceiling: AuthorityCeiling
    scope: tuple[str, ...]


class FractalDelegationGuard:
    def validate(self, delegation: Delegation) -> tuple[bool, str]:
        if _AUTHORITY_RANK[delegation.child_ceiling] > _AUTHORITY_RANK[delegation.parent_ceiling]:
            return False, "CHILD_AUTHORITY_EXPANSION"
        if not delegation.scope:
            return False, "EMPTY_SCOPE"
        return True, "NARROW_OR_EQUAL_AUTHORITY"


@dataclass(frozen=True)
class Anomaly:
    anomaly_id: str
    severity: AnomalySeverity
    affected_domains: tuple[str, ...]
    confidence: float
    reversible_containment: bool
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContainmentPlan:
    isolate_domains: tuple[str, ...]
    global_freeze: bool
    independent_work_may_continue: bool
    escalate_to_owner: bool
    plan_sha256: str


class InstitutionalImmuneSystem:
    def contain(self, anomaly: Anomaly, *, federation_domain_count: int) -> ContainmentPlan:
        if federation_domain_count < 1:
            raise ValueError("federation_domain_count must be positive")
        affected = tuple(sorted(set(anomaly.affected_domains)))
        global_freeze = (
            anomaly.severity == AnomalySeverity.CRITICAL
            and len(affected) >= federation_domain_count
            and _clip(anomaly.confidence) >= 0.9
        )
        escalate = anomaly.severity in {AnomalySeverity.HIGH, AnomalySeverity.CRITICAL} and not anomaly.reversible_containment
        body = {
            "anomaly": asdict(anomaly),
            "federation_domain_count": federation_domain_count,
            "global_freeze": global_freeze,
            "escalate": escalate,
        }
        return ContainmentPlan(
            isolate_domains=affected,
            global_freeze=global_freeze,
            independent_work_may_continue=not global_freeze,
            escalate_to_owner=escalate,
            plan_sha256=_digest(body),
        )


@dataclass(frozen=True)
class InstitutionalEvent:
    sequence: int
    event_type: str
    payload: Mapping[str, object]
    previous_hash: str
    event_hash: str


class InstitutionalMemory:
    """Append-only hash chain for public-safe institutional state transitions."""

    def __init__(self) -> None:
        self._events: list[InstitutionalEvent] = []

    def append(self, event_type: str, payload: Mapping[str, object]) -> InstitutionalEvent:
        if not event_type.strip():
            raise ValueError("event_type is required")
        sequence = len(self._events) + 1
        previous = self._events[-1].event_hash if self._events else "GENESIS"
        body = {"sequence": sequence, "event_type": event_type, "payload": dict(payload), "previous_hash": previous}
        event = InstitutionalEvent(sequence, event_type, dict(payload), previous, _digest(body))
        self._events.append(event)
        return event

    def events(self) -> tuple[InstitutionalEvent, ...]:
        return tuple(self._events)

    def verify(self) -> bool:
        previous = "GENESIS"
        for index, event in enumerate(self._events, start=1):
            if event.sequence != index or event.previous_hash != previous:
                return False
            body = {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "payload": dict(event.payload),
                "previous_hash": event.previous_hash,
            }
            if event.event_hash != _digest(body):
                return False
            previous = event.event_hash
        return True


@dataclass(frozen=True)
class InstitutionalCycleReceipt:
    constitution_sha256: str
    council_sha256: str
    robust_choice_sha256: str
    selected_objectives: tuple[str, ...]
    cycle_sha256: str


class FederatedCognitiveInstitution:
    """Thin institutional composition over existing MCE/AMCF/SOE semantics."""

    def __init__(self, *, institutional_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL) -> None:
        self.institutional_ceiling = institutional_ceiling
        self.constitution = ConstitutionKernel()
        self.council = EvidenceWeightedCouncil()
        self.timescales = MultiTimescalePlanner()
        self.scenarios = RobustScenarioPlanner()
        self.memory = InstitutionalMemory()

    def deliberate(
        self,
        *,
        proposal: InstitutionalProposal,
        council_members: Iterable[CouncilMember],
        objectives: Iterable[HorizonObjective],
        scenario_options: Iterable[ScenarioOption],
        slots: int,
        owner_approval: bool = False,
    ) -> InstitutionalCycleReceipt:
        constitutional = self.constitution.evaluate(
            proposal,
            institutional_ceiling=self.institutional_ceiling,
            owner_approval=owner_approval,
        )
        if not constitutional.admitted:
            raise ValueError(f"constitutional veto: {','.join(constitutional.vetoes)}")
        council = self.council.decide(council_members)
        if council.outcome != "ADMIT":
            raise ValueError(f"council hold: {council.outcome}")
        selected = self.timescales.select(objectives, slots=slots)
        robust = self.scenarios.choose(scenario_options)
        body = {
            "proposal_id": proposal.proposal_id,
            "constitution": constitutional.decision_sha256,
            "council": council.decision_sha256,
            "selected_objectives": [item.objective_id for item in selected],
            "robust_choice": robust.choice_sha256,
        }
        receipt = InstitutionalCycleReceipt(
            constitution_sha256=constitutional.decision_sha256,
            council_sha256=council.decision_sha256,
            robust_choice_sha256=robust.choice_sha256,
            selected_objectives=tuple(item.objective_id for item in selected),
            cycle_sha256=_digest(body),
        )
        self.memory.append("INSTITUTIONAL_CYCLE", {"receipt": asdict(receipt)})
        return receipt
