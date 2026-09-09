"""FUSE AI-Bot Multi-Path / Multi-Stream Fabric v1.

A provider-neutral composition adapter that reuses Formation Ω's Autonomic Mission
Convergence Fabric and adopts Alpha→Omega's path/stream discipline for FUSE mission
execution. It does not create credentials, provider identities, a second scheduler,
a second memory root, background execution, or external effects.

Logical AI-bot cells are planning/verification roles. They become provider-native
workers only when an independent runtime attests actual worker identity, execution and
readback. Route failure is preserved as negative knowledge and does not freeze unrelated
paths or streams.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Sequence

from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    AutonomicMissionFabric,
    FailureForecast,
    MissionGenome,
    SwarmRole,
)

SCHEMA = "FUSE-AI-BOT-MULTIPATH-MULTISTREAM-V1"
VERSION = "1.0.0"


class PathState(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    HELD = "HELD"


@dataclass(frozen=True, slots=True)
class StreamPath:
    path_id: str
    stream_id: str
    objective: str
    independent_group: str
    closure_leverage: float
    information_gain: float
    success_probability: float
    reversibility: float
    cost: float
    risk: float
    latency: float
    unlock_count: int = 0
    mutation_domain: str = ""
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    required_capabilities: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.path_id.strip():
            raise ValueError("PATH_ID_REQUIRED")
        if not self.stream_id.strip():
            raise ValueError("STREAM_ID_REQUIRED")
        if not self.objective.strip():
            raise ValueError("OBJECTIVE_REQUIRED")
        if not self.independent_group.strip():
            raise ValueError("INDEPENDENT_GROUP_REQUIRED")

    def as_action(self) -> ActionCandidate:
        self.validate()
        return ActionCandidate(
            action_id=self.path_id,
            objective=self.objective,
            closure_leverage=self.closure_leverage,
            information_gain=self.information_gain,
            success_probability=self.success_probability,
            reversibility=self.reversibility,
            cost=self.cost,
            risk=self.risk,
            latency=self.latency,
            unlock_count=self.unlock_count,
            shared_state_key=self.mutation_domain or None,
            authority_ceiling=self.authority_ceiling,
            external_effect=self.external_effect,
            required_capabilities=self.required_capabilities,
            evidence_refs=self.evidence_refs,
        )


@dataclass(frozen=True, slots=True)
class BotCell:
    bot_id: str
    role: str
    mission_id: str
    objective: str
    authority_ceiling: str
    independence_domain: str
    logical_only: bool = True
    may_self_certify: bool = False


@dataclass(frozen=True, slots=True)
class PathOutcome:
    path_id: str
    stream_id: str
    independent_group: str
    state: PathState
    evidence_refs: tuple[str, ...] = ()
    failure_fingerprint: str = ""
    retry_after_predicate: str = ""
    critical_conflict: bool = False

    def validate(self) -> None:
        if not self.path_id.strip() or not self.stream_id.strip() or not self.independent_group.strip():
            raise ValueError("OUTCOME_IDENTITY_REQUIRED")
        if self.state is PathState.VERIFIED and not self.evidence_refs:
            raise ValueError("VERIFIED_PATH_REQUIRES_EVIDENCE")
        if self.state is PathState.FAILED and not self.failure_fingerprint.strip():
            raise ValueError("FAILED_PATH_REQUIRES_FINGERPRINT")


@dataclass(frozen=True, slots=True)
class StreamAssessment:
    stream_id: str
    verified_paths: tuple[str, ...]
    independent_groups: tuple[str, ...]
    complete: bool
    reason: str


@dataclass(frozen=True, slots=True)
class MultiStreamPlan:
    schema: str
    version: str
    mission_id: str
    objective: str
    required_streams: tuple[str, ...]
    path_registry: tuple[tuple[str, str, str], ...]
    ranked_paths_by_stream: tuple[tuple[str, tuple[str, ...]], ...]
    selected_wave: tuple[str, ...]
    held_paths: tuple[tuple[str, str], ...]
    declared_alternates: tuple[tuple[str, str, str], ...]
    logical_bot_cells: tuple[BotCell, ...]
    preempted_failures: tuple[str, ...]
    corroboration_required_per_stream: int
    provider_native_worker_count: int
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class OmegaWitness:
    schema: str
    mission_id: str
    state: str
    stream_assessments: tuple[StreamAssessment, ...]
    negative_knowledge: tuple[str, ...]
    retryable_failures: tuple[str, ...]
    critical_conflicts: tuple[str, ...]
    completion_allowed: bool
    witness_sha256: str


_ROLE_TO_BOT = {
    SwarmRole.BUILDER: "BUILD_BOT",
    SwarmRole.FALSIFIER: "FALSIFIER_BOT",
    SwarmRole.EVIDENCE: "EVIDENCE_BOT",
    SwarmRole.ROUTE: "ROUTE_BOT",
    SwarmRole.SENTINEL: "SENTINEL_BOT",
    SwarmRole.RECOVERY: "RECOVERY_BOT",
    SwarmRole.WITNESS: "WITNESS_BOT",
}


def _digest(payload: object) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


class FUSEAIBotMultiStreamFabric:
    """Compose Formation Ω swarm/scheduling with Alpha→Omega path/stream discipline."""

    def __init__(
        self,
        *,
        authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
        max_parallel: int = 4,
        corroboration_required_per_stream: int = 1,
    ) -> None:
        if max_parallel < 1:
            raise ValueError("MAX_PARALLEL_MUST_BE_POSITIVE")
        if corroboration_required_per_stream < 1:
            raise ValueError("CORROBORATION_MUST_BE_POSITIVE")
        self.authority_ceiling = authority_ceiling
        self.max_parallel = max_parallel
        self.corroboration_required_per_stream = corroboration_required_per_stream
        self.formation = AutonomicMissionFabric(authority_ceiling=authority_ceiling)

    def plan(
        self,
        *,
        mission_id: str,
        objective: str,
        required_streams: Iterable[str],
        paths: Sequence[StreamPath],
        forecasts: Iterable[FailureForecast] = (),
        genome: MissionGenome | None = None,
    ) -> MultiStreamPlan:
        mission_id = mission_id.strip()
        objective = " ".join(objective.split())
        streams = tuple(sorted({str(item).strip() for item in required_streams if str(item).strip()}))
        if not mission_id:
            raise ValueError("MISSION_ID_REQUIRED")
        if not objective:
            raise ValueError("MISSION_OBJECTIVE_REQUIRED")
        if not streams:
            raise ValueError("REQUIRED_STREAMS_REQUIRED")
        if not paths:
            raise ValueError("MULTIPATH_REQUIRES_CANDIDATES")

        by_id: dict[str, StreamPath] = {}
        by_stream: dict[str, list[StreamPath]] = {stream: [] for stream in streams}
        for path in paths:
            path.validate()
            if path.path_id in by_id:
                raise ValueError(f"DUPLICATE_PATH_ID:{path.path_id}")
            if path.stream_id not in by_stream:
                raise ValueError(f"UNDECLARED_STREAM:{path.stream_id}")
            by_id[path.path_id] = path
            by_stream[path.stream_id].append(path)
        missing = tuple(stream for stream in streams if not by_stream[stream])
        if missing:
            raise ValueError("STREAM_WITHOUT_PATH:" + ",".join(missing))

        actions = tuple(path.as_action() for path in paths)
        formation_plan = self.formation.plan(
            mission_id=mission_id,
            objective=objective,
            actions=actions,
            forecasts=forecasts,
            genome=genome,
            max_parallel=self.max_parallel,
        )
        ranked = self.formation.scheduler.rank(actions)
        hold_by_path = {item.action.action_id: item.hold_reason for item in ranked if item.hold_reason}
        score_order = {item.action.action_id: index for index, item in enumerate(ranked)}
        ranked_by_stream = tuple(
            (
                stream,
                tuple(
                    path.path_id
                    for path in sorted(by_stream[stream], key=lambda item: (score_order[item.path_id], item.path_id))
                ),
            )
            for stream in streams
        )

        bots = tuple(
            BotCell(
                bot_id=f"{mission_id}:{_ROLE_TO_BOT[cell.role]}",
                role=cell.role.value,
                mission_id=mission_id,
                objective=objective,
                authority_ceiling=cell.authority_ceiling.value,
                independence_domain=cell.independence_domain,
                logical_only=True,
                may_self_certify=False,
            )
            for cell in formation_plan.swarm
        )
        selected = tuple(item.action.action_id for item in formation_plan.selected_wave)
        registry = tuple(sorted((path.path_id, path.stream_id, path.independent_group) for path in paths))
        held = tuple(sorted((path_id, reason) for path_id, reason in hold_by_path.items() if reason))
        selected_set = set(selected)
        held_set = {path_id for path_id, _ in held}
        declared_alternates: list[tuple[str, str, str]] = []
        for stream, ranked_path_ids in ranked_by_stream:
            selected_primary = next(
                (path_id for path_id in ranked_path_ids if path_id in selected_set),
                None,
            )
            if selected_primary is None:
                continue
            declared_alternates.extend(
                (path_id, stream, selected_primary)
                for path_id in ranked_path_ids
                if path_id not in selected_set and path_id not in held_set
            )
        alternates = tuple(sorted(declared_alternates))
        payload = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission_id,
            "objective": objective,
            "required_streams": streams,
            "path_registry": registry,
            "ranked_paths_by_stream": ranked_by_stream,
            "selected_wave": selected,
            "held_paths": held,
            "declared_alternates": alternates,
            "bots": [(bot.bot_id, bot.role, bot.authority_ceiling) for bot in bots],
            "preemptions": [item.fingerprint for item in formation_plan.preemptions],
            "corroboration_required_per_stream": self.corroboration_required_per_stream,
            "provider_native_worker_count": 0,
        }
        return MultiStreamPlan(
            schema=SCHEMA,
            version=VERSION,
            mission_id=mission_id,
            objective=objective,
            required_streams=streams,
            path_registry=registry,
            ranked_paths_by_stream=ranked_by_stream,
            selected_wave=selected,
            held_paths=held,
            declared_alternates=alternates,
            logical_bot_cells=bots,
            preempted_failures=tuple(item.fingerprint for item in formation_plan.preemptions),
            corroboration_required_per_stream=self.corroboration_required_per_stream,
            provider_native_worker_count=0,
            plan_sha256=_digest(payload),
        )

    def reconcile(self, plan: MultiStreamPlan, outcomes: Sequence[PathOutcome]) -> OmegaWitness:
        registry = {path_id: (stream_id, group) for path_id, stream_id, group in plan.path_registry}
        selected = set(plan.selected_wave)
        held = dict(plan.held_paths)
        alternates = {
            path_id: (stream_id, selected_primary)
            for path_id, stream_id, selected_primary in plan.declared_alternates
        }
        seen: set[str] = set()
        by_stream: dict[str, list[PathOutcome]] = {stream: [] for stream in plan.required_streams}
        negative: list[str] = []
        retryable: list[str] = []
        conflicts: list[str] = []

        indexed_outcomes: dict[str, PathOutcome] = {}
        for outcome in outcomes:
            outcome.validate()
            if outcome.path_id in seen:
                raise ValueError(f"DUPLICATE_OUTCOME:{outcome.path_id}")
            seen.add(outcome.path_id)
            expected = registry.get(outcome.path_id)
            if expected is None:
                raise ValueError(f"UNKNOWN_PATH:{outcome.path_id}")
            if expected != (outcome.stream_id, outcome.independent_group):
                raise ValueError(f"PATH_IDENTITY_CONFLICT:{outcome.path_id}")
            indexed_outcomes[outcome.path_id] = outcome

        for outcome in outcomes:
            if outcome.path_id in held:
                raise ValueError(
                    f"OUTCOME_FROM_HELD_PATH:{outcome.path_id}:{held[outcome.path_id]}"
                )
            if outcome.path_id not in selected:
                alternate = alternates.get(outcome.path_id)
                if alternate is None:
                    raise ValueError(f"OUTCOME_FROM_UNSELECTED_PATH:{outcome.path_id}")
                stream_id, selected_primary = alternate
                primary_outcome = indexed_outcomes.get(selected_primary)
                if (
                    outcome.stream_id != stream_id
                    or primary_outcome is None
                    or primary_outcome.state is not PathState.FAILED
                ):
                    raise ValueError(
                        "ALTERNATE_REQUIRES_SELECTED_PATH_FAILURE:"
                        f"{outcome.path_id}:{selected_primary}"
                    )
            by_stream[outcome.stream_id].append(outcome)
            if outcome.critical_conflict:
                conflicts.append(outcome.path_id)
            if outcome.state is PathState.FAILED:
                negative.append(
                    f"{outcome.path_id}:{outcome.failure_fingerprint}:retry_after={outcome.retry_after_predicate or 'PREDICATE_CHANGE_REQUIRED'}"
                )
                if outcome.retry_after_predicate:
                    retryable.append(f"{outcome.path_id}:{outcome.retry_after_predicate}")

        assessments: list[StreamAssessment] = []
        for stream in plan.required_streams:
            verified = tuple(sorted(item.path_id for item in by_stream[stream] if item.state is PathState.VERIFIED))
            groups = tuple(sorted({item.independent_group for item in by_stream[stream] if item.state is PathState.VERIFIED}))
            complete = len(groups) >= plan.corroboration_required_per_stream
            if complete:
                reason = "STREAM_VERIFIED"
            elif by_stream[stream]:
                reason = "CONTINUE_ALTERNATE_PATHS"
            else:
                reason = "STREAM_UNPROVEN"
            assessments.append(StreamAssessment(stream, verified, groups, complete, reason))

        if conflicts:
            state = "REJECT_CONFLICTED"
            completion = False
        elif all(item.complete for item in assessments):
            state = "OMEGA_MULTIPATH_MULTISTREAM_VERIFIED"
            completion = True
        else:
            state = "CONTINUE_MULTIPATH_MULTISTREAM"
            completion = False

        payload = {
            "schema": SCHEMA,
            "mission_id": plan.mission_id,
            "plan_sha256": plan.plan_sha256,
            "state": state,
            "streams": [
                {
                    "stream_id": item.stream_id,
                    "verified_paths": item.verified_paths,
                    "independent_groups": item.independent_groups,
                    "complete": item.complete,
                    "reason": item.reason,
                }
                for item in assessments
            ],
            "negative_knowledge": sorted(set(negative)),
            "retryable_failures": sorted(set(retryable)),
            "critical_conflicts": sorted(set(conflicts)),
            "completion_allowed": completion,
        }
        return OmegaWitness(
            schema=SCHEMA,
            mission_id=plan.mission_id,
            state=state,
            stream_assessments=tuple(assessments),
            negative_knowledge=tuple(sorted(set(negative))),
            retryable_failures=tuple(sorted(set(retryable))),
            critical_conflicts=tuple(sorted(set(conflicts))),
            completion_allowed=completion,
            witness_sha256=_digest(payload),
        )


__all__ = [
    "BotCell",
    "FUSEAIBotMultiStreamFabric",
    "MultiStreamPlan",
    "OmegaWitness",
    "PathOutcome",
    "PathState",
    "SCHEMA",
    "StreamAssessment",
    "StreamPath",
    "VERSION",
]
