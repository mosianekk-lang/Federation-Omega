from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceSurface:
    name: str
    available: bool = True
    authority: str = "UNKNOWN"
    freshness: str = "UNKNOWN"
    cost: float = 1.0
    latency: float = 1.0
    notes: str = ""


@dataclass
class Unknown:
    unknown_id: str
    question: str
    decision_impact: float = 0.5
    information_gain: float = 0.5
    urgency: float = 0.5
    owner_only: bool = False
    source_hints: list[str] = field(default_factory=list)


@dataclass
class MatterPacket:
    matter_id: str
    objective: str
    forum: str = "UNKNOWN"
    stage: str = "UNKNOWN"
    facts: list[dict[str, Any]] = field(default_factory=list)
    disputed_facts: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[Unknown] = field(default_factory=list)
    legal_elements: list[str] = field(default_factory=list)
    remedies: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    sources: list[SourceSurface] = field(default_factory=list)
    prior_learning: list[dict[str, Any]] = field(default_factory=list)
    opponent_capabilities: list[str] = field(default_factory=list)
    cross_lane_risks: list[str] = field(default_factory=list)
    owner_preferences: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MatterPacket":
        unknowns = [u if isinstance(u, Unknown) else Unknown(**u) for u in raw.get("unknowns", [])]
        sources = [s if isinstance(s, SourceSurface) else SourceSurface(**s) for s in raw.get("sources", [])]
        return cls(
            matter_id=str(raw["matter_id"]),
            objective=str(raw["objective"]),
            forum=str(raw.get("forum", "UNKNOWN")),
            stage=str(raw.get("stage", "UNKNOWN")),
            facts=list(raw.get("facts", [])),
            disputed_facts=list(raw.get("disputed_facts", [])),
            unknowns=unknowns,
            legal_elements=list(raw.get("legal_elements", [])),
            remedies=list(raw.get("remedies", [])),
            constraints=list(raw.get("constraints", [])),
            sources=sources,
            prior_learning=list(raw.get("prior_learning", [])),
            opponent_capabilities=list(raw.get("opponent_capabilities", [])),
            cross_lane_risks=list(raw.get("cross_lane_risks", [])),
            owner_preferences=dict(raw.get("owner_preferences", {})),
        )


@dataclass
class RetrievalRoute:
    unknown_id: str
    surface: str
    query: str
    score: float
    reason: str
    executable: bool


@dataclass
class ForecastNode:
    step: int
    label: str
    scenario: str
    probability: float
    impact: float
    evidence_needed: list[str] = field(default_factory=list)
    fallback: str = ""


@dataclass
class StrategyCandidate:
    route_id: str
    name: str
    description: str
    expected_value: float
    reversibility: float
    information_gain: float
    owner_burden: float
    legal_risk: float
    proof_quality: float
    external_effect: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass
class ActionPacket:
    action_id: str
    action_type: str
    target: str
    state: str
    consequential: bool
    owner_approval_required: bool
    exact_target_digest: str
    prerequisites: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class LearningEvent:
    event_type: str
    fingerprint: str
    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    measurable_delta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyRun:
    run_id: str
    matter_id: str
    timestamp_utc: str
    mode: str
    access_resolution: dict[str, Any]
    ask_owner_allowed: bool
    case_twin: dict[str, Any]
    forecast_tree: list[ForecastNode]
    route_tournament: list[StrategyCandidate]
    selected_strategy: StrategyCandidate | None
    future_evidence_queue: list[dict[str, Any]]
    action_queue: list[ActionPacket]
    learning_events: list[LearningEvent]
    ao_cra_builds: list[dict[str, Any]]
    truth_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
