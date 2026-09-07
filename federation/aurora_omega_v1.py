"""FUSE AURORA-Ω v1 clean-room frontier agent harness.

This module intentionally implements *observable operating behaviours* associated
with strong long-horizon agents. It does not copy or claim access to proprietary
model weights, system prompts, training data, or confidential vendor internals.

AURORA-Ω is provider-agnostic. The deterministic kernel governs mission state,
route formation, specialist allocation, failure recovery, evidence, context
handoffs, and completion. A model/provider adapter may be attached separately.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence


class MissionPhase(str, Enum):
    INTAKE = "INTAKE"
    APPRECIATE = "APPRECIATE"
    DISCOVER = "DISCOVER"
    FORM = "FORM"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    RECOVER = "RECOVER"
    COMPLETE = "COMPLETE"


class TerminalEvent(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CONSTRAINT = "CONSTRAINT"
    CORRECTION = "CORRECTION"
    RECOVERY = "RECOVERY"
    INNOVATION_CANDIDATE = "INNOVATION_CANDIDATE"
    EXPERIMENT_RESULT = "EXPERIMENT_RESULT"
    NEGATIVE_RESULT = "NEGATIVE_RESULT"


class SpecialistRole(str, Enum):
    MISSION_PLANNER = "MISSION_PLANNER"
    INNOVATION_HISTORIAN = "INNOVATION_HISTORIAN"
    SYNTHESIS_SCHOLAR = "SYNTHESIS_SCHOLAR"
    RESEARCHER = "RESEARCHER"
    ROOT_CAUSE_INVESTIGATOR = "ROOT_CAUSE_INVESTIGATOR"
    BUILDER = "BUILDER"
    CHALLENGER = "CHALLENGER"
    VERIFIER = "VERIFIER"
    VISUAL_REVIEWER = "VISUAL_REVIEWER"
    KNOWLEDGE_CURATOR = "KNOWLEDGE_CURATOR"


class Lens(str, Enum):
    GENIUS_APPRECIATION = "GENIUS_APPRECIATION"
    BALANCED = "BALANCED"
    TECHNICAL = "TECHNICAL"
    ADVERSARIAL = "ADVERSARIAL"


@dataclass(frozen=True)
class LensWeights:
    originality: float
    synthesis: float
    significance: float
    execution: float
    rigor: float
    risk: float


LENS_WEIGHTS: Mapping[Lens, LensWeights] = {
    Lens.GENIUS_APPRECIATION: LensWeights(1.0, 1.0, 1.0, 0.35, 0.55, 0.25),
    Lens.BALANCED: LensWeights(0.7, 0.7, 0.7, 0.7, 0.8, 0.65),
    Lens.TECHNICAL: LensWeights(0.35, 0.45, 0.45, 1.0, 1.0, 0.8),
    Lens.ADVERSARIAL: LensWeights(0.25, 0.35, 0.35, 0.7, 1.0, 1.0),
}


@dataclass(frozen=True)
class MissionContract:
    objective: str
    completion_predicates: tuple[str, ...]
    lens: Lens = Lens.BALANCED
    authority_ceiling: str = "A1_INTERNAL"
    external_effects_allowed: bool = False
    require_independent_verification: bool = True
    require_root_cause_on_failure: bool = True


@dataclass(frozen=True)
class AppreciationFinding:
    finding_id: str
    kind: str
    claim: str
    evidence_refs: tuple[str, ...] = ()
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if self.kind not in {"ORIGINALITY", "SYNTHESIS", "SIGNIFICANCE", "LINEAGE"}:
            raise ValueError(f"unsupported appreciation kind: {self.kind}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(frozen=True)
class Evidence:
    ref: str
    kind: str
    claim: str
    verified: bool = False
    independent: bool = False
    provider_native: bool = False


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    description: str
    success_probability: float = 0.5
    impact: float = 0.5
    information_gain: float = 0.0
    reuse_value: float = 0.0
    reversibility: float = 0.5
    proofability: float = 0.5
    cost: float = 0.0
    latency: float = 0.0
    authority_risk: float = 0.0
    duplication: float = 0.0
    coordination_overhead: float = 0.0
    collision_key: str | None = None
    parallel_safe: bool = True
    family: str = "GENERAL"

    def score(self) -> float:
        values = (
            self.success_probability,
            self.impact,
            self.information_gain,
            self.reuse_value,
            self.reversibility,
            self.proofability,
            self.cost,
            self.latency,
            self.authority_risk,
            self.duplication,
            self.coordination_overhead,
        )
        if any((not math.isfinite(v)) for v in values):
            raise ValueError("route score inputs must be finite")
        return (
            (self.success_probability * self.impact)
            + self.information_gain
            + self.reuse_value
            + self.reversibility
            + self.proofability
            - self.cost
            - self.latency
            - self.authority_risk
            - self.duplication
            - self.coordination_overhead
        )


@dataclass(frozen=True)
class WorkPacket:
    packet_id: str
    role: SpecialistRole
    objective: str
    dependencies: tuple[str, ...] = ()
    parallel_safe: bool = True
    collision_key: str | None = None
    required_evidence_kinds: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()
    authority: str = "READ_ONLY"
    external_effect: bool = False


@dataclass(frozen=True)
class AgentEvent:
    sequence: int
    event_type: TerminalEvent
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str


@dataclass
class MissionState:
    mission_id: str
    contract: MissionContract
    version: int = 1
    phase: MissionPhase = MissionPhase.INTAKE
    routes: list[RouteCandidate] = field(default_factory=list)
    selected_route_ids: list[str] = field(default_factory=list)
    appreciation_findings: list[AppreciationFinding] = field(default_factory=list)
    open_unknowns: list[str] = field(default_factory=list)
    root_causes: dict[str, str] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)
    failure_fingerprints: dict[str, str] = field(default_factory=dict)
    banned_routes: set[str] = field(default_factory=set)
    evidence: list[Evidence] = field(default_factory=list)
    specialist_roster: list[SpecialistRole] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)
    satisfied_predicates: set[str] = field(default_factory=set)
    critical_unknowns: set[str] = field(default_factory=set)
    artifacts: list[str] = field(default_factory=list)

    def bump(self, phase: MissionPhase | None = None) -> None:
        self.version += 1
        if phase is not None:
            self.phase = phase


@dataclass(frozen=True)
class CompletionDecision:
    complete: bool
    state: str
    missing_predicates: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelRequest:
    mission_id: str
    mission_version: int
    phase: MissionPhase
    role: SpecialistRole
    lens: Lens
    objective: str
    context: Mapping[str, Any]
    response_contract: Mapping[str, str]


@dataclass(frozen=True)
class ModelResponse:
    role: SpecialistRole
    findings: tuple[Mapping[str, Any], ...] = ()
    proposed_routes: tuple[RouteCandidate, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    unknowns: tuple[str, ...] = ()
    terminal_event: TerminalEvent | None = None


class ModelDriver(Protocol):
    """Minimal provider-neutral model driver contract."""

    def run(self, request: ModelRequest) -> ModelResponse:
        ...


class AuroraOmegaAgent:
    """Deterministic governance and orchestration kernel for AURORA-Ω."""

    VERSION = "1.0.0"
    SCHEMA = "FUSE-AURORA-OMEGA-V1"
    AUTHORITY_CEILING = "A1_INTERNAL"

    APPRECIATION_MINIMUM = {
        "ORIGINALITY": 1,
        "SYNTHESIS": 1,
        "SIGNIFICANCE": 1,
    }

    DEFAULT_CONTEXT_EVENT_WINDOW = 12

    def new_mission(
        self,
        mission_id: str,
        objective: str,
        completion_predicates: Sequence[str],
        *,
        lens: Lens = Lens.BALANCED,
        external_effects_allowed: bool = False,
    ) -> MissionState:
        if not mission_id.strip():
            raise ValueError("mission_id is required")
        if not objective.strip():
            raise ValueError("objective is required")
        predicates = tuple(p.strip() for p in completion_predicates if p.strip())
        if not predicates:
            raise ValueError("at least one completion predicate is required")
        contract = MissionContract(
            objective=objective.strip(),
            completion_predicates=predicates,
            lens=lens,
            authority_ceiling=self.AUTHORITY_CEILING,
            external_effects_allowed=bool(external_effects_allowed),
        )
        phase = MissionPhase.APPRECIATE if lens == Lens.GENIUS_APPRECIATION else MissionPhase.DISCOVER
        return MissionState(mission_id=mission_id.strip(), contract=contract, phase=phase)

    @staticmethod
    def lens_weights(lens: Lens) -> LensWeights:
        return LENS_WEIGHTS[lens]

    def add_appreciation_finding(
        self, state: MissionState, finding: AppreciationFinding
    ) -> None:
        state.appreciation_findings.append(finding)
        state.bump()

    def appreciation_gate(self, state: MissionState) -> tuple[bool, tuple[str, ...]]:
        if state.contract.lens != Lens.GENIUS_APPRECIATION:
            return True, ()
        counts: dict[str, int] = {}
        for finding in state.appreciation_findings:
            if finding.confidence >= 0.5:
                counts[finding.kind] = counts.get(finding.kind, 0) + 1
        missing = tuple(
            kind
            for kind, minimum in self.APPRECIATION_MINIMUM.items()
            if counts.get(kind, 0) < minimum
        )
        return not missing, missing

    def can_enter_technical_critique(self, state: MissionState) -> bool:
        passed, _ = self.appreciation_gate(state)
        return passed

    def select_specialists(
        self,
        state: MissionState,
        *,
        complexity: float = 0.5,
        stakes: float = 0.5,
        visual_material: bool = False,
    ) -> tuple[SpecialistRole, ...]:
        roles: list[SpecialistRole] = [SpecialistRole.MISSION_PLANNER]
        if state.contract.lens == Lens.GENIUS_APPRECIATION:
            roles += [
                SpecialistRole.INNOVATION_HISTORIAN,
                SpecialistRole.SYNTHESIS_SCHOLAR,
            ]
        roles.append(SpecialistRole.RESEARCHER)
        if complexity >= 0.6:
            roles += [
                SpecialistRole.ROOT_CAUSE_INVESTIGATOR,
                SpecialistRole.BUILDER,
            ]
        if stakes >= 0.5 or complexity >= 0.7:
            roles += [SpecialistRole.CHALLENGER, SpecialistRole.VERIFIER]
        if visual_material:
            roles.append(SpecialistRole.VISUAL_REVIEWER)
        roles.append(SpecialistRole.KNOWLEDGE_CURATOR)

        deduped = tuple(dict.fromkeys(roles))
        state.specialist_roster = list(deduped)
        state.bump()
        return deduped

    @staticmethod
    def _route_materially_distinct(a: RouteCandidate, b: RouteCandidate) -> bool:
        if a.family != b.family:
            return True
        wa = set(re.findall(r"[a-z0-9]+", a.description.lower()))
        wb = set(re.findall(r"[a-z0-9]+", b.description.lower()))
        if not wa or not wb:
            return a.route_id != b.route_id
        jaccard = len(wa & wb) / len(wa | wb)
        return jaccard < 0.65

    def rank_routes(
        self, state: MissionState, routes: Iterable[RouteCandidate]
    ) -> tuple[RouteCandidate, ...]:
        eligible = [r for r in routes if r.route_id not in state.banned_routes]
        return tuple(sorted(eligible, key=lambda r: (r.score(), r.route_id), reverse=True))

    def should_spawn_path(
        self,
        candidate: RouteCandidate,
        selected: Sequence[RouteCandidate],
        *,
        marginal_value_floor: float = 0.25,
    ) -> bool:
        if not candidate.parallel_safe or candidate.score() < marginal_value_floor:
            return False
        for existing in selected:
            if (
                candidate.collision_key is not None
                and existing.collision_key == candidate.collision_key
            ):
                return False
            if not self._route_materially_distinct(candidate, existing):
                return False
        return True

    def select_parallel_routes(
        self,
        state: MissionState,
        routes: Iterable[RouteCandidate],
        *,
        max_paths: int = 4,
        marginal_value_floor: float = 0.25,
    ) -> tuple[RouteCandidate, ...]:
        ranked = self.rank_routes(state, routes)
        selected: list[RouteCandidate] = []
        for candidate in ranked:
            if len(selected) >= max_paths:
                break
            if self.should_spawn_path(
                candidate, selected, marginal_value_floor=marginal_value_floor
            ):
                selected.append(candidate)
        state.routes = list(ranked)
        state.selected_route_ids = [r.route_id for r in selected]
        state.bump(MissionPhase.PLAN if selected else MissionPhase.FORM)
        return tuple(selected)

    def plan_packets(
        self, state: MissionState, objective_by_role: Mapping[SpecialistRole, str]
    ) -> tuple[WorkPacket, ...]:
        if not state.specialist_roster:
            self.select_specialists(state)
        packets: list[WorkPacket] = []
        for idx, role in enumerate(state.specialist_roster, start=1):
            objective = objective_by_role.get(role, state.contract.objective)
            parallel_safe = role not in {SpecialistRole.BUILDER}
            collision_key = "shared-build-target" if role == SpecialistRole.BUILDER else None
            required = ("INDEPENDENT_VERIFICATION",) if role == SpecialistRole.VERIFIER else ()
            packets.append(
                WorkPacket(
                    packet_id=f"{state.mission_id}-P{idx:03d}",
                    role=role,
                    objective=objective,
                    parallel_safe=parallel_safe,
                    collision_key=collision_key,
                    required_evidence_kinds=required,
                )
            )
        return tuple(packets)

    @staticmethod
    def _event_hash(
        sequence: int,
        event_type: TerminalEvent,
        payload: Mapping[str, Any],
        previous_hash: str,
    ) -> str:
        canonical = json.dumps(
            {
                "sequence": sequence,
                "event_type": event_type.value,
                "payload": payload,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def record_event(
        self,
        state: MissionState,
        event_type: TerminalEvent,
        payload: Mapping[str, Any],
    ) -> AgentEvent:
        sequence = len(state.events) + 1
        previous_hash = state.events[-1].event_hash if state.events else "GENESIS"
        event_hash = self._event_hash(sequence, event_type, payload, previous_hash)
        event = AgentEvent(
            sequence=sequence,
            event_type=event_type,
            payload=dict(payload),
            previous_hash=previous_hash,
            event_hash=event_hash,
        )
        state.events.append(event)
        state.bump()
        return event

    def verify_event_chain(self, state: MissionState) -> bool:
        previous = "GENESIS"
        for idx, event in enumerate(state.events, start=1):
            if event.sequence != idx or event.previous_hash != previous:
                return False
            expected = self._event_hash(
                event.sequence, event.event_type, event.payload, previous
            )
            if event.event_hash != expected:
                return False
            previous = event.event_hash
        return True

    def record_failure(
        self,
        state: MissionState,
        *,
        route_id: str,
        fingerprint: str,
        error: str,
        root_cause: str | None = None,
    ) -> None:
        count = state.failure_counts.get(route_id, 0) + 1
        prior_fingerprint = state.failure_fingerprints.get(route_id)
        state.failure_counts[route_id] = count
        state.failure_fingerprints[route_id] = fingerprint
        repeated = prior_fingerprint == fingerprint or count >= 2
        if repeated:
            state.banned_routes.add(route_id)
        if root_cause:
            state.root_causes[fingerprint] = root_cause
        state.phase = MissionPhase.RECOVER
        self.record_event(
            state,
            TerminalEvent.FAILURE,
            {
                "route_id": route_id,
                "fingerprint": fingerprint,
                "error": error,
                "repeated": repeated,
                "root_cause_known": bool(root_cause),
            },
        )

    def failure_can_close(self, state: MissionState, fingerprint: str) -> bool:
        if not state.contract.require_root_cause_on_failure:
            return True
        return bool(state.root_causes.get(fingerprint, "").strip())

    def recovery_route(
        self, state: MissionState, routes: Iterable[RouteCandidate]
    ) -> RouteCandidate | None:
        ranked = self.rank_routes(state, routes)
        for route in ranked:
            if route.route_id not in state.banned_routes:
                return route
        return None

    def add_evidence(self, state: MissionState, *items: Evidence) -> None:
        state.evidence.extend(items)
        state.bump()

    @staticmethod
    def _tokenize_query(query: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9_]+", query.lower())
            if len(token) > 1
        }

    def tool_search(
        self,
        query: str,
        catalog: Sequence[ToolDescriptor],
        *,
        limit: int = 8,
        allow_external_effects: bool = False,
    ) -> tuple[ToolDescriptor, ...]:
        q = self._tokenize_query(query)
        scored: list[tuple[float, ToolDescriptor]] = []
        for tool in catalog:
            if tool.external_effect and not allow_external_effects:
                continue
            hay = " ".join((tool.name, tool.description, *tool.tags)).lower()
            tokens = self._tokenize_query(hay)
            overlap = len(q & tokens)
            if overlap == 0:
                continue
            score = overlap / max(1, len(q))
            if any(term in tool.name.lower() for term in q):
                score += 0.25
            scored.append((score, tool))
        scored.sort(key=lambda pair: (pair[0], pair[1].tool_id), reverse=True)
        return tuple(tool for _, tool in scored[: max(1, limit)])

    def compact_context(
        self,
        state: MissionState,
        *,
        event_window: int | None = None,
    ) -> Mapping[str, Any]:
        window = self.DEFAULT_CONTEXT_EVENT_WINDOW if event_window is None else max(0, event_window)
        recent_events = state.events[-window:] if window else []
        return {
            "schema": self.SCHEMA,
            "agent_version": self.VERSION,
            "mission_id": state.mission_id,
            "mission_version": state.version,
            "objective": state.contract.objective,
            "completion_predicates": list(state.contract.completion_predicates),
            "satisfied_predicates": sorted(state.satisfied_predicates),
            "phase": state.phase.value,
            "lens": state.contract.lens.value,
            "authority_ceiling": state.contract.authority_ceiling,
            "external_effects_allowed": state.contract.external_effects_allowed,
            "selected_route_ids": list(state.selected_route_ids),
            "banned_routes": sorted(state.banned_routes),
            "open_unknowns": list(state.open_unknowns),
            "critical_unknowns": sorted(state.critical_unknowns),
            "root_causes": dict(state.root_causes),
            "evidence_refs": [e.ref for e in state.evidence if e.verified],
            "appreciation_findings": [
                {
                    "finding_id": f.finding_id,
                    "kind": f.kind,
                    "claim": f.claim,
                    "evidence_refs": list(f.evidence_refs),
                    "confidence": f.confidence,
                }
                for f in state.appreciation_findings
            ],
            "recent_events": [
                {
                    "sequence": e.sequence,
                    "event_type": e.event_type.value,
                    "payload": dict(e.payload),
                    "event_hash": e.event_hash,
                }
                for e in recent_events
            ],
            "event_chain_tip": state.events[-1].event_hash if state.events else "GENESIS",
        }

    def make_model_request(
        self,
        state: MissionState,
        role: SpecialistRole,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> ModelRequest:
        return ModelRequest(
            mission_id=state.mission_id,
            mission_version=state.version,
            phase=state.phase,
            role=role,
            lens=state.contract.lens,
            objective=state.contract.objective,
            context=context or self.compact_context(state),
            response_contract={
                "findings": "list[structured finding]",
                "proposed_routes": "list[RouteCandidate]",
                "evidence": "list[Evidence]",
                "unknowns": "list[str]",
                "terminal_event": "optional TerminalEvent",
            },
        )

    def apply_model_response(
        self, state: MissionState, response: ModelResponse
    ) -> None:
        if response.proposed_routes:
            state.routes.extend(response.proposed_routes)
        if response.evidence:
            state.evidence.extend(response.evidence)
        if response.unknowns:
            for unknown in response.unknowns:
                if unknown not in state.open_unknowns:
                    state.open_unknowns.append(unknown)
        if response.terminal_event is not None:
            self.record_event(
                state,
                response.terminal_event,
                {"role": response.role.value, "findings": len(response.findings)},
            )
        else:
            state.bump()

    def completion_gate(self, state: MissionState) -> CompletionDecision:
        missing_predicates = tuple(
            p for p in state.contract.completion_predicates
            if p not in state.satisfied_predicates
        )
        missing_requirements: list[str] = []
        if state.critical_unknowns:
            missing_requirements.append("CRITICAL_UNKNOWNS_OPEN")
        if not self.verify_event_chain(state):
            missing_requirements.append("EVENT_CHAIN_INVALID")

        if state.contract.require_independent_verification:
            independent = any(
                e.verified and e.independent for e in state.evidence
            )
            if not independent:
                missing_requirements.append("INDEPENDENT_VERIFICATION_MISSING")

        passed, appreciation_missing = self.appreciation_gate(state)
        if not passed:
            missing_requirements.extend(f"APPRECIATION_{x}_MISSING" for x in appreciation_missing)

        complete = not missing_predicates and not missing_requirements
        return CompletionDecision(
            complete=complete,
            state="COMPLETE_VERIFIED" if complete else "INCOMPLETE",
            missing_predicates=missing_predicates,
            missing_requirements=tuple(missing_requirements),
        )

    def mark_predicate_satisfied(self, state: MissionState, predicate: str) -> None:
        if predicate not in state.contract.completion_predicates:
            raise ValueError(f"predicate is not in mission contract: {predicate}")
        state.satisfied_predicates.add(predicate)
        state.bump()

    def bounded_autonomy_allowed(self, state: MissionState, *, external_effect: bool) -> bool:
        if external_effect and not state.contract.external_effects_allowed:
            return False
        return state.contract.authority_ceiling == self.AUTHORITY_CEILING

    def status_projection(self, state: MissionState) -> Mapping[str, Any]:
        decision = self.completion_gate(state)
        return {
            "mission_id": state.mission_id,
            "phase": state.phase.value,
            "version": state.version,
            "selected_routes": list(state.selected_route_ids),
            "open_unknowns": list(state.open_unknowns),
            "banned_routes": sorted(state.banned_routes),
            "proof_refs": [e.ref for e in state.evidence if e.verified],
            "completion": asdict(decision),
        }
