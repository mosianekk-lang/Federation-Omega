from __future__ import annotations

import hashlib
import json
import random
import time
from typing import Any, Callable, Dict, Optional

from .currentness import CurrentnessDecision
from .frontier_binding_v1 import FrontierControlPlane, SAFE_SINGLEFLIGHT_EFFECTS
from .routing import MissionPlan
from .state import DurableState


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class ConnectorGateway:
    """Enforce routing, idempotency, retries, circuits and semantic readback.

    Explicit NO_EFFECT / READ_ONLY operations additionally pass through the
    load-bearing frontier single-flight coordinator. Existing callers preserve the
    prior behavior because the default effect class is UNSPECIFIED and therefore
    never enters the safe-read coalescing path.

    When a caller supplies a CurrentnessDecision, durable receipt reuse is allowed
    only while that decision is CURRENT, semantically bound to the caller's exact
    subject, and anchored to the same provider/source observation identity. A
    stale/invalid safe-read decision forces real re-execution; a stale/invalid
    non-read decision fails closed before any effectful handler can run. The
    gateway does not manufacture currentness or authority when no decision is
    supplied.
    """

    def __init__(
        self,
        state: DurableState,
        frontier: Optional[FrontierControlPlane] = None,
    ) -> None:
        self.state = state
        self.frontier = frontier or FrontierControlPlane()

    @staticmethod
    def idempotency_key(
        mission_id: str, action: str, target: str, source_version: str = ""
    ) -> str:
        return _sha(
            {
                "mission_id": mission_id,
                "action": action,
                "target": target,
                "source_version": source_version,
            }
        )

    def execute(
        self,
        *,
        plan: MissionPlan,
        connector: str,
        action: str,
        target: str,
        fn: Callable[[], Any],
        semantic_check: Optional[Callable[[Any], bool]] = None,
        source_version: str = "",
        force_revalidation: bool = False,
        retry_attempts: int = 3,
        retry_base_seconds: float = 0.15,
        retry_max_seconds: float = 2.0,
        effect_class: str = "UNSPECIFIED",
        use_frontier: bool = True,
        currentness: Optional[CurrentnessDecision] = None,
        currentness_subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        if connector not in plan.active_connectors:
            raise PermissionError(
                f"Connector {connector!r} is not active for mission {plan.mission_id}"
            )
        if connector in plan.excluded_connectors:
            raise PermissionError(f"Connector {connector!r} is excluded by mission plan")
        if not self.state.circuit_allows(connector):
            raise RuntimeError(f"Circuit open for connector {connector}")

        effect = str(effect_class).strip().upper()
        expected_subject = str(currentness_subject or "").strip()
        currentness_state = currentness.state if currentness is not None else "UNSPECIFIED"
        currentness_refresh_required = bool(currentness is not None and not currentness.reusable)
        currentness_anchor = ""
        if currentness is not None:
            if currentness.mission_id != plan.mission_id:
                raise ValueError("CURRENTNESS_MISSION_MISMATCH")
            if not expected_subject:
                raise ValueError("CURRENTNESS_SUBJECT_REQUIRED")
            if currentness.subject != expected_subject:
                raise ValueError("CURRENTNESS_SUBJECT_MISMATCH")
            currentness_anchor = str(
                currentness.source_ref or currentness.projection_id or ""
            ).strip()
            if currentness.reusable and not currentness_anchor:
                raise ValueError("CURRENTNESS_REUSE_ANCHOR_REQUIRED")
        if currentness_refresh_required and effect not in SAFE_SINGLEFLIGHT_EFFECTS:
            raise RuntimeError(
                "CURRENTNESS_REFRESH_REQUIRED_BEFORE_NON_READ:"
                + str(currentness.stale_action or "REFRESH_REQUIRED")
            )

        reuse_epoch = str(source_version)
        if currentness is not None:
            reuse_epoch = _sha(
                {
                    "source_version": source_version,
                    "currentness_subject": expected_subject,
                    "currentness_anchor": currentness_anchor or currentness.state,
                }
            )
        key = self.idempotency_key(plan.mission_id, action, target, reuse_epoch)
        prior = self.state.get_receipt(key)
        reuse_allowed = not force_revalidation and not currentness_refresh_required
        if prior and prior["success"] and prior["semantic_ok"] and reuse_allowed:
            return {
                "reused": True,
                "reuse_source": "DURABLE_IDEMPOTENCY_RECEIPT",
                "idempotency_key": key,
                "payload": prior["payload"],
                "currentness_state": currentness_state,
                "currentness_subject": expected_subject,
                "currentness_anchor": currentness_anchor,
                "currentness_refresh_performed": False,
            }

        def execute_core() -> Dict[str, Any]:
            started = time.time()
            last_error = ""
            for attempt in range(1, retry_attempts + 1):
                try:
                    payload = fn()
                    semantic_ok = bool(semantic_check(payload)) if semantic_check else True
                    if not semantic_ok:
                        raise ValueError("Semantic readback failed")

                    elapsed_ms = (time.time() - started) * 1000.0
                    self.state.update_metric("connector.latency_ms", elapsed_ms)
                    self.state.update_metric("connector.failure_rate", 0.0)
                    self.state.circuit_success(connector)
                    self.state.save_receipt(
                        key=key,
                        mission_id=plan.mission_id,
                        action=action,
                        target=target,
                        success=True,
                        semantic_ok=True,
                        payload=payload,
                    )
                    return {
                        "reused": False,
                        "reuse_source": "EXECUTED",
                        "idempotency_key": key,
                        "payload": payload,
                        "attempts": attempt,
                        "latency_ms": round(elapsed_ms, 2),
                        "currentness_state": currentness_state,
                        "currentness_subject": expected_subject,
                        "currentness_anchor": currentness_anchor,
                        "currentness_refresh_performed": currentness_refresh_required,
                    }
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    self.state.circuit_failure(connector, last_error)
                    self.state.update_metric("connector.failure_rate", 1.0)
                    if attempt >= retry_attempts:
                        break
                    delay = min(
                        retry_max_seconds,
                        retry_base_seconds * (2 ** (attempt - 1)),
                    )
                    delay *= 0.9 + random.random() * 0.2
                    time.sleep(delay)

            self.state.save_receipt(
                key=key,
                mission_id=plan.mission_id,
                action=action,
                target=target,
                success=False,
                semantic_ok=False,
                payload={"error": last_error},
            )
            raise RuntimeError(
                f"Connector execution failed after {retry_attempts} attempts: {last_error}"
            )

        if (
            use_frontier
            and not force_revalidation
            and effect in SAFE_SINGLEFLIGHT_EFFECTS
        ):
            result = self.frontier.execute_safe_read(
                key=key,
                fn=execute_core,
                effect_class=effect,
            )
            # A coalesced waiter receives the first caller's exact proof-bearing
            # execution result. No synthetic provider success is manufactured.
            return {**result, "frontier_singleflight": True}

        return {**execute_core(), "frontier_singleflight": False}


class StallDetector:
    """Detect repeated no-progress patterns and return a repair route."""

    def __init__(self, state: DurableState) -> None:
        self.state = state

    def detect(
        self,
        mission_id: str,
        *,
        repeated_blockers: Dict[str, int],
        duplicate_retrievals: int = 0,
        irrelevant_connectors: Optional[list[str]] = None,
        repeat_limit: int = 2,
        no_progress_seconds: int = 18 * 60,
    ) -> Dict[str, Any]:
        reasons: list[str] = []
        for blocker, count in repeated_blockers.items():
            if count >= repeat_limit:
                reasons.append(f"REPEATED_BLOCKER:{blocker}:{count}")
        if duplicate_retrievals:
            reasons.append(f"DUPLICATE_RETRIEVAL:{duplicate_retrievals}")
        if irrelevant_connectors:
            reasons.append("IRRELEVANT_CONNECTORS:" + ",".join(irrelevant_connectors))
        last_proof = self.state.last_proof_checkpoint_at(mission_id)
        if last_proof is not None and time.time() - last_proof >= no_progress_seconds:
            reasons.append(f"NO_PROOF_PROGRESS_SECONDS:{int(time.time() - last_proof)}")
        return {
            "stalled": bool(reasons),
            "reasons": reasons,
            "repair_sequence": [
                "isolate dependent lane",
                "cancel redundant retrieval",
                "remove irrelevant connectors",
                "restore latest durable checkpoint",
                "continue independent executable lanes",
                "write next proof-bearing checkpoint",
            ] if reasons else [],
        }
