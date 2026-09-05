"""CFBE execution-progress governor v1.

This module binds existing Federation progress, failure-genome and route-selection
principles at the execution boundary. It does not execute tools itself and it does
not create authority. Hosts call ``preflight`` before a tool/action and
``record_attempt`` after readback.

The central invariant is simple: the same action against the same material state
may receive a bounded retry budget, but repeated zero-progress attempts must open
the circuit and force a materially different route.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from evidenceops.capital_intelligence_os.failure_genome import FailureToRouteGeneCompiler
from formation_omega.autonomic_fabric import MissionStateVector, MonotonicClosureGate


def _stable_hash(value: Any) -> str:
    body = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return sha256(body.encode("utf-8")).hexdigest()


def _normalise_text(value: str) -> str:
    return " ".join(re.sub(r"\s+", " ", value or "").strip().split())


def canonical_action_fingerprint(
    *,
    action_name: str,
    arguments: Mapping[str, Any],
    state_version: str,
    scope_id: str = "",
) -> str:
    """Hash an action together with the exact material state it targets.

    ``state_version`` is deliberately part of the fingerprint. The same action is
    therefore retryable after genuinely new state/evidence appears, while an
    unchanged-state loop is detectable.
    """

    material = {
        "action_name": _normalise_text(action_name),
        "arguments": dict(arguments),
        "state_version": _normalise_text(state_version),
        "scope_id": _normalise_text(scope_id),
    }
    if not material["action_name"]:
        raise ValueError("action_name is required")
    if not material["state_version"]:
        raise ValueError("state_version is required")
    return "act_" + _stable_hash(material)[:24]


@dataclass(frozen=True)
class PreflightDecision:
    allow: bool
    mode: str
    action_fingerprint: str
    prior_zero_progress_attempts: int
    reason: str
    suggested_route: str = ""
    regression_rule: str = ""


@dataclass(frozen=True)
class ProgressReceipt:
    attempt_id: str
    action_fingerprint: str
    decision: str
    progress_accepted: bool
    progress_axes: tuple[str, ...]
    regressed_axes: tuple[str, ...]
    axis_deltas: tuple[tuple[str, float], ...]
    same_state_zero_progress_attempts: int
    global_zero_progress_streak: int
    result_digest: str
    route_gene_classification: str
    suggested_route: str
    regression_rule: str


@dataclass(frozen=True)
class StatusUpdateDecision:
    allow: bool
    mode: str
    state_digest: str
    update_digest: str
    reason: str


class ExecutionProgressGovernor:
    """Deterministic circuit breaker for unchanged zero-progress actions."""

    def __init__(
        self,
        *,
        same_state_retry_budget: int = 2,
        zero_progress_streak_limit: int = 3,
        closure_gate: MonotonicClosureGate | None = None,
        failure_compiler: FailureToRouteGeneCompiler | None = None,
    ) -> None:
        if same_state_retry_budget < 1:
            raise ValueError("same_state_retry_budget must be at least one")
        if zero_progress_streak_limit < 1:
            raise ValueError("zero_progress_streak_limit must be at least one")
        self.same_state_retry_budget = int(same_state_retry_budget)
        self.zero_progress_streak_limit = int(zero_progress_streak_limit)
        self.closure_gate = closure_gate or MonotonicClosureGate()
        self.failure_compiler = failure_compiler or FailureToRouteGeneCompiler()
        self._zero_progress_by_fingerprint: dict[str, int] = {}
        self._last_failure_by_fingerprint: dict[str, str] = {}
        self._blocked_fingerprints: set[str] = set()
        self._global_zero_progress_streak = 0

    def preflight(
        self,
        *,
        action_name: str,
        arguments: Mapping[str, Any],
        state_version: str,
        scope_id: str = "",
    ) -> PreflightDecision:
        fingerprint = canonical_action_fingerprint(
            action_name=action_name,
            arguments=arguments,
            state_version=state_version,
            scope_id=scope_id,
        )
        count = self._zero_progress_by_fingerprint.get(fingerprint, 0)
        if fingerprint in self._blocked_fingerprints or count >= self.same_state_retry_budget:
            gene = self.failure_compiler.compile(
                self._last_failure_by_fingerprint.get(fingerprint, "unchanged route made no progress")
            )
            return PreflightDecision(
                allow=False,
                mode="ROUTE_MUTATION_REQUIRED",
                action_fingerprint=fingerprint,
                prior_zero_progress_attempts=count,
                reason="UNCHANGED_SAME_STATE_ROUTE_CIRCUIT_OPEN",
                suggested_route=gene.smallest_safe_repair,
                regression_rule=gene.regression_rule,
            )
        return PreflightDecision(
            allow=True,
            mode="ALLOW_BOUNDED_ATTEMPT",
            action_fingerprint=fingerprint,
            prior_zero_progress_attempts=count,
            reason="WITHIN_RETRY_BUDGET",
        )

    def record_attempt(
        self,
        *,
        action_name: str,
        arguments: Mapping[str, Any],
        state_version: str,
        before: MissionStateVector,
        after: MissionStateVector,
        result_summary: str = "",
        scope_id: str = "",
    ) -> ProgressReceipt:
        fingerprint = canonical_action_fingerprint(
            action_name=action_name,
            arguments=arguments,
            state_version=state_version,
            scope_id=scope_id,
        )
        gate = self.closure_gate.evaluate(before, after)
        left = before.normalized()
        right = after.normalized()
        axis_deltas = tuple(
            (axis, round(getattr(right, axis) - getattr(left, axis), 12))
            for axis in self.closure_gate.AXES
        )
        result_digest = _stable_hash(_normalise_text(result_summary))
        route_gene = self.failure_compiler.compile(result_summary or gate.reason)

        if gate.accepted:
            self._zero_progress_by_fingerprint.pop(fingerprint, None)
            self._last_failure_by_fingerprint.pop(fingerprint, None)
            self._blocked_fingerprints.discard(fingerprint)
            self._global_zero_progress_streak = 0
            decision = "ACCEPT_PROGRESS"
            same_state_count = 0
        else:
            same_state_count = self._zero_progress_by_fingerprint.get(fingerprint, 0) + 1
            self._zero_progress_by_fingerprint[fingerprint] = same_state_count
            self._last_failure_by_fingerprint[fingerprint] = result_summary or gate.reason
            self._global_zero_progress_streak += 1
            if gate.regressed_axes:
                self._blocked_fingerprints.add(fingerprint)
                decision = "REJECT_REGRESSION_ROUTE_MUTATION_REQUIRED"
            elif same_state_count >= self.same_state_retry_budget:
                self._blocked_fingerprints.add(fingerprint)
                decision = "REQUIRE_ROUTE_MUTATION"
            elif self._global_zero_progress_streak >= self.zero_progress_streak_limit:
                decision = "ESCAPE_ROUTE_REQUIRED"
            else:
                decision = "RETRY_BUDGET_REMAINS"

        attempt_material = {
            "fingerprint": fingerprint,
            "decision": decision,
            "same_state_count": same_state_count,
            "global_streak": self._global_zero_progress_streak,
            "result_digest": result_digest,
            "axis_deltas": axis_deltas,
        }
        return ProgressReceipt(
            attempt_id="att_" + _stable_hash(attempt_material)[:20],
            action_fingerprint=fingerprint,
            decision=decision,
            progress_accepted=gate.accepted,
            progress_axes=gate.improved_axes,
            regressed_axes=gate.regressed_axes,
            axis_deltas=axis_deltas,
            same_state_zero_progress_attempts=same_state_count,
            global_zero_progress_streak=self._global_zero_progress_streak,
            result_digest=result_digest,
            route_gene_classification=route_gene.classification,
            suggested_route=route_gene.smallest_safe_repair,
            regression_rule=route_gene.regression_rule,
        )


class StatusUpdateGate:
    """Suppresses status narration when the underlying material state did not move."""

    def __init__(self) -> None:
        self._last_state_digest: str | None = None

    def evaluate(
        self,
        *,
        state_digest: str,
        update_text: str,
        material_event: bool = False,
    ) -> StatusUpdateDecision:
        if not state_digest.strip():
            raise ValueError("state_digest is required")
        update_digest = _stable_hash(_normalise_text(update_text))
        if material_event:
            self._last_state_digest = state_digest
            return StatusUpdateDecision(
                True,
                "ALLOW_MATERIAL_EVENT",
                state_digest,
                update_digest,
                "MATERIAL_EVENT",
            )
        if self._last_state_digest == state_digest:
            return StatusUpdateDecision(
                False,
                "SUPPRESS_ZERO_DELTA_STATUS",
                state_digest,
                update_digest,
                "NO_MATERIAL_STATE_CHANGE",
            )
        self._last_state_digest = state_digest
        return StatusUpdateDecision(
            True,
            "ALLOW_STATE_DELTA_STATUS",
            state_digest,
            update_digest,
            "MATERIAL_STATE_CHANGED",
        )


__all__ = [
    "ExecutionProgressGovernor",
    "PreflightDecision",
    "ProgressReceipt",
    "StatusUpdateDecision",
    "StatusUpdateGate",
    "canonical_action_fingerprint",
]
