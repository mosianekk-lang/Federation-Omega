"""FUSE Master Bible Production Portfolio Compiler v1.

Provider-neutral, effect-free implementation of the MBMPC portfolio algorithm. It
consumes current snapshots from existing Federation sources (FDOF Missions, Gap
Closure Ledger, Capability Deficit Map or equivalent projections) and compiles one
deterministic production portfolio / execution graph without creating another truth,
authority, scheduler, memory or proof plane.

The compiler is intentionally conservative: it only promotes maturity from explicit
proof/state markers or caller-supplied P-stage evidence. Source/CI never self-promotes
to host/runtime/provider maturity. Owner-only gaps remain visible debt but never freeze
independent safe machine work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence

from federation.fuse_mbmpc_pilf_closure_bridge_v1 import PStage

SCHEMA = "FUSE-MASTER-BIBLE-PRODUCTION-PORTFOLIO-V1"
VERSION = "1.0.0"


class MissionClass(str, Enum):
    CONSTITUTIONAL_CONTROL = "CONSTITUTIONAL_CONTROL"
    CAPABILITY_MISSION = "CAPABILITY_MISSION"
    RUNTIME_MISSION = "RUNTIME_MISSION"
    PROVIDER_BINDING_MISSION = "PROVIDER_BINDING_MISSION"
    SECURITY_ASSURANCE_MISSION = "SECURITY_ASSURANCE_MISSION"
    PRODUCT_MISSION = "PRODUCT_MISSION"
    DOMAIN_MISSION = "DOMAIN_MISSION"
    RESEARCH_EXPERIMENT = "RESEARCH_EXPERIMENT"
    PORTFOLIO_PROGRAM = "PORTFOLIO_PROGRAM"
    HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"


_TERMINAL_STATES = (
    "COMPLETE_VERIFIED",
    "SUPERSEDED_WITH_PROOF",
    "RETIRED_BY_OWNER",
    "RETIRED_BY_CONSTITUTION",
)

_STAGE_MARKERS: tuple[tuple[PStage, tuple[str, ...]], ...] = (
    (PStage.P18_FRONTIER_SUPERIOR_VERIFIED, ("FRONTIER_SUPERIOR_VERIFIED",)),
    (PStage.P17_CONTINUOUS_IMPROVEMENT_ACTIVE, ("CONTINUOUS_IMPROVEMENT_ACTIVE",)),
    (PStage.P16_VALUE_OBSERVED, ("VALUE_OBSERVED", "VALUE_VERIFIED")),
    (PStage.P15_PRODUCTION_PROMOTED, ("PRODUCTION_PROMOTED",)),
    (PStage.P14_PRODUCTION_QUALIFIED, ("PRODUCTION_QUALIFIED",)),
    (PStage.P13_BEHAVIOUR_VERIFIED, ("BEHAVIOUR_VERIFIED", "BEHAVIOR_VERIFIED")),
    (PStage.P12_SEMANTIC_READBACK_VERIFIED, ("SEMANTIC_READBACK_VERIFIED", "SEMANTIC_VERIFIED")),
    (PStage.P11_PROVIDER_RUNNING, ("PROVIDER_RUNNING", "PROVIDER_EXECUTED")),
    (PStage.P10_HOST_BOUND, ("HOST_BOUND", "HOSTED_ADOPTER_PRESENT", "HOST_BINDING_VERIFIED")),
    (PStage.P9_SOURCE_ADMITTED, ("SOURCE_ADMITTED", "MERGED_SIGNED_MAIN_READBACK_VERIFIED")),
    (PStage.P8_LOCAL_ASSURED, ("LOCAL_ASSURED", "LOCAL_TESTED", "TESTED_LOCAL", "EXACT_HEAD_THREE_GATE_PASS")),
    (PStage.P7_BUILT, ("BUILT", "IMPLEMENTED")),
    (PStage.P6_IMPLEMENTATION_PLAN_READY, ("IMPLEMENTATION_PLAN_READY",)),
    (PStage.P5_ROUTE_SELECTED, ("ROUTE_SELECTED", "ROUTE_QUALIFIED")),
    (PStage.P4_GAP_GRAPH_COMPILED, ("GAP_GRAPH_COMPILED", "REQUIREMENT_GAP_GRAPH_COMPILED")),
    (PStage.P3_CURRENT_STATE_CENSUSED, ("CURRENT_STATE_CENSUSED", "CENSUS_COMPLETE", "BASELINE_COMPLETE")),
    (PStage.P2_REQUIREMENTS_COMPILED, ("REQUIREMENTS_COMPILED",)),
    (PStage.P1_INTENT_BOUND, ("INTENT_BOUND",)),
)


_CLASSIFICATION_WEIGHT = {
    "MISSING": 35.0,
    "UNBOUND": 32.0,
    "UNPROVEN": 28.0,
    "PROVIDER_HELD": 24.0,
    "CLOSING": 14.0,
    "OWNER_ONLY": 5.0,
}

_PRIORITY_WEIGHT = {"P0": 30.0, "P1": 18.0, "P2": 10.0, "P3": 4.0}


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _split(value: object) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    return tuple(sorted({part.strip() for part in re.split(r"[;,|]", text) if part.strip()}))


def _stage_from_text(value: str) -> PStage:
    upper = value.upper()
    for stage, markers in _STAGE_MARKERS:
        if any(marker in upper for marker in markers):
            return stage
    return PStage.P0_CANONICAL_DISCOVERED


def _mission_class_from_text(mission_id: str, objective: str) -> MissionClass:
    text = f"{mission_id} {objective}".upper()
    if any(token in text for token in ("CONSTITUTION", "GOVERNANCE", "CONTROL PLANE", "INTERLOCK")):
        return MissionClass.CONSTITUTIONAL_CONTROL
    if any(token in text for token in ("SECURITY", "ASSURANCE", "PROOFOS", "AIRLOCK")):
        return MissionClass.SECURITY_ASSURANCE_MISSION
    if any(token in text for token in ("PROVIDER", "APPS SCRIPT", "VERTEX", "GEMINI", "COPILOT", "OAUTH")):
        return MissionClass.PROVIDER_BINDING_MISSION
    if any(token in text for token in ("RUNTIME", "SCHEDULER", "24X7", "24/7", "HOST", "WORKER")):
        return MissionClass.RUNTIME_MISSION
    if "PORTFOLIO" in text or "ESTATE" in text:
        return MissionClass.PORTFOLIO_PROGRAM
    if "EXPERIMENT" in text or "SHADOW" in text:
        return MissionClass.RESEARCH_EXPERIMENT
    return MissionClass.CAPABILITY_MISSION


@dataclass(frozen=True, slots=True)
class MissionRecord:
    mission_id: str
    objective: str
    state: str
    proof_state: str
    next_action: str
    authority_ceiling: str = "A1_INTERNAL"
    priority: str = "P1"
    parent_mission_id: str = ""
    owner_intent_id: str = ""
    mission_class: MissionClass | None = None
    current_p_stage: PStage | None = None
    required_p_stage: PStage | None = None
    required_terminal_predicates: tuple[str, ...] = ()
    satisfied_terminal_predicates: tuple[str, ...] = ()
    source_ref: str = ""

    def validate(self) -> "MissionRecord":
        if not self.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if not self.objective.strip():
            raise ValueError(f"MISSION_OBJECTIVE_REQUIRED:{self.mission_id}")
        return self

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "MissionRecord":
        mission_id = _clean(row.get("Mission_ID"))
        objective = _clean(row.get("Objective"))
        mission_class_raw = _clean(row.get("Mission_Class"))
        mission_class = MissionClass(mission_class_raw) if mission_class_raw else None
        current_raw = _clean(row.get("Current_P_Stage"))
        required_raw = _clean(row.get("Required_P_Stage"))
        current = PStage[current_raw] if current_raw else None
        required = PStage[required_raw] if required_raw else None
        return cls(
            mission_id=mission_id,
            objective=objective,
            state=_clean(row.get("State")),
            proof_state=_clean(row.get("Proof_State")),
            next_action=_clean(row.get("Next_Action")),
            authority_ceiling=_clean(row.get("Authority_Ceiling")) or "A1_INTERNAL",
            priority=_clean(row.get("Priority")) or "P1",
            parent_mission_id=_clean(row.get("Parent_Mission_ID")),
            owner_intent_id=_clean(row.get("Owner_Intent_ID")),
            mission_class=mission_class,
            current_p_stage=current,
            required_p_stage=required,
            required_terminal_predicates=_split(row.get("Required_Terminal_Predicates")),
            satisfied_terminal_predicates=_split(row.get("Satisfied_Terminal_Predicates")),
            source_ref=_clean(row.get("Source_Ref")),
        ).validate()

    def resolved_class(self) -> MissionClass:
        return self.mission_class or _mission_class_from_text(self.mission_id, self.objective)

    def resolved_current_stage(self) -> PStage:
        if self.current_p_stage is not None:
            return self.current_p_stage
        return _stage_from_text(f"{self.state} {self.proof_state}")

    def resolved_required_stage(self) -> PStage:
        if self.required_p_stage is not None:
            return self.required_p_stage
        cls = self.resolved_class()
        text = f"{self.mission_id} {self.objective} {self.state}".upper()
        if "SOURCE-ADMISSION" in self.mission_id.upper() and not any(
            token in text for token in ("PRODUCTION", "RUNTIME", "PROVIDER RUNNING")
        ):
            return PStage.P9_SOURCE_ADMITTED
        if cls in {MissionClass.CONSTITUTIONAL_CONTROL, MissionClass.SECURITY_ASSURANCE_MISSION}:
            baseline = PStage.P13_BEHAVIOUR_VERIFIED
        elif cls is MissionClass.RESEARCH_EXPERIMENT:
            baseline = PStage.P13_BEHAVIOUR_VERIFIED
        elif cls is MissionClass.PROVIDER_BINDING_MISSION:
            baseline = PStage.P12_SEMANTIC_READBACK_VERIFIED
        else:
            baseline = PStage.P15_PRODUCTION_PROMOTED
        if any(token in text for token in ("FRONTIER_SUPERIOR", " 10X", " 2X", "MARKET-LEADING", "DOMINANCE", "SUPERIORITY")):
            return max(baseline, PStage.P18_FRONTIER_SUPERIOR_VERIFIED)
        if any(token in text for token in ("CONTINUOUS IMPROVEMENT", "24X7", "24/7", "AUTONOMIC", "GOVERNED AUTONOMY", "SELF-IMPROV")):
            return max(baseline, PStage.P17_CONTINUOUS_IMPROVEMENT_ACTIVE)
        if any(token in text for token in ("OWNER VALUE", "OWNER-VALUE", "MEASURABLE VALUE", "VALUE OBSERVED")):
            return max(baseline, PStage.P16_VALUE_OBSERVED)
        if "HOST ADOPTER" in text and cls is MissionClass.RUNTIME_MISSION and "PRODUCTION" not in text:
            return PStage.P10_HOST_BOUND
        return baseline

    def terminal(self) -> bool:
        upper = self.state.upper()
        return any(token in upper for token in _TERMINAL_STATES)


@dataclass(frozen=True, slots=True)
class GapRecord:
    gap_id: str
    mission_id: str
    requirement: str
    classification: str
    criticality: str
    dependency_on: tuple[str, ...]
    closure_route: str
    executor_profile: str
    proof_gate: str
    state: str
    current_evidence: str = ""
    truth_boundary: str = ""

    def validate(self) -> "GapRecord":
        if not self.gap_id.strip() or not self.mission_id.strip():
            raise ValueError("GAP_IDENTITY_REQUIRED")
        return self

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "GapRecord":
        return cls(
            gap_id=_clean(row.get("Gap_ID")),
            mission_id=_clean(row.get("Mission_ID")),
            requirement=_clean(row.get("Requirement")),
            classification=_clean(row.get("Classification")).upper(),
            criticality=_clean(row.get("Criticality")).upper() or "P1",
            dependency_on=_split(row.get("Dependency_On")),
            current_evidence=_clean(row.get("Current_Evidence")),
            closure_route=_clean(row.get("Closure_Route")),
            executor_profile=_clean(row.get("Executor_Profile")),
            proof_gate=_clean(row.get("Proof_Gate")),
            state=_clean(row.get("State")).upper(),
            truth_boundary=_clean(row.get("Truth_Boundary")),
        ).validate()

    def closed(self) -> bool:
        return self.classification == "VERIFIED_PRESENT" or self.state in {"CLOSED", "COMPLETE_VERIFIED"}

    def owner_only(self) -> bool:
        return self.classification == "OWNER_ONLY" or "OWNER_ONLY" in self.state or "OWNER_INTERACTION" in self.state


@dataclass(frozen=True, slots=True)
class CapabilityDeficitRecord:
    capability_id: str
    capability: str
    classification: str
    reusable: bool
    affected_missions: tuple[str, ...]
    closure_strategy: str
    owner_burden: str
    priority: str
    truth_boundary: str = ""

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "CapabilityDeficitRecord":
        return cls(
            capability_id=_clean(row.get("Capability_ID")),
            capability=_clean(row.get("Capability")),
            classification=_clean(row.get("Classification")).upper(),
            reusable=_clean(row.get("Reusable")).upper() in {"YES", "TRUE", "1"},
            affected_missions=_split(row.get("Affected_Missions")),
            closure_strategy=_clean(row.get("Closure_Strategy")),
            owner_burden=_clean(row.get("Owner_Burden")),
            priority=_clean(row.get("Priority")).upper() or "P1",
            truth_boundary=_clean(row.get("Truth_Boundary")),
        )

    def open(self) -> bool:
        return self.classification not in {"VERIFIED_PRESENT", "CLOSED", "COMPLETE_VERIFIED"}


@dataclass(frozen=True, slots=True)
class MissionProjection:
    mission_id: str
    mission_class: str
    current_p_stage: str
    required_p_stage: str
    stage_debt: tuple[str, ...]
    terminal_debt: tuple[str, ...]
    open_gap_ids: tuple[str, ...]
    ready_gap_ids: tuple[str, ...]
    blocked_gap_ids: tuple[str, ...]
    owner_only_gap_ids: tuple[str, ...]
    next_action: str
    priority_score: float
    complete_at_required_stage: bool


@dataclass(frozen=True, slots=True)
class ReadyAction:
    mission_id: str
    gap_id: str
    action: str
    executor_profile: str
    proof_gate: str
    score: float


@dataclass(frozen=True, slots=True)
class SharedEnabler:
    capability_id: str
    capability: str
    classification: str
    affected_active_missions: tuple[str, ...]
    closure_strategy: str
    score: float


@dataclass(frozen=True, slots=True)
class PortfolioReceipt:
    schema: str
    version: str
    active_mission_id: str
    active_required_mission_count: int
    mission_projections: tuple[MissionProjection, ...]
    ready_wave: tuple[ReadyAction, ...]
    shared_enablers: tuple[SharedEnabler, ...]
    total_open_gap_debt: int
    total_owner_only_debt: int
    total_stage_debt: int
    total_terminal_debt: int
    complete_verified_mission_count: int
    portfolio_complete_verified: bool
    next_action: str
    receipt_sha256: str


class MasterBiblePortfolioCompiler:
    """Compile current Federation mission/gap/deficit snapshots into one execution graph."""

    def __init__(self, *, max_parallel: int = 4) -> None:
        if max_parallel < 1:
            raise ValueError("MAX_PARALLEL_MUST_BE_POSITIVE")
        self.max_parallel = max_parallel

    @staticmethod
    def _gap_ready(gap: GapRecord, by_gap: Mapping[str, GapRecord]) -> tuple[bool, str]:
        if gap.closed():
            return False, "GAP_ALREADY_CLOSED"
        if gap.owner_only():
            return False, "OWNER_ONLY"
        for dep in gap.dependency_on:
            parent = by_gap.get(dep)
            if parent is None:
                return False, f"UNKNOWN_GAP_DEPENDENCY:{dep}"
            if not parent.closed():
                return False, f"DEPENDENCY_OPEN:{dep}"
        return True, "READY"

    @staticmethod
    def _deficit_affects(deficit: CapabilityDeficitRecord, mission_id: str) -> bool:
        if any(item.upper().startswith("ALL") for item in deficit.affected_missions):
            return True
        return mission_id in deficit.affected_missions

    def compile(
        self,
        *,
        missions: Sequence[MissionRecord],
        gaps: Sequence[GapRecord] = (),
        capability_deficits: Sequence[CapabilityDeficitRecord] = (),
        active_mission_id: str = "",
    ) -> PortfolioReceipt:
        if not missions:
            raise ValueError("MISSION_SNAPSHOT_REQUIRED")
        mission_map: dict[str, MissionRecord] = {}
        for mission in missions:
            mission.validate()
            if mission.mission_id in mission_map:
                raise ValueError(f"DUPLICATE_MISSION_ID:{mission.mission_id}")
            mission_map[mission.mission_id] = mission
        gap_map: dict[str, GapRecord] = {}
        by_mission_gap: dict[str, list[GapRecord]] = {mission_id: [] for mission_id in mission_map}
        for gap in gaps:
            gap.validate()
            if gap.gap_id in gap_map:
                raise ValueError(f"DUPLICATE_GAP_ID:{gap.gap_id}")
            if gap.mission_id not in mission_map:
                raise ValueError(f"GAP_UNKNOWN_MISSION:{gap.gap_id}:{gap.mission_id}")
            gap_map[gap.gap_id] = gap
            by_mission_gap[gap.mission_id].append(gap)

        active = tuple(mission for mission in missions if not mission.terminal() and mission.resolved_class() is not MissionClass.HISTORICAL_EVIDENCE)
        if not active:
            raise ValueError("NO_ACTIVE_REQUIRED_MISSIONS")
        if active_mission_id and active_mission_id not in {mission.mission_id for mission in active}:
            raise ValueError("ACTIVE_MISSION_NOT_IN_ACTIVE_PORTFOLIO")

        open_deficits = tuple(item for item in capability_deficits if item.open())
        projections: list[MissionProjection] = []
        ready_actions: list[ReadyAction] = []

        for mission in active:
            current = mission.resolved_current_stage()
            required = mission.resolved_required_stage()
            stage_debt = () if current >= required else (f"P_STAGE:{current.name}->{required.name}",)
            terminal_debt = tuple(sorted(set(mission.required_terminal_predicates) - set(mission.satisfied_terminal_predicates)))
            mission_gaps = tuple(sorted(by_mission_gap[mission.mission_id], key=lambda item: item.gap_id))
            open_gaps = tuple(gap for gap in mission_gaps if not gap.closed())
            ready: list[str] = []
            blocked: list[str] = []
            owner: list[str] = []
            for gap in open_gaps:
                is_ready, reason = self._gap_ready(gap, gap_map)
                if is_ready:
                    ready.append(gap.gap_id)
                    score = (
                        (100.0 if mission.mission_id == active_mission_id else 0.0)
                        + _PRIORITY_WEIGHT.get(gap.criticality, 8.0)
                        + _CLASSIFICATION_WEIGHT.get(gap.classification, 10.0)
                        + _PRIORITY_WEIGHT.get(mission.priority.upper(), 8.0)
                    )
                    ready_actions.append(
                        ReadyAction(
                            mission_id=mission.mission_id,
                            gap_id=gap.gap_id,
                            action=gap.closure_route or mission.next_action or "CLOSE_GAP",
                            executor_profile=gap.executor_profile,
                            proof_gate=gap.proof_gate,
                            score=round(score, 6),
                        )
                    )
                elif reason == "OWNER_ONLY":
                    owner.append(gap.gap_id)
                else:
                    blocked.append(gap.gap_id)

            affected_deficits = sum(1 for deficit in open_deficits if self._deficit_affects(deficit, mission.mission_id))
            mission_score = (
                (100.0 if mission.mission_id == active_mission_id else 0.0)
                + _PRIORITY_WEIGHT.get(mission.priority.upper(), 8.0)
                + 6.0 * len(ready)
                + 3.0 * affected_deficits
                + (10.0 if stage_debt else 0.0)
            )
            if ready:
                first = next(gap for gap in open_gaps if gap.gap_id == sorted(ready)[0])
                next_action = first.closure_route or mission.next_action or "CLOSE_READY_GAP"
            elif mission.next_action:
                next_action = mission.next_action
            elif stage_debt:
                next_action = "ADVANCE_PRODUCTION_STAGE"
            elif terminal_debt:
                next_action = "CLOSE_TERMINAL_PREDICATES"
            else:
                next_action = "AWAIT_CHANGED_PREDICATE_OR_TERMINAL_RECONCILIATION"
            complete = not stage_debt and not open_gaps and not terminal_debt
            projections.append(
                MissionProjection(
                    mission_id=mission.mission_id,
                    mission_class=mission.resolved_class().value,
                    current_p_stage=current.name,
                    required_p_stage=required.name,
                    stage_debt=stage_debt,
                    terminal_debt=terminal_debt,
                    open_gap_ids=tuple(gap.gap_id for gap in open_gaps),
                    ready_gap_ids=tuple(sorted(ready)),
                    blocked_gap_ids=tuple(sorted(blocked)),
                    owner_only_gap_ids=tuple(sorted(owner)),
                    next_action=next_action,
                    priority_score=round(mission_score, 6),
                    complete_at_required_stage=complete,
                )
            )

        active_ids = {item.mission_id for item in active}
        enablers: list[SharedEnabler] = []
        for deficit in open_deficits:
            if not deficit.reusable:
                continue
            affected = tuple(sorted(mission_id for mission_id in active_ids if self._deficit_affects(deficit, mission_id)))
            if len(affected) < 2 and not any(item.upper().startswith("ALL") for item in deficit.affected_missions):
                continue
            score = (
                _CLASSIFICATION_WEIGHT.get(deficit.classification, 10.0)
                + _PRIORITY_WEIGHT.get(deficit.priority.upper(), 8.0)
                + 8.0 * max(1, len(affected))
                + (8.0 if "ZERO" in deficit.owner_burden.upper() or "REDUCE" in deficit.owner_burden.upper() else 0.0)
            )
            enablers.append(
                SharedEnabler(
                    capability_id=deficit.capability_id,
                    capability=deficit.capability,
                    classification=deficit.classification,
                    affected_active_missions=affected,
                    closure_strategy=deficit.closure_strategy,
                    score=round(score, 6),
                )
            )

        ranked_actions = sorted(ready_actions, key=lambda item: (-item.score, item.mission_id, item.gap_id))
        selected: list[ReadyAction] = []
        locked_executor_domains: set[str] = set()
        for action in ranked_actions:
            domain = action.executor_profile.strip() or f"GAP:{action.gap_id}"
            if domain in locked_executor_domains:
                continue
            selected.append(action)
            locked_executor_domains.add(domain)
            if len(selected) >= self.max_parallel:
                break

        projections_sorted = tuple(sorted(projections, key=lambda item: (-item.priority_score, item.mission_id)))
        enablers_sorted = tuple(sorted(enablers, key=lambda item: (-item.score, item.capability_id)))
        total_open_gap_debt = sum(len(item.open_gap_ids) for item in projections_sorted)
        total_owner_only_debt = sum(len(item.owner_only_gap_ids) for item in projections_sorted)
        total_stage_debt = sum(len(item.stage_debt) for item in projections_sorted)
        total_terminal_debt = sum(len(item.terminal_debt) for item in projections_sorted)
        complete_count = sum(1 for item in projections_sorted if item.complete_at_required_stage)
        portfolio_complete = complete_count == len(projections_sorted)
        if selected:
            next_action = selected[0].action
        elif enablers_sorted:
            next_action = enablers_sorted[0].closure_strategy or "CLOSE_SHARED_ENABLER"
        elif portfolio_complete:
            next_action = "PORTFOLIO_COMPLETE_VERIFIED"
        else:
            next_action = "WAIT_FOR_CHANGED_PREDICATE_OR_OWNER_ONLY_GATE_WHILE_PRESERVING_DEBT"

        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "active_mission_id": active_mission_id,
            "projections": [asdict(item) for item in projections_sorted],
            "ready_wave": [asdict(item) for item in selected],
            "shared_enablers": [asdict(item) for item in enablers_sorted],
            "totals": {
                "open_gap": total_open_gap_debt,
                "owner_only": total_owner_only_debt,
                "stage": total_stage_debt,
                "terminal": total_terminal_debt,
                "complete": complete_count,
            },
            "portfolio_complete_verified": portfolio_complete,
            "next_action": next_action,
        }
        return PortfolioReceipt(
            schema=SCHEMA,
            version=VERSION,
            active_mission_id=active_mission_id,
            active_required_mission_count=len(projections_sorted),
            mission_projections=projections_sorted,
            ready_wave=tuple(selected),
            shared_enablers=enablers_sorted,
            total_open_gap_debt=total_open_gap_debt,
            total_owner_only_debt=total_owner_only_debt,
            total_stage_debt=total_stage_debt,
            total_terminal_debt=total_terminal_debt,
            complete_verified_mission_count=complete_count,
            portfolio_complete_verified=portfolio_complete,
            next_action=next_action,
            receipt_sha256=_digest(material),
        )


__all__ = [
    "CapabilityDeficitRecord",
    "GapRecord",
    "MasterBiblePortfolioCompiler",
    "MissionClass",
    "MissionProjection",
    "MissionRecord",
    "PortfolioReceipt",
    "ReadyAction",
    "SCHEMA",
    "SharedEnabler",
    "VERSION",
]
