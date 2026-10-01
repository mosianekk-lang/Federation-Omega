from __future__ import annotations

"""Hypercube adaptive response runtime.

Pure/deterministic decision layer for bottleneck auto-response.  It consumes the
existing Failure Queue, Route Memory and Learning Ledger shapes; it does not create
another truth plane and it has no provider/tool execution authority.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from .hypercube_bottleneck_resolver import (
    BottleneckResolution,
    BottleneckSignal,
    HypercubeBottleneckResolver,
)

SCHEMA = "FUSE-HYPERCUBE-ADAPTIVE-RESPONSE-V1"
VERSION = "1.0.0"


class AdaptiveAction(str, Enum):
    REUSE_CHAMPION = "REUSE_CHAMPION"
    SUPPRESS_NO_DELTA = "SUPPRESS_NO_DELTA"
    CHANGED_MECHANISM_REQUIRED = "CHANGED_MECHANISM_REQUIRED"
    HARVEST_COMPOSE = "HARVEST_COMPOSE"
    HARVEST_BUILD_RESIDUAL = "HARVEST_BUILD_RESIDUAL"
    HARD_GATE_WAIT = "HARD_GATE_WAIT"
    WORK_WHILE_WAITING = "WORK_WHILE_WAITING"


@dataclass(frozen=True, slots=True)
class RouteMemoryRecord:
    route_id: str
    failure_fingerprint: str
    state: str
    confidence: str = ""
    invalidation_key: str = ""
    notes: str = ""

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "RouteMemoryRecord":
        def pick(*names: str) -> str:
            lower = {str(k).lower(): v for k, v in row.items()}
            for name in names:
                value = lower.get(name.lower())
                if value is not None:
                    return str(value)
            return ""
        return cls(
            route_id=pick("RouteId", "route_id"),
            failure_fingerprint=pick("FailureFingerprint", "failure_fingerprint"),
            state=pick("State", "state"),
            confidence=pick("Confidence", "confidence"),
            invalidation_key=pick("InvalidationKey", "invalidation_key"),
            notes=pick("Notes", "notes"),
        )


@dataclass(frozen=True, slots=True)
class FailureMemoryRecord:
    failure_id: str
    fingerprint: str
    route: str
    state: str
    invalidation_key: str = ""

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> "FailureMemoryRecord":
        def pick(*names: str) -> str:
            lower = {str(k).lower(): v for k, v in row.items()}
            for name in names:
                value = lower.get(name.lower())
                if value is not None:
                    return str(value)
            return ""
        return cls(
            failure_id=pick("FailureId", "failure_id"),
            fingerprint=pick("Fingerprint", "fingerprint"),
            route=pick("Route", "route"),
            state=pick("State", "state"),
            invalidation_key=pick("InvalidationKey", "invalidation_key"),
        )


@dataclass(frozen=True, slots=True)
class AdaptiveResponseDecision:
    schema: str
    version: str
    fingerprint: str
    action: AdaptiveAction
    selected_route_id: str | None
    negative_cache_hit: bool
    changed_mechanism_required: bool
    harvest_required: bool
    build_residual_required: bool
    work_while_waiting: bool
    formation_routes_required: int
    external_effect_authorized: bool
    resolution: BottleneckResolution | None
    next_actions: tuple[str, ...]
    receipt_sha256: str


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


class AdaptiveBottleneckRuntime:
    """Convert learned failure/route memory into the next safe bottleneck action."""

    _CHAMPION_STATES = {
        "CHAMPION",
        "VERIFIED",
        "ACTIVE",
        "SUCCESS",
        "ADMITTED",
        "RELEASED",
        "GLOBAL_CONTROL_BOUND",
    }

    def __init__(self, *, resolver: HypercubeBottleneckResolver | None = None) -> None:
        self.resolver = resolver or HypercubeBottleneckResolver()
        self.routes: tuple[RouteMemoryRecord, ...] = ()
        self.failures: tuple[FailureMemoryRecord, ...] = ()
        self.learning_memory: tuple[Mapping[str, object], ...] = ()

    def load_memory(
        self,
        *,
        route_memory: Sequence[Mapping[str, object]] = (),
        failure_memory: Sequence[Mapping[str, object]] = (),
        learning_memory: Sequence[Mapping[str, object]] = (),
    ) -> None:
        self.routes = tuple(RouteMemoryRecord.from_mapping(row) for row in route_memory)
        self.failures = tuple(FailureMemoryRecord.from_mapping(row) for row in failure_memory)
        self.learning_memory = tuple(dict(row) for row in learning_memory)

    def _champion(self, fingerprint: str) -> RouteMemoryRecord | None:
        rows = [
            row
            for row in self.routes
            if row.failure_fingerprint == fingerprint and row.state.upper() in self._CHAMPION_STATES
        ]
        if not rows:
            return None
        return sorted(rows, key=lambda row: (row.route_id, row.confidence), reverse=True)[0]

    def _negative_cached(self, fingerprint: str) -> bool:
        if any(
            row.failure_fingerprint == fingerprint and "NEGATIVE_CACHED" in row.state.upper()
            for row in self.routes
        ):
            return True
        return any(
            row.fingerprint == fingerprint and "NEGATIVE_CACHED" in row.state.upper()
            for row in self.failures
        )

    def decide(
        self,
        *,
        signal: BottleneckSignal,
        fingerprint: str,
        current_state_signature: str,
        previous_state_signature: str | None = None,
        same_semantic_failures: int = 0,
        invalidation_changed: bool = False,
        external_wait: bool = False,
        hard_gate: bool = False,
    ) -> AdaptiveResponseDecision:
        signal = signal.validate()
        if not fingerprint.strip():
            raise ValueError("HYPERCUBE_ADAPTIVE_FINGERPRINT_REQUIRED")
        if not current_state_signature.strip():
            raise ValueError("HYPERCUBE_ADAPTIVE_STATE_SIGNATURE_REQUIRED")
        if same_semantic_failures < 0:
            raise ValueError("HYPERCUBE_ADAPTIVE_FAILURE_COUNT_NONNEGATIVE")

        no_delta = (
            previous_state_signature is not None
            and previous_state_signature == current_state_signature
            and not invalidation_changed
        )
        negative_cache = self._negative_cached(fingerprint) and not invalidation_changed
        champion = self._champion(fingerprint)
        resolution: BottleneckResolution | None = None
        selected_route_id: str | None = None
        changed = False
        harvest = False
        residual = False
        work = False
        formation = 0

        if no_delta and (negative_cache or same_semantic_failures > 0):
            action = AdaptiveAction.SUPPRESS_NO_DELTA
            work = True
            next_actions = (
                "NEGATIVE_CACHE_EXACT_QUERY_STATE",
                "EXECUTE_DEPENDENCY_SAFE_DISJOINT_WORK",
                "WAIT_FOR_MATERIAL_INVALIDATION_KEY",
                "BATCH_NEXT_READBACK",
            )
        elif hard_gate and not invalidation_changed:
            action = AdaptiveAction.HARD_GATE_WAIT
            work = True
            next_actions = (
                "PRESERVE_HARD_GATE_WITHOUT_AUTHORITY_INFLATION",
                "EXECUTE_UNRELATED_SAFE_LANES",
                "RECHECK_ONLY_ON_MATERIAL_AUTHORITY_OR_RESOURCE_CHANGE",
            )
        elif same_semantic_failures >= 3:
            action = AdaptiveAction.HARVEST_BUILD_RESIDUAL
            changed = True
            harvest = True
            residual = True
            formation = 3
            resolution = self.resolver.resolve(signal)
            next_actions = (
                "RUN_LAWFUL_5D_HARVEST",
                "GENERATE_UP_TO_3_FORMATION_CLEAN_SHEET_ROUTES",
                "INCLUDE_SIMPLIFICATION_AND_DIRECT_NATIVE_CHALLENGERS",
                "EXECUTE_TOP_SAFE_CHANGED_MECHANISM",
                "PROVE_AND_LEARN",
            )
        elif same_semantic_failures >= 2:
            action = AdaptiveAction.CHANGED_MECHANISM_REQUIRED
            changed = True
            harvest = True
            resolution = self.resolver.resolve(signal)
            next_actions = (
                "FORBID_SAME_SEMANTIC_RETRY",
                "SELECT_DIFFERENT_MECHANISM_FAMILY",
                "EXECUTE_AND_READ_BACK",
                "WRITE_OUTCOME_TO_ROUTE_MEMORY",
            )
        elif champion is not None and not negative_cache:
            action = AdaptiveAction.REUSE_CHAMPION
            selected_route_id = champion.route_id
            next_actions = (
                "EXECUTE_PROVEN_CHAMPION_ROUTE",
                "READ_BACK_EFFECT_OR_PROOF",
                "REMEASURE_BOTTLENECK",
                "UPDATE_CONFIDENCE_AND_CHALLENGER_QUEUE",
            )
        elif external_wait:
            action = AdaptiveAction.WORK_WHILE_WAITING
            work = True
            next_actions = (
                "PARK_EXTERNAL_WAIT_WITHOUT_COMPUTE_LOOP",
                "EXECUTE_DEPENDENCY_SAFE_DISJOINT_WORK",
                "RECHECK_ON_MATERIAL_EVENT",
            )
        else:
            action = AdaptiveAction.HARVEST_COMPOSE
            harvest = True
            resolution = self.resolver.resolve(signal)
            next_actions = (
                "REUSE_INTERNAL_CAPABILITY_FIRST",
                "RUN_LAWFUL_5D_HARVEST_FOR_GAPS",
                "COMPOSE_OR_BUILD_RESIDUAL",
                "EXECUTE_IN_SHADOW_OR_SAFE_LANE",
                "PROVE_AND_LEARN",
            )

        body = {
            "schema": SCHEMA,
            "version": VERSION,
            "fingerprint": fingerprint,
            "action": action.value,
            "selected_route_id": selected_route_id,
            "negative_cache_hit": negative_cache,
            "changed_mechanism_required": changed,
            "harvest_required": harvest,
            "build_residual_required": residual,
            "work_while_waiting": work,
            "formation_routes_required": formation,
            "external_effect_authorized": False,
            "resolution_receipt": resolution.receipt_sha256 if resolution else None,
            "next_actions": list(next_actions),
        }
        return AdaptiveResponseDecision(
            schema=SCHEMA,
            version=VERSION,
            fingerprint=fingerprint,
            action=action,
            selected_route_id=selected_route_id,
            negative_cache_hit=negative_cache,
            changed_mechanism_required=changed,
            harvest_required=harvest,
            build_residual_required=residual,
            work_while_waiting=work,
            formation_routes_required=formation,
            external_effect_authorized=False,
            resolution=resolution,
            next_actions=next_actions,
            receipt_sha256=_digest(body),
        )

    def learn_outcome(
        self,
        *,
        decision: AdaptiveResponseDecision,
        success: bool,
        state_signature: str,
        evidence_refs: Sequence[str],
        route_id: str | None = None,
    ) -> dict[str, object]:
        if not state_signature.strip():
            raise ValueError("HYPERCUBE_LEARNING_STATE_SIGNATURE_REQUIRED")
        if not evidence_refs:
            raise ValueError("HYPERCUBE_LEARNING_EVIDENCE_REQUIRED")
        resolved_route = route_id or decision.selected_route_id
        if resolved_route is None and decision.resolution is not None:
            resolved_route = decision.resolution.selected.candidate_id
        resolved_route = resolved_route or "NO_EXECUTED_ROUTE"

        failure_state = "RESOLVED_PROVEN" if success else "NEGATIVE_CACHED_REROUTED"
        route_state = "CHAMPION" if success else "NEGATIVE_CACHED"
        outcome = "PROVEN_ROUTE_LEARNING" if success else "FAILED_ROUTE_LEARNING"
        learning = {
            "schema": "FUSE-HYPERCUBE-ADAPTIVE-LEARNING-V1",
            "failure_fingerprint": decision.fingerprint,
            "route_id": resolved_route,
            "outcome": outcome,
            "state_signature": state_signature,
            "evidence_refs": list(evidence_refs),
            "promotable": bool(success),
            "external_effect_authorized": False,
        }
        return {
            "failure_queue": {
                "Fingerprint": decision.fingerprint,
                "Route": resolved_route,
                "State": failure_state,
                "InvalidationKey": state_signature,
                "EvidenceRef": "|".join(evidence_refs),
            },
            "route_memory": {
                "RouteId": resolved_route,
                "FailureFingerprint": decision.fingerprint,
                "State": route_state,
                "Confidence": "HIGH" if success else "MEDIUM",
                "InvalidationKey": state_signature,
                "Notes": "Adaptive response outcome; proof-before-promotion preserved.",
            },
            "learning_ledger": learning,
            "learning_sha256": _digest(learning),
        }
