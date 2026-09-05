"""ChatGov Ω3.6 frontier runtime controls.

This module composes missing industry-leading runtime genes into the existing
ChatGov/Bubbles control plane without creating a new sovereign authority plane.
It is deliberately effect-neutral: it can admit, suppress, isolate, cache,
checkpoint and replay control decisions, but external effects remain governed by
Human-First/SOVARA and provider-native readback.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import time
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from .state import DurableState


def _stable(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_stable(value)).hexdigest()


class HookEvent(str, Enum):
    PRE_TOOL_USE = "PRE_TOOL_USE"
    POST_TOOL_USE = "POST_TOOL_USE"
    POST_TOOL_FAILURE = "POST_TOOL_FAILURE"
    PRE_COMPACT = "PRE_COMPACT"
    POST_COMPACT = "POST_COMPACT"
    STOP = "STOP"
    SUBAGENT_START = "SUBAGENT_START"
    SUBAGENT_STOP = "SUBAGENT_STOP"
    TASK_CREATED = "TASK_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"


@dataclass(frozen=True, slots=True)
class HookContext:
    event: HookEvent
    mission_id: str
    action: str = ""
    connector: str = ""
    target: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("HOOK_MISSION_ID_REQUIRED")
        if self.event == HookEvent.PRE_TOOL_USE and not self.action.strip():
            raise ValueError("HOOK_TOOL_ACTION_REQUIRED")


@dataclass(frozen=True, slots=True)
class HookOutcome:
    allow: bool = True
    payload: Mapping[str, Any] | None = None
    inject_context: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


HookHandler = Callable[[HookContext], HookOutcome | None]
HookMatcher = Callable[[HookContext], bool]


@dataclass(frozen=True, slots=True)
class HookRegistration:
    name: str
    event: HookEvent
    priority: int
    handler: HookHandler
    fail_closed: bool = True
    matcher: HookMatcher | None = None


@dataclass(frozen=True, slots=True)
class HookDispatchReceipt:
    allowed: bool
    event: HookEvent
    mission_id: str
    executed_hooks: tuple[str, ...]
    transformed_payload: Mapping[str, Any]
    injected_context: tuple[str, ...]
    reasons: tuple[str, ...]
    receipt_sha256: str


class LifecycleHookBus:
    """Deterministic lifecycle hook bus with fail-closed pre-action control.

    Hooks execute outside provider/tool payloads. A hook may block a pre-action,
    transform only the in-memory action payload, or inject bounded context. The
    bus never performs the tool action itself and never grants provider authority.
    """

    def __init__(self) -> None:
        self._hooks: list[HookRegistration] = []

    def register(
        self,
        *,
        name: str,
        event: HookEvent,
        handler: HookHandler,
        priority: int = 100,
        fail_closed: bool = True,
        matcher: HookMatcher | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("HOOK_NAME_REQUIRED")
        if any(h.name == name and h.event == event for h in self._hooks):
            raise ValueError("DUPLICATE_HOOK_REGISTRATION")
        self._hooks.append(HookRegistration(name, event, priority, handler, fail_closed, matcher))

    def dispatch(self, context: HookContext) -> HookDispatchReceipt:
        context.validate()
        payload: MutableMapping[str, Any] = dict(context.payload)
        injected: list[str] = []
        reasons: list[str] = []
        executed: list[str] = []
        allowed = True
        candidates = sorted(
            (h for h in self._hooks if h.event == context.event),
            key=lambda h: (h.priority, h.name),
        )
        for hook in candidates:
            current = HookContext(
                event=context.event,
                mission_id=context.mission_id,
                action=context.action,
                connector=context.connector,
                target=context.target,
                payload=dict(payload),
                metadata=context.metadata,
            )
            if hook.matcher is not None and not hook.matcher(current):
                continue
            executed.append(hook.name)
            try:
                outcome = hook.handler(current) or HookOutcome()
            except Exception as exc:  # hook failure must be deterministic and bounded
                reasons.append(f"HOOK_ERROR:{hook.name}:{type(exc).__name__}")
                if hook.fail_closed:
                    allowed = False
                    reasons.append(f"HOOK_FAIL_CLOSED:{hook.name}")
                    break
                continue
            if outcome.payload is not None:
                payload = dict(outcome.payload)
            if outcome.inject_context:
                injected.extend(str(item) for item in outcome.inject_context)
            reasons.extend(str(item) for item in outcome.reasons)
            if not outcome.allow:
                allowed = False
                reasons.append(f"HOOK_BLOCK:{hook.name}")
                break
        receipt_body = {
            "allowed": allowed,
            "event": context.event.value,
            "mission_id": context.mission_id,
            "executed_hooks": executed,
            "transformed_payload": payload,
            "injected_context": injected,
            "reasons": reasons,
        }
        return HookDispatchReceipt(
            allowed=allowed,
            event=context.event,
            mission_id=context.mission_id,
            executed_hooks=tuple(executed),
            transformed_payload=dict(payload),
            injected_context=tuple(injected),
            reasons=tuple(reasons),
            receipt_sha256=_digest(receipt_body),
        )


class OwnerSignalKind(str, Enum):
    PROGRESS = "PROGRESS"
    DIAGNOSTIC = "DIAGNOSTIC"
    VERIFIED_MILESTONE = "VERIFIED_MILESTONE"
    MATERIAL_RISK = "MATERIAL_RISK"
    OWNER_DECISION = "OWNER_DECISION"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class OwnerSignal:
    kind: OwnerSignalKind
    summary: str
    verified: bool = False
    recoverable: bool = False
    material: bool = False
    unresolved: bool = False
    owner_decision_required: bool = False
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OwnerAttentionDecision:
    owner_visible: bool
    report_mode: str
    headline: str
    reasons: tuple[str, ...]


class OwnerAttentionGovernor:
    """Solve-before-report owner-attention firewall.

    Raw retry noise, routine progress and recoverable diagnostics stay internal.
    Verified outcomes, material unresolved risk and genuine owner decisions are
    surfaced. This is an attention policy only; it cannot hide failed proof or
    material risk.
    """

    def decide(self, signal: OwnerSignal) -> OwnerAttentionDecision:
        if not signal.summary.strip():
            raise ValueError("OWNER_SIGNAL_SUMMARY_REQUIRED")
        if signal.owner_decision_required or signal.kind == OwnerSignalKind.OWNER_DECISION:
            return OwnerAttentionDecision(True, "PRECISE_OWNER_DECISION", signal.summary, ("OWNER_RESERVED_DECISION",))
        if signal.kind == OwnerSignalKind.MATERIAL_RISK or (signal.material and signal.unresolved):
            return OwnerAttentionDecision(True, "MATERIAL_RESIDUAL_RISK", signal.summary, ("MATERIAL_RISK_MUST_SURFACE",))
        if signal.kind == OwnerSignalKind.TERMINAL:
            mode = "VERIFIED_OUTCOME" if signal.verified else "BOUNDED_TERMINAL_STATE"
            return OwnerAttentionDecision(True, mode, signal.summary, ("TERMINAL_STATE",))
        if signal.kind == OwnerSignalKind.VERIFIED_MILESTONE and signal.verified:
            return OwnerAttentionDecision(True, "VERIFIED_MILESTONE", signal.summary, ("PROOF_BEARING_MILESTONE",))
        if signal.kind == OwnerSignalKind.DIAGNOSTIC and not signal.recoverable and signal.unresolved:
            return OwnerAttentionDecision(True, "UNRESOLVED_DIAGNOSTIC", signal.summary, ("RECOVERY_NOT_AVAILABLE",))
        return OwnerAttentionDecision(False, "INTERNAL_ONLY", "", ("SOLVE_BEFORE_REPORT", "OWNER_ATTENTION_PRESERVED"))


@dataclass(frozen=True, slots=True)
class IsolatedTaskPacket:
    task_id: str
    objective: str
    body: Mapping[str, Any]
    omitted_sections: tuple[str, ...]
    byte_count: int
    digest: str


class ContextIsolationBroker:
    """Compile bounded side-task packets and merge only result pointers upstream."""

    OPTIONAL_ORDER = ("evidence_summaries", "recent_failures", "notes", "metadata")
    MERGE_KEYS = ("summary", "decision", "proof_refs", "artifact_refs", "metrics")
    RAW_KEYS = ("raw_payload", "raw_tool_output", "full_transcript", "provider_dump")

    def __init__(self, *, max_packet_bytes: int = 6000, max_merge_bytes: int = 4000) -> None:
        if max_packet_bytes < 512 or max_merge_bytes < 256:
            raise ValueError("CONTEXT_ISOLATION_BUDGET_TOO_SMALL")
        self.max_packet_bytes = max_packet_bytes
        self.max_merge_bytes = max_merge_bytes

    def compile(
        self,
        *,
        task_id: str,
        objective: str,
        requirements: Sequence[str] = (),
        constraints: Sequence[str] = (),
        source_refs: Sequence[str] = (),
        evidence_summaries: Sequence[str] = (),
        recent_failures: Sequence[str] = (),
        notes: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> IsolatedTaskPacket:
        if not task_id.strip() or not objective.strip():
            raise ValueError("ISOLATED_TASK_IDENTITY_REQUIRED")
        body: dict[str, Any] = {
            "requirements": list(map(str, requirements)),
            "constraints": list(map(str, constraints)),
            "source_refs": list(map(str, source_refs)),
            "evidence_summaries": list(map(str, evidence_summaries)),
            "recent_failures": list(map(str, recent_failures)),
            "notes": list(map(str, notes)),
            "metadata": dict(metadata or {}),
        }
        omitted: list[str] = []

        def encoded() -> bytes:
            return _stable({"task_id": task_id, "objective": objective, "body": body, "omitted": omitted})

        for key in self.OPTIONAL_ORDER:
            if len(encoded()) <= self.max_packet_bytes:
                break
            if body.get(key):
                body.pop(key, None)
                omitted.append(key)
        if len(encoded()) > self.max_packet_bytes:
            raise ValueError("ISOLATED_REQUIRED_CONTEXT_EXCEEDS_BUDGET")
        digest = _digest({"task_id": task_id, "objective": objective, "body": body, "omitted": sorted(omitted)})
        return IsolatedTaskPacket(task_id, objective, dict(body), tuple(sorted(omitted)), len(encoded()), digest)

    def merge_result(self, result: Mapping[str, Any]) -> Mapping[str, Any]:
        for key in self.RAW_KEYS:
            if key in result and result.get(key) not in (None, "", (), [], {}):
                raise ValueError(f"RAW_SIDE_TASK_CONTEXT_PROHIBITED:{key}")
        merged = {key: result[key] for key in self.MERGE_KEYS if key in result}
        if not merged:
            raise ValueError("SIDE_TASK_MERGE_REQUIRES_RESULT_SUMMARY_OR_POINTER")
        if len(_stable(merged)) > self.max_merge_bytes:
            raise ValueError("SIDE_TASK_MERGE_EXCEEDS_BUDGET")
        return merged


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    provider: str
    capabilities: tuple[str, ...]
    source_fingerprint: str
    cache_scope: str
    created_at: float
    expires_at: float
    authority_ceiling: str = "A0_READ_ONLY"


@dataclass(frozen=True, slots=True)
class CatalogLookup:
    state: str
    provider: str
    capabilities: tuple[str, ...]
    source_fingerprint: str = ""
    authority_ceiling: str = "A0_READ_ONLY"


class CapabilityCatalogCache:
    """Deterministic TTL capability cache; cache state never implies authority."""

    SCOPES = {"session", "mission", "provider"}

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CatalogEntry] = {}

    def put(
        self,
        *,
        provider: str,
        capabilities: Sequence[str],
        source_fingerprint: str,
        now: float | None = None,
        ttl_ms: int = 300_000,
        cache_scope: str = "session",
        authority_ceiling: str = "A0_READ_ONLY",
    ) -> CatalogEntry:
        if not provider.strip() or not source_fingerprint.strip():
            raise ValueError("CATALOG_PROVIDER_AND_FINGERPRINT_REQUIRED")
        if cache_scope not in self.SCOPES or ttl_ms <= 0:
            raise ValueError("CATALOG_CACHE_HINT_INVALID")
        clock = time.time() if now is None else float(now)
        entry = CatalogEntry(
            provider=provider,
            capabilities=tuple(sorted(set(map(str, capabilities)))),
            source_fingerprint=source_fingerprint,
            cache_scope=cache_scope,
            created_at=clock,
            expires_at=clock + ttl_ms / 1000.0,
            authority_ceiling=authority_ceiling,
        )
        self._entries[(provider, cache_scope)] = entry
        return entry

    def get(
        self,
        *,
        provider: str,
        cache_scope: str = "session",
        now: float | None = None,
        required: Sequence[str] = (),
    ) -> CatalogLookup:
        entry = self._entries.get((provider, cache_scope))
        if entry is None:
            return CatalogLookup("MISS", provider, ())
        clock = time.time() if now is None else float(now)
        if clock >= entry.expires_at:
            return CatalogLookup("STALE", provider, (), entry.source_fingerprint, entry.authority_ceiling)
        required_set = set(map(str, required))
        if not required_set.issubset(set(entry.capabilities)):
            return CatalogLookup("CAPABILITY_MISS", provider, entry.capabilities, entry.source_fingerprint, entry.authority_ceiling)
        return CatalogLookup("HIT", provider, entry.capabilities, entry.source_fingerprint, entry.authority_ceiling)


@dataclass(frozen=True, slots=True)
class ActivityRequest:
    activity_id: str
    mission_id: str
    connector: str
    operation: str
    input_digest: str
    effectful: bool = False
    authorization_ref: str = ""
    readback_required: bool = True

    def validate(self) -> None:
        if not all(map(str.strip, (self.activity_id, self.mission_id, self.connector, self.operation, self.input_digest))):
            raise ValueError("ACTIVITY_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class ActivityDecision:
    state: str
    execute: bool
    result_ref: str = ""
    reasons: tuple[str, ...] = ()


class DurableActivityBoundary:
    """Temporal-style replay boundary over existing ChatGov durable receipts.

    Nondeterministic provider/tool calls live outside deterministic orchestration.
    A previously verified activity result is replayed by reference instead of
    re-executing the provider call. This class never performs the provider call.
    """

    def __init__(self, state: DurableState) -> None:
        self.state = state

    @staticmethod
    def _key(activity_id: str) -> str:
        return f"chatgov:activity:{activity_id}"

    def admit(self, request: ActivityRequest) -> ActivityDecision:
        request.validate()
        if request.effectful and not request.authorization_ref.strip():
            return ActivityDecision("HOLD_AUTHORIZATION_REQUIRED", False, reasons=("SOVARA_OR_HUMAN_FIRST_AUTHORIZATION_REQUIRED",))
        if request.effectful and not request.readback_required:
            return ActivityDecision("HOLD_READBACK_REQUIRED", False, reasons=("EFFECT_REQUIRES_SEMANTIC_READBACK",))
        existing = self.state.get_receipt(self._key(request.activity_id))
        if existing is None:
            return ActivityDecision("EXECUTE_ACTIVITY", True, reasons=("NO_RECORDED_RESULT",))
        payload = dict(existing.get("payload") or {})
        identity = {
            "mission_id": request.mission_id,
            "connector": request.connector,
            "operation": request.operation,
            "input_digest": request.input_digest,
            "effectful": request.effectful,
        }
        if payload.get("identity") != identity:
            return ActivityDecision("REJECT_DIVERGENT_REPLAY", False, reasons=("ACTIVITY_ID_REUSED_WITH_DIFFERENT_INPUT",))
        if bool(existing.get("success")) and bool(existing.get("semantic_ok")) and payload.get("result_ref"):
            return ActivityDecision("REPLAY_RECORDED_RESULT", False, str(payload["result_ref"]), ("VERIFIED_RESULT_REUSED",))
        return ActivityDecision("HOLD_INCOMPLETE_PRIOR_ACTIVITY", False, reasons=("PRIOR_RESULT_NOT_SEMANTICALLY_VERIFIED",))

    def record_result(
        self,
        request: ActivityRequest,
        *,
        success: bool,
        semantic_ok: bool,
        result_ref: str,
    ) -> None:
        request.validate()
        if semantic_ok and not result_ref.strip():
            raise ValueError("ACTIVITY_SEMANTIC_RESULT_REF_REQUIRED")
        identity = {
            "mission_id": request.mission_id,
            "connector": request.connector,
            "operation": request.operation,
            "input_digest": request.input_digest,
            "effectful": request.effectful,
        }
        self.state.save_receipt(
            key=self._key(request.activity_id),
            mission_id=request.mission_id,
            action="ACTIVITY_RESULT",
            target=request.connector,
            success=success,
            semantic_ok=semantic_ok,
            payload={"identity": identity, "result_ref": result_ref},
        )


@dataclass(frozen=True, slots=True)
class ParallelismObservation:
    read_only_lanes: int
    effectful_lanes: int
    context_utilization: float
    connector_failure_ewma: float
    latency_ewma: float = 0.0


@dataclass(frozen=True, slots=True)
class ParallelismDecision:
    read_only_max_workers: int
    effectful_max_workers: int
    reasons: tuple[str, ...]


class AdaptiveParallelismController:
    """Scale independent reads while preventing effectful fan-out storms."""

    def __init__(self, *, hard_read_cap: int = 8) -> None:
        if hard_read_cap < 1:
            raise ValueError("PARALLELISM_CAP_INVALID")
        self.hard_read_cap = hard_read_cap

    def decide(self, obs: ParallelismObservation) -> ParallelismDecision:
        if min(obs.read_only_lanes, obs.effectful_lanes) < 0:
            raise ValueError("PARALLELISM_LANE_COUNT_INVALID")
        if not 0.0 <= obs.context_utilization <= 1.0 or not 0.0 <= obs.connector_failure_ewma <= 1.0:
            raise ValueError("PARALLELISM_OBSERVATION_RANGE_INVALID")
        reasons: list[str] = []
        if obs.context_utilization >= 0.85 or obs.connector_failure_ewma >= 0.35:
            read_cap = 1
            reasons.append("PRESSURE_SHED")
        elif obs.context_utilization >= 0.65 or obs.connector_failure_ewma >= 0.20:
            read_cap = 2
            reasons.append("CONSERVATIVE_PARALLELISM")
        elif obs.context_utilization <= 0.35 and obs.connector_failure_ewma <= 0.05:
            read_cap = min(6, self.hard_read_cap)
            reasons.append("SAFE_READ_FANOUT")
        else:
            read_cap = min(4, self.hard_read_cap)
            reasons.append("BALANCED_PARALLELISM")
        if obs.latency_ewma > 5.0 and read_cap < self.hard_read_cap and obs.context_utilization < 0.65:
            read_cap = min(read_cap + 1, self.hard_read_cap)
            reasons.append("LATENCY_HIDING_READ_FANOUT")
        return ParallelismDecision(
            read_only_max_workers=min(max(obs.read_only_lanes, 1), read_cap) if obs.read_only_lanes else 0,
            effectful_max_workers=1 if obs.effectful_lanes else 0,
            reasons=tuple(reasons + (["EFFECTFUL_SINGLE_FLIGHT"] if obs.effectful_lanes else [])),
        )


@dataclass(frozen=True, slots=True)
class StablePrefixPlan:
    stable_prefix: Mapping[str, Any]
    volatile_suffix: Mapping[str, Any]
    stable_digest: str
    stable_bytes: int


class StablePrefixCompiler:
    """Keep invariant control context stable and volatile evidence behind it."""

    def __init__(self, *, max_stable_bytes: int = 16_000) -> None:
        self.max_stable_bytes = max_stable_bytes

    def compile(self, invariant: Mapping[str, Any], volatile: Mapping[str, Any]) -> StablePrefixPlan:
        prefix = {str(k): invariant[k] for k in sorted(invariant)}
        suffix = {str(k): volatile[k] for k in sorted(volatile)}
        size = len(_stable(prefix))
        if size > self.max_stable_bytes:
            raise ValueError("STABLE_PREFIX_EXCEEDS_BUDGET")
        return StablePrefixPlan(prefix, suffix, _digest(prefix), size)


__all__ = [
    "ActivityDecision", "ActivityRequest", "AdaptiveParallelismController",
    "CapabilityCatalogCache", "CatalogEntry", "CatalogLookup", "ContextIsolationBroker",
    "DurableActivityBoundary", "HookContext", "HookDispatchReceipt", "HookEvent",
    "HookOutcome", "IsolatedTaskPacket", "LifecycleHookBus", "OwnerAttentionDecision",
    "OwnerAttentionGovernor", "OwnerSignal", "OwnerSignalKind", "ParallelismDecision",
    "ParallelismObservation", "StablePrefixCompiler", "StablePrefixPlan",
]
