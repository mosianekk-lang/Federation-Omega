from __future__ import annotations

"""Market-leader convergence for Sentinel Ω incident-to-repair flow.

This is a composition layer, not a new scheduler, topology engine, or executor.
It combines patterns seen in causal AIOps, event orchestration, episode analytics,
and root-cause-to-code repair systems while preserving Federation proof and
authority boundaries.

The layer consumes already-normalized/clustered incident evidence and emits a
bounded repair work packet. Execution remains delegated to the existing SOL 6.1
repair fabric and provider-specific executors.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from formation_omega.autonomic_fabric import ActionCandidate

from .repair_binding import (
    BoundRepairPlan,
    ProviderAuthorityEvidence,
    RepairRunbookRegistry,
    SentinelRepairBinder,
)

SCHEMA = "SENTINEL-OMEGA-MARKET-LEADER-CONVERGENCE-V1"
EXTERNAL_EFFECTS = False


class OrchestrationAction(StrEnum):
    OBSERVE = "OBSERVE"
    PREWARM_DIAGNOSTICS = "PREWARM_DIAGNOSTICS"
    BIND_REPAIR = "BIND_REPAIR"
    HOLD = "HOLD"


class RepairWorkStage(StrEnum):
    ROOT_CAUSE_CANDIDATE = "ROOT_CAUSE_CANDIDATE"
    SOLUTION_CANDIDATE = "SOLUTION_CANDIDATE"
    REPAIR_PROOF_REQUIRED = "REPAIR_PROOF_REQUIRED"
    PROVIDER_EXECUTION_REQUIRED = "PROVIDER_EXECUTION_REQUIRED"
    HELD = "HELD"


@dataclass(frozen=True)
class IncidentContext:
    incident_id: str
    incident_class: str
    severity: int
    confidence: float
    probable_origin_ref: str | None
    affected_entities: tuple[str, ...]
    customer_impact: float
    business_impact: float
    blast_radius: int
    recent_change_refs: tuple[str, ...]
    trace_refs: tuple[str, ...]
    proof_refs: tuple[str, ...]

    def validate(self) -> "IncidentContext":
        if not self.incident_id.strip() or not self.incident_class.strip():
            raise ValueError("incident identity and class are required")
        if not 0 <= self.severity <= 5:
            raise ValueError("severity must be in [0,5]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")
        if not 0.0 <= self.customer_impact <= 1.0 or not 0.0 <= self.business_impact <= 1.0:
            raise ValueError("impact scores must be in [0,1]")
        if self.blast_radius < 0:
            raise ValueError("blast_radius must be non-negative")
        if not self.proof_refs:
            raise ValueError("incident proof_refs are required")
        return self

    @property
    def impact_priority(self) -> float:
        """Bounded impact score; evidence ranking only, never causal proof."""
        blast = min(self.blast_radius, 20) / 20.0
        return round(
            0.30 * (self.severity / 5.0)
            + 0.25 * self.customer_impact
            + 0.20 * self.business_impact
            + 0.15 * blast
            + 0.10 * self.confidence,
            6,
        )


@dataclass(frozen=True)
class EventOrchestrationRule:
    rule_id: str
    priority: int
    action: OrchestrationAction
    incident_classes: tuple[str, ...] = ()
    minimum_severity: int = 0
    minimum_confidence: float = 0.0
    minimum_impact_priority: float = 0.0
    require_probable_origin: bool = False
    require_change_or_trace_anchor: bool = False

    def matches(self, incident: IncidentContext) -> bool:
        if self.incident_classes and incident.incident_class not in self.incident_classes:
            return False
        if incident.severity < self.minimum_severity:
            return False
        if incident.confidence < self.minimum_confidence:
            return False
        if incident.impact_priority < self.minimum_impact_priority:
            return False
        if self.require_probable_origin and not incident.probable_origin_ref:
            return False
        if self.require_change_or_trace_anchor and not (incident.recent_change_refs or incident.trace_refs):
            return False
        return True


@dataclass(frozen=True)
class EventOrchestrationDecision:
    rule_id: str | None
    action: OrchestrationAction
    incident_id: str
    impact_priority: float
    proof_refs: tuple[str, ...]
    reason: str


class EventOrchestrationEngine:
    """Deterministic first-match rules; machine-speed routing without effects."""

    def __init__(self, rules: Iterable[EventOrchestrationRule] = ()) -> None:
        ordered = sorted(tuple(rules), key=lambda r: (-r.priority, r.rule_id))
        ids = [r.rule_id for r in ordered]
        if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("orchestration rule IDs must be non-empty and unique")
        self._rules = tuple(ordered)

    def decide(self, incident: IncidentContext) -> EventOrchestrationDecision:
        incident.validate()
        for rule in self._rules:
            if rule.matches(incident):
                return EventOrchestrationDecision(
                    rule_id=rule.rule_id,
                    action=rule.action,
                    incident_id=incident.incident_id,
                    impact_priority=incident.impact_priority,
                    proof_refs=tuple(sorted(set(incident.proof_refs))),
                    reason="MATCHED_POLICY_RULE",
                )
        return EventOrchestrationDecision(
            rule_id=None,
            action=OrchestrationAction.OBSERVE,
            incident_id=incident.incident_id,
            impact_priority=incident.impact_priority,
            proof_refs=tuple(sorted(set(incident.proof_refs))),
            reason="NO_RULE_MATCH_OBSERVE_ONLY",
        )


@dataclass(frozen=True)
class RepairWorkPacket:
    incident_id: str
    stage: RepairWorkStage
    probable_origin_ref: str | None
    diagnosis_refs: tuple[str, ...]
    solution_refs: tuple[str, ...]
    change_refs: tuple[str, ...]
    trace_refs: tuple[str, ...]
    orchestration_rule_id: str | None
    repair_plan: BoundRepairPlan | None
    external_effect_performed: bool
    truth_boundary: str


class RootCauseToRepairCompiler:
    """Sentry-style staged fix formation, bound to Federation repair gates."""

    def __init__(self, binder: SentinelRepairBinder | None = None) -> None:
        self._binder = binder or SentinelRepairBinder()

    def compile(
        self,
        *,
        incident: IncidentContext,
        decision: EventOrchestrationDecision,
        action_candidate: ActionCandidate | None,
        registry: RepairRunbookRegistry,
        provider_authority: ProviderAuthorityEvidence | None = None,
    ) -> RepairWorkPacket:
        incident.validate()
        if decision.incident_id != incident.incident_id:
            raise ValueError("decision/incident identity mismatch")
        diagnosis_refs = tuple(sorted(set(incident.proof_refs) | set(incident.trace_refs)))
        if decision.action in {OrchestrationAction.OBSERVE, OrchestrationAction.PREWARM_DIAGNOSTICS}:
            return RepairWorkPacket(
                incident_id=incident.incident_id,
                stage=RepairWorkStage.ROOT_CAUSE_CANDIDATE,
                probable_origin_ref=incident.probable_origin_ref,
                diagnosis_refs=diagnosis_refs,
                solution_refs=(),
                change_refs=incident.recent_change_refs,
                trace_refs=incident.trace_refs,
                orchestration_rule_id=decision.rule_id,
                repair_plan=None,
                external_effect_performed=False,
                truth_boundary="DIAGNOSIS_OR_PREWARM_ONLY_NO_REPAIR_EXECUTION",
            )
        if decision.action == OrchestrationAction.HOLD:
            return RepairWorkPacket(
                incident_id=incident.incident_id,
                stage=RepairWorkStage.HELD,
                probable_origin_ref=incident.probable_origin_ref,
                diagnosis_refs=diagnosis_refs,
                solution_refs=(),
                change_refs=incident.recent_change_refs,
                trace_refs=incident.trace_refs,
                orchestration_rule_id=decision.rule_id,
                repair_plan=None,
                external_effect_performed=False,
                truth_boundary="POLICY_HOLD_NO_REPAIR_EXECUTION",
            )
        if action_candidate is None:
            raise ValueError("BIND_REPAIR requires an ActionCandidate")
        plan = self._binder.bind(
            action_candidate,
            incident_class=incident.incident_class,
            registry=registry,
            provider_authority=provider_authority,
        )
        if plan.repair_candidate is None:
            stage = RepairWorkStage.HELD
            solution_refs: tuple[str, ...] = ()
        elif plan.external_effect:
            stage = RepairWorkStage.PROVIDER_EXECUTION_REQUIRED
            solution_refs = plan.proof_refs
        else:
            stage = RepairWorkStage.REPAIR_PROOF_REQUIRED
            solution_refs = plan.proof_refs
        return RepairWorkPacket(
            incident_id=incident.incident_id,
            stage=stage,
            probable_origin_ref=incident.probable_origin_ref,
            diagnosis_refs=diagnosis_refs,
            solution_refs=solution_refs,
            change_refs=incident.recent_change_refs,
            trace_refs=incident.trace_refs,
            orchestration_rule_id=decision.rule_id,
            repair_plan=plan,
            external_effect_performed=False,
            truth_boundary="REPAIR_FORMED_NOT_EXECUTED_REQUIRES_EXISTING_PROOF_AND_AUTHORITY_GATES",
        )


class MarketLeaderRepairConvergence:
    """One bounded facade for incident priority, orchestration, and repair formation."""

    def __init__(self, rules: Iterable[EventOrchestrationRule]) -> None:
        self._orchestration = EventOrchestrationEngine(rules)
        self._compiler = RootCauseToRepairCompiler()

    def route(
        self,
        incident: IncidentContext,
        *,
        action_candidate: ActionCandidate | None,
        registry: RepairRunbookRegistry,
        provider_authority: ProviderAuthorityEvidence | None = None,
    ) -> RepairWorkPacket:
        decision = self._orchestration.decide(incident)
        return self._compiler.compile(
            incident=incident,
            decision=decision,
            action_candidate=action_candidate,
            registry=registry,
            provider_authority=provider_authority,
        )
