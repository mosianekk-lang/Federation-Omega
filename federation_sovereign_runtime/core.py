from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


RUNTIME_ID = "FEDERATION-SOVEREIGN-INTELLIGENCE-RUNTIME-OMEGA1"
RUNTIME_VERSION = "1.0.0"


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


_REASONING_ORDER = (
    ReasoningEffort.LOW,
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
    ReasoningEffort.XHIGH,
    ReasoningEffort.MAX,
)


class SteeringKind(str, Enum):
    SIDE_QUESTION = "SIDE_QUESTION"
    ADD_CONSTRAINT = "ADD_CONSTRAINT"
    CORRECTION = "CORRECTION"
    PRIORITY_UPDATE = "PRIORITY_UPDATE"
    OBJECTIVE_CHANGE = "OBJECTIVE_CHANGE"
    CANCEL = "CANCEL"


class WorkState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    HOLD_READBACK = "HOLD_READBACK"


class ToolEffect(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    REVERSIBLE_INTERNAL = "REVERSIBLE_INTERNAL"
    REVERSIBLE_EXTERNAL = "REVERSIBLE_EXTERNAL"
    HIGH_CONSEQUENCE = "HIGH_CONSEQUENCE"


@dataclass(frozen=True)
class MissionFrame:
    mission_id: str
    owner: str
    root_objective: str
    current_objective: str
    success_conditions: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    completed_work_refs: tuple[str, ...] = ()
    invalidated_work_refs: tuple[str, ...] = ()
    authority_ceiling: str = "A1_INTERNAL"
    privacy_envelope: str = "PRIVATE"
    version: int = 1

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.mission_id.strip():
            errors.append("MISSION_ID_REQUIRED")
        if not self.owner.strip():
            errors.append("OWNER_REQUIRED")
        if not self.root_objective.strip():
            errors.append("ROOT_OBJECTIVE_REQUIRED")
        if not self.current_objective.strip():
            errors.append("CURRENT_OBJECTIVE_REQUIRED")
        if not self.success_conditions:
            errors.append("SUCCESS_CONDITION_REQUIRED")
        return tuple(errors)

    @property
    def fingerprint(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class SteeringEvent:
    event_id: str
    kind: SteeringKind
    content: str
    owner_authorized: bool = False
    invalidate_work_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SteeringDecision:
    accepted: bool
    human_required: bool
    mode: str
    mission: MissionFrame
    reasons: tuple[str, ...] = ()


class MissionSteeringController:
    """Apply mid-mission steering without silently replacing human intent."""

    def apply(self, mission: MissionFrame, event: SteeringEvent) -> SteeringDecision:
        errors = mission.validate()
        if errors:
            return SteeringDecision(False, True, "BLOCK_INVALID_MISSION", mission, errors)
        if not event.event_id.strip() or not event.content.strip():
            return SteeringDecision(
                False,
                True,
                "BLOCK_INVALID_STEERING_EVENT",
                mission,
                ("STEERING_EVENT_ID_AND_CONTENT_REQUIRED",),
            )

        if event.kind is SteeringKind.OBJECTIVE_CHANGE and not event.owner_authorized:
            return SteeringDecision(
                False,
                True,
                "HOLD_OBJECTIVE_CHANGE_FOR_OWNER",
                mission,
                ("ROOT_INTENT_CANNOT_BE_SILENTLY_REPLACED",),
            )

        if event.kind is SteeringKind.CANCEL and not event.owner_authorized:
            return SteeringDecision(
                False,
                True,
                "HOLD_CANCEL_FOR_OWNER",
                mission,
                ("CANCEL_REQUIRES_OWNER_AUTHORITY",),
            )

        constraints = list(mission.constraints)
        current_objective = mission.current_objective
        invalidated = list(mission.invalidated_work_refs)

        if event.kind is SteeringKind.OBJECTIVE_CHANGE:
            current_objective = event.content.strip()
        elif event.kind in {SteeringKind.ADD_CONSTRAINT, SteeringKind.CORRECTION}:
            constraints.append(event.content.strip())
        elif event.kind is SteeringKind.PRIORITY_UPDATE:
            constraints.append("PRIORITY: " + event.content.strip())
        elif event.kind is SteeringKind.CANCEL:
            constraints.append("MISSION_CANCELLED_BY_OWNER")
        # SIDE_QUESTION deliberately leaves objective/constraints unchanged.

        for ref in event.invalidate_work_refs:
            if ref and ref not in invalidated:
                invalidated.append(ref)

        updated = replace(
            mission,
            current_objective=current_objective,
            constraints=tuple(dict.fromkeys(constraints)),
            invalidated_work_refs=tuple(dict.fromkeys(invalidated)),
            version=mission.version + 1,
        )
        return SteeringDecision(
            True,
            False,
            "STEERING_APPLIED_WITH_INTENT_PRESERVED",
            updated,
            ("ROOT_OBJECTIVE_PRESERVED", "COMPLETED_WORK_PRESERVED_UNLESS_EXPLICITLY_INVALIDATED"),
        )


@dataclass(frozen=True)
class ReasoningConfiguration:
    effort: ReasoningEffort
    configuration_version: int = 1
    reason: str = ""


class AdaptiveReasoningController:
    """Provider-neutral reasoning-pressure controller.

    It changes a logical reasoning configuration, not a provider model by itself.
    """

    def choose(
        self,
        *,
        current: ReasoningConfiguration | None = None,
        complexity: float = 0.5,
        consequence: float = 0.5,
        uncertainty: float = 0.5,
        adversarial_complexity: float = 0.5,
        repeated_failures: int = 0,
        high_stakes: bool = False,
    ) -> ReasoningConfiguration:
        def unit(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        pressure = (
            0.30 * unit(complexity)
            + 0.28 * unit(consequence)
            + 0.22 * unit(uncertainty)
            + 0.20 * unit(adversarial_complexity)
        )
        if high_stakes:
            pressure = max(pressure, 0.66)
        if repeated_failures >= 2:
            pressure = max(pressure, 0.82)
        if repeated_failures >= 4:
            pressure = 1.0

        if pressure < 0.28:
            effort = ReasoningEffort.LOW
        elif pressure < 0.48:
            effort = ReasoningEffort.MEDIUM
        elif pressure < 0.68:
            effort = ReasoningEffort.HIGH
        elif pressure < 0.88:
            effort = ReasoningEffort.XHIGH
        else:
            effort = ReasoningEffort.MAX

        if high_stakes and _REASONING_ORDER.index(effort) < _REASONING_ORDER.index(ReasoningEffort.HIGH):
            effort = ReasoningEffort.HIGH

        version = 1 if current is None else current.configuration_version + 1
        return ReasoningConfiguration(
            effort=effort,
            configuration_version=version,
            reason=f"reasoning_pressure={pressure:.3f};high_stakes={high_stakes};repeated_failures={repeated_failures}",
        )


@dataclass(frozen=True)
class ProcessorProfile:
    processor_id: str
    provider: str
    model: str
    capabilities: frozenset[str]
    available: bool
    authorized: bool
    max_context_tokens: int | None = None
    measured_quality: float | None = None
    measured_latency_score: float | None = None
    measured_cost_score: float | None = None
    measured_privacy_score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessorRequirement:
    required_capabilities: frozenset[str]
    minimum_quality: float | None = None
    required_context_tokens: int | None = None
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "quality": 0.55,
            "latency": 0.15,
            "cost": 0.15,
            "privacy": 0.15,
        }
    )


@dataclass(frozen=True)
class ProcessorDecision:
    selected: ProcessorProfile | None
    state: str
    score: float | None
    reasons: tuple[str, ...]


class SovereignProcessorMarket:
    """Treat model providers as replaceable processors, never mission authorities."""

    @staticmethod
    def _score(profile: ProcessorProfile, weights: Mapping[str, float]) -> float | None:
        values = {
            "quality": profile.measured_quality,
            "latency": profile.measured_latency_score,
            "cost": profile.measured_cost_score,
            "privacy": profile.measured_privacy_score,
        }
        if any(values[key] is None for key in weights):
            return None
        return sum(float(weights[key]) * float(values[key]) for key in weights)

    def select(
        self,
        requirement: ProcessorRequirement,
        profiles: Iterable[ProcessorProfile],
    ) -> ProcessorDecision:
        eligible: list[tuple[float, ProcessorProfile]] = []
        held: list[str] = []
        for profile in profiles:
            if not profile.available:
                held.append(f"{profile.processor_id}:UNAVAILABLE")
                continue
            if not profile.authorized:
                held.append(f"{profile.processor_id}:UNAUTHORIZED")
                continue
            if not requirement.required_capabilities.issubset(profile.capabilities):
                held.append(f"{profile.processor_id}:CAPABILITY_GAP")
                continue
            if (
                requirement.required_context_tokens is not None
                and (
                    profile.max_context_tokens is None
                    or profile.max_context_tokens < requirement.required_context_tokens
                )
            ):
                held.append(f"{profile.processor_id}:CONTEXT_WINDOW_TOO_SMALL")
                continue
            if (
                requirement.minimum_quality is not None
                and (
                    profile.measured_quality is None
                    or profile.measured_quality < requirement.minimum_quality
                )
            ):
                held.append(f"{profile.processor_id}:QUALITY_UNPROVEN_OR_BELOW_FLOOR")
                continue
            score = self._score(profile, requirement.weights)
            if score is None:
                held.append(f"{profile.processor_id}:MEASUREMENT_INCOMPLETE")
                continue
            eligible.append((score, profile))

        if not eligible:
            return ProcessorDecision(
                None,
                "HOLD_NO_PROVEN_ELIGIBLE_PROCESSOR",
                None,
                tuple(held) or ("NO_PROCESSORS_SUPPLIED",),
            )
        eligible.sort(key=lambda item: (item[0], item[1].processor_id), reverse=True)
        score, selected = eligible[0]
        return ProcessorDecision(
            selected,
            "PROCESSOR_SELECTED_FROM_MEASURED_ELIGIBLE_SET",
            round(score, 6),
            ("PROVIDER_IS_PROCESSOR_NOT_AUTHORITY",),
        )


@dataclass(frozen=True)
class ToolTicket:
    call_id: str
    tool_name: str
    effect: ToolEffect
    state: WorkState = WorkState.READY
    authorization_ref: str = ""
    readback_required: bool = False
    result_ref: str = ""
    error: str = ""


class NonblockingToolBroker:
    """Track independent tool work without turning one pending tool into a global stall."""

    def __init__(self) -> None:
        self._tickets: dict[str, ToolTicket] = {}

    def submit(self, ticket: ToolTicket) -> ToolTicket:
        if not ticket.call_id.strip() or not ticket.tool_name.strip():
            raise ValueError("TOOL_CALL_ID_AND_NAME_REQUIRED")
        if ticket.call_id in self._tickets:
            existing = self._tickets[ticket.call_id]
            if existing.tool_name != ticket.tool_name or existing.effect != ticket.effect:
                raise ValueError("TOOL_CALL_IDEMPOTENCY_CONFLICT")
            return existing
        if ticket.effect in {ToolEffect.REVERSIBLE_EXTERNAL, ToolEffect.HIGH_CONSEQUENCE}:
            if not ticket.authorization_ref.strip():
                raise PermissionError("EXTERNAL_TOOL_AUTHORIZATION_REF_REQUIRED")
            if not ticket.readback_required:
                raise PermissionError("EXTERNAL_TOOL_READBACK_REQUIRED")
        running = replace(ticket, state=WorkState.RUNNING)
        self._tickets[ticket.call_id] = running
        return running

    def complete(self, call_id: str, *, result_ref: str) -> ToolTicket:
        ticket = self._tickets[call_id]
        if not result_ref.strip():
            raise ValueError("TOOL_RESULT_REF_REQUIRED")
        completed = replace(ticket, state=WorkState.COMPLETE, result_ref=result_ref)
        self._tickets[call_id] = completed
        return completed

    def fail(self, call_id: str, *, error: str, effect_uncertain: bool = False) -> ToolTicket:
        ticket = self._tickets[call_id]
        next_state = (
            WorkState.HOLD_READBACK
            if effect_uncertain and ticket.effect in {ToolEffect.REVERSIBLE_EXTERNAL, ToolEffect.HIGH_CONSEQUENCE}
            else WorkState.FAILED
        )
        failed = replace(ticket, state=next_state, error=error)
        self._tickets[call_id] = failed
        return failed

    def pending(self) -> tuple[ToolTicket, ...]:
        return tuple(
            ticket
            for ticket in self._tickets.values()
            if ticket.state in {WorkState.RUNNING, WorkState.WAITING, WorkState.HOLD_READBACK}
        )

    def independent_work_may_continue(self, dependency_call_ids: Sequence[str] = ()) -> bool:
        dependencies = set(dependency_call_ids)
        return not any(
            ticket.call_id in dependencies
            and ticket.state in {WorkState.RUNNING, WorkState.WAITING, WorkState.HOLD_READBACK}
            for ticket in self._tickets.values()
        )


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    content: str
    token_estimate: int
    relevance: float
    freshness: float
    proof_bearing: bool = False
    pinned: bool = False
    source_ref: str = ""


@dataclass(frozen=True)
class ContextCapsule:
    selected: tuple[ContextItem, ...]
    omitted_ids: tuple[str, ...]
    total_tokens: int
    budget_tokens: int
    overflow: bool
    capsule_sha256: str


class ContextVirtualizer:
    """Build bounded context capsules while never silently dropping pinned proof."""

    @staticmethod
    def _priority(item: ContextItem) -> tuple[int, int, float, float, str]:
        return (
            1 if item.pinned else 0,
            1 if item.proof_bearing else 0,
            max(0.0, min(1.0, item.relevance)),
            max(0.0, min(1.0, item.freshness)),
            item.item_id,
        )

    def compact(self, items: Iterable[ContextItem], *, budget_tokens: int) -> ContextCapsule:
        if budget_tokens <= 0:
            raise ValueError("CONTEXT_BUDGET_MUST_BE_POSITIVE")
        material = tuple(items)
        if any(item.token_estimate < 0 for item in material):
            raise ValueError("CONTEXT_TOKEN_ESTIMATE_NEGATIVE")
        selected: list[ContextItem] = []
        omitted: list[str] = []
        used = 0

        mandatory = [item for item in material if item.pinned or item.proof_bearing]
        optional = [item for item in material if item not in mandatory]
        mandatory.sort(key=self._priority, reverse=True)
        optional.sort(key=self._priority, reverse=True)

        for item in mandatory:
            selected.append(item)
            used += item.token_estimate

        overflow = used > budget_tokens
        if not overflow:
            for item in optional:
                if used + item.token_estimate <= budget_tokens:
                    selected.append(item)
                    used += item.token_estimate
                else:
                    omitted.append(item.item_id)
        else:
            omitted.extend(item.item_id for item in optional)

        capsule_material = {
            "selected": [item.item_id for item in selected],
            "omitted": omitted,
            "total_tokens": used,
            "budget_tokens": budget_tokens,
            "overflow": overflow,
        }
        return ContextCapsule(
            selected=tuple(selected),
            omitted_ids=tuple(omitted),
            total_tokens=used,
            budget_tokens=budget_tokens,
            overflow=overflow,
            capsule_sha256=stable_hash(capsule_material),
        )


@dataclass(frozen=True)
class AlignmentFinding:
    code: str
    detail: str


class AlignmentSentinel:
    """Detect control-plane drift without pretending to infer hidden model intent."""

    def inspect(
        self,
        *,
        mission: MissionFrame,
        proposed_objective: str,
        required_authority: str,
        allowed_authority: str,
        claimed_scope: str = "",
        proven_scope: str = "",
    ) -> tuple[AlignmentFinding, ...]:
        findings: list[AlignmentFinding] = []
        if proposed_objective.strip() != mission.current_objective.strip():
            findings.append(AlignmentFinding("OBJECTIVE_DRIFT", "Proposed objective differs from current Human Mission Contract objective."))
        if required_authority != allowed_authority:
            findings.append(AlignmentFinding("AUTHORITY_SCOPE_CHANGE", f"required={required_authority};allowed={allowed_authority}"))
        if claimed_scope and proven_scope and claimed_scope != proven_scope:
            findings.append(AlignmentFinding("CLAIM_SCOPE_EXCEEDS_OR_DIFFERS_FROM_PROOF", f"claimed={claimed_scope};proven={proven_scope}"))
        return tuple(findings)


class SovereignRuntimeKernel:
    """Federation-owned composition spine around replaceable intelligence processors."""

    def __init__(self) -> None:
        self.steering = MissionSteeringController()
        self.reasoning = AdaptiveReasoningController()
        self.processors = SovereignProcessorMarket()
        self.tools = NonblockingToolBroker()
        self.context = ContextVirtualizer()
        self.alignment = AlignmentSentinel()

    def bootstrap(self) -> dict[str, Any]:
        return {
            "runtime_id": RUNTIME_ID,
            "version": RUNTIME_VERSION,
            "architecture": "FEDERATION_OWNED_PROVIDER_NEUTRAL_INTELLIGENCE_RUNTIME_SPINE",
            "provider_role": "REPLACEABLE_COGNITIVE_PROCESSOR",
            "mission_authority": "HUMAN_FIRST_OMEGA",
            "strategic_perception": "FOREST_FIRST_OMEGA",
            "foresight": "HORIZON_OMEGA",
            "reasoning_governance": "SLOS_AND_ADAPTIVE_INTELLIGENCE_ROUTER",
            "effect_authority": "SOVARA",
            "proof_authority": "REALITYGUARD_TRUTHGRID_JFRIE_PROOFGRAPH",
            "truth_boundary": {
                "source_runtime_kernel_present": True,
                "provider_model_weights_copied": False,
                "provider_private_reasoning_copied": False,
                "native_chatgpt_modified": False,
                "astra_provider_execution_proved": False,
                "universal_runtime_enforcement_proved": False,
            },
        }


__all__ = [
    "AdaptiveReasoningController",
    "AlignmentFinding",
    "AlignmentSentinel",
    "ContextCapsule",
    "ContextItem",
    "ContextVirtualizer",
    "MissionFrame",
    "MissionSteeringController",
    "NonblockingToolBroker",
    "ProcessorDecision",
    "ProcessorProfile",
    "ProcessorRequirement",
    "ReasoningConfiguration",
    "ReasoningEffort",
    "RUNTIME_ID",
    "RUNTIME_VERSION",
    "SovereignProcessorMarket",
    "SovereignRuntimeKernel",
    "SteeringDecision",
    "SteeringEvent",
    "SteeringKind",
    "ToolEffect",
    "ToolTicket",
    "WorkState",
    "stable_hash",
]
