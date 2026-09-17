from __future__ import annotations

import dataclasses
import json
import time
from typing import Any, Mapping

try:
    from .fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from .sol_62_frontier_primitives import ConstraintError, digest
except ImportError:
    from fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from sol_62_frontier_primitives import ConstraintError, digest


SOVEREIGN_REPLACEMENT_VERSION = "1.0.0"
FUSE_OWNED_PROVIDERS = {"fuse", "fuse-native", "owner-native", "local-fuse"}

REPLACEMENT_COMPONENT_RULES = (
    (("WORKFLOW", "AIRLOCK", "CI", "ADMISSION", "POLICY"), "FUSE_FORGE_PROOF_GATE"),
    (("IDENTITY", "AUTH", "OIDC", "PERMISSION", "CREDENTIAL"), "FUSE_IDENTITY_AUTHORITY"),
    (("CONFIG", "VARIABLE", "SECRET"), "FUSE_CONFIG_VAULT"),
    (("ARTIFACT", "REGISTRY", "PACKAGE"), "FUSE_ARTIFACT_STORE"),
    (("HOST", "CLOUD_RUN", "SERVICE", "DEPLOYMENT"), "FUSE_SERVICE_FABRIC"),
    (("SYNC", "DRIVE", "SHEET", "MEMORY", "DATA"), "FUSE_MEMORY_FABRIC"),
    (("MCP", "API", "CAPABILITY", "CONNECTOR"), "FUSE_CAPABILITY_BUS"),
    (("RATE", "QUOTA", "MODEL", "COMPUTE"), "FUSE_COMPUTE_ROUTER"),
    (("REPO", "GIT", "SOURCE"), "FUSE_SOURCE_LEDGER"),
)

REPLACEMENT_LIFECYCLE = (
    "DETECT_EXTERNAL_FRICTION",
    "REUSE_EXISTING_FUSE_NATIVE_FIRST",
    "BUILD_MINIMUM_MISSING_FUSE_NATIVE",
    "DETERMINISTIC_TEST",
    "ADVERSARIAL_PROOF",
    "PROMOTE_FUSE_NATIVE_ON_EVIDENCE",
    "DEMOTE_EXTERNAL_TO_OPTIONAL_ADAPTER",
    "RETIRE_EXTERNAL_CONTROL_DEPENDENCY",
)


class SovereignFederationDistributedOperatingFabric(FederationDistributedOperatingFabric):
    """FDOF extension that converts provider friction into FUSE-owned replacement work.

    External systems remain optional adapters. A blocked provider route is never treated
    as the end of the mission: it creates an idempotent sovereign replacement signal.
    The base FDOF routing contract is preserved; callers that want a non-raising form
    can use ``route_or_replace``.
    """

    def __init__(self, runtime: Any) -> None:
        super().__init__(runtime)
        self._register_sovereign_replacement_schema()

    def _register_sovereign_replacement_schema(self) -> None:
        self.control.register_schema(
            "fdof.sovereign_replacement",
            1,
            {
                "required": [
                    "signal_id",
                    "status",
                    "mission_id",
                    "route_id",
                    "failure_class",
                    "recommended_component",
                    "replacement_action",
                    "lifecycle",
                    "request_sha256",
                ],
                "external_dependency_is_control_plane": False,
                "fuse_owned_replacement_required": True,
                "proof_before_promotion": True,
                "duplicate_builds_forbidden": True,
            },
        )

    @staticmethod
    def _recommended_component(failure_class: str, operation: str, target: str) -> str:
        haystack = " ".join((failure_class, operation, target)).upper()
        for markers, component in REPLACEMENT_COMPONENT_RULES:
            if any(marker in haystack for marker in markers):
                return component
        return "FUSE_NATIVE_CAPABILITY"

    @staticmethod
    def _is_fuse_owned(executor: Mapping[str, Any]) -> bool:
        provider = str(executor.get("provider") or "").strip().lower()
        ownership = str((executor.get("metadata") or {}).get("ownership") or "").strip().upper()
        return provider in FUSE_OWNED_PROVIDERS or ownership == "FUSE_OWNED"

    def _matching_fuse_owned_executors(self, request: RouteRequest) -> list[str]:
        rows = self.control.db.execute(
            "SELECT item_key,value_json FROM state WHERE namespace='fdof.executor' ORDER BY item_key"
        ).fetchall()
        matches: list[str] = []
        for row in rows:
            executor = json.loads(row["value_json"])
            if not self._is_fuse_owned(executor):
                continue
            if not set(request.required_capabilities) <= set(executor.get("capabilities") or []):
                continue
            if not self._target_matches(request.target, executor.get("target_prefixes") or ()):
                continue
            matches.append(str(executor["executor_id"]))
        return sorted(matches)

    def _replacement_action(self, request: RouteRequest) -> tuple[str, list[str]]:
        existing = self._matching_fuse_owned_executors(request)
        if existing:
            return "ACTIVATE_OR_REPAIR_EXISTING_FUSE_NATIVE", existing
        return "BUILD_MINIMUM_FUSE_NATIVE_REPLACEMENT", []

    def _persist_replacement_signal(
        self,
        request: RouteRequest,
        *,
        failure_class: str,
        source_system: str,
        evidence_ref: str = "",
        trigger_kind: str = "ROUTE_BLOCKED",
        now_epoch: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        replacement_action, existing = self._replacement_action(request)
        recommended_component = self._recommended_component(
            failure_class, request.operation, request.target
        )
        identity = {
            "mission_id": request.mission_id,
            "route_id": request.route_id,
            "transition_id": request.transition_id,
            "failure_class": failure_class,
            "source_system": source_system,
            "operation": request.operation,
            "target": request.target,
            "required_capabilities": list(request.required_capabilities),
        }
        signal_id = f"srt-{digest(identity)[:24]}"
        current = self.control.get_state("fdof.sovereign_replacement", signal_id)
        if current is not None:
            return {**current["value"], "version": int(current["version"]), "idempotent": True}

        payload = {
            "schema": "FUSE-SOVEREIGN-REPLACEMENT-SIGNAL-V1",
            "version": 1,
            "signal_id": signal_id,
            "status": "OPEN",
            "trigger_kind": trigger_kind,
            "failure_class": failure_class,
            "source_system": source_system or "UNKNOWN_EXTERNAL",
            "evidence_ref": evidence_ref,
            "mission_id": request.mission_id,
            "route_id": request.route_id,
            "transition_id": request.transition_id,
            "operation": request.operation,
            "target": request.target,
            "required_capabilities": list(request.required_capabilities),
            "authority_ceiling": request.authority_ceiling,
            "allowed_cost_classes": list(request.allowed_cost_classes),
            "require_readback": bool(request.require_readback),
            "require_rollback": bool(request.require_rollback or request.consequential),
            "recommended_component": recommended_component,
            "replacement_action": replacement_action,
            "existing_fuse_candidates": existing,
            "lifecycle": list(REPLACEMENT_LIFECYCLE),
            "external_adapter_policy": "OPTIONAL_ONLY_AFTER_FUSE_NATIVE_REPLACEMENT",
            "ownership_target": "FUSE_OWNED",
            "clean_room_reimplementation": True,
            "no_duplicate_build": True,
            "owner_private_default": True,
            "proof_before_promotion": True,
            "created_at_epoch": now_epoch,
            "request_sha256": digest(dataclasses.asdict(request)),
            "metadata": dict(metadata or {}),
        }
        version = self.control.cas_put(
            "fdof.sovereign_replacement", signal_id, payload, expected_version=0
        )
        self.control.append_event(
            request.mission_id,
            "FDOF_SOVEREIGN_REPLACEMENT_TRIGGERED",
            {
                "signal_id": signal_id,
                "route_id": request.route_id,
                "failure_class": failure_class,
                "recommended_component": recommended_component,
                "replacement_action": replacement_action,
                "existing_fuse_candidates": existing,
            },
        )
        return {**payload, "version": version, "idempotent": False}

    def record_external_constraint(
        self,
        request: RouteRequest,
        *,
        failure_class: str,
        source_system: str,
        evidence_ref: str = "",
        now_epoch: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Turn any external-provider constraint into FUSE sovereign replacement work."""
        if not failure_class:
            raise ConstraintError("REPLACEMENT_FAILURE_CLASS_REQUIRED")
        return self._persist_replacement_signal(
            request,
            failure_class=failure_class,
            source_system=source_system,
            evidence_ref=evidence_ref,
            trigger_kind="EXTERNAL_CONSTRAINT",
            now_epoch=now_epoch,
            metadata=metadata,
        )

    def route(self, request: RouteRequest, *, now_epoch: int | None = None) -> dict[str, Any]:
        try:
            return super().route(request, now_epoch=now_epoch)
        except ConstraintError as exc:
            if "NO_VERIFIED_EXECUTOR_ROUTE" in str(exc):
                self._persist_replacement_signal(
                    request,
                    failure_class=str(request.metadata.get("failure_class") or "NO_VERIFIED_EXECUTOR_ROUTE"),
                    source_system=str(request.metadata.get("source_system") or "external-provider"),
                    evidence_ref=str(request.metadata.get("evidence_ref") or ""),
                    trigger_kind="ROUTE_BLOCKED",
                    now_epoch=now_epoch,
                    metadata=request.metadata,
                )
            raise

    def route_or_replace(
        self, request: RouteRequest, *, now_epoch: int | None = None
    ) -> dict[str, Any]:
        try:
            decision = self.route(request, now_epoch=now_epoch)
            return {"state": "ROUTED", "decision": decision, "replacement": None}
        except ConstraintError as exc:
            if "NO_VERIFIED_EXECUTOR_ROUTE" not in str(exc):
                raise
            signal = self.replacement_for_route(request.route_id)
            if signal is None:
                raise ConstraintError("SOVEREIGN_REPLACEMENT_SIGNAL_MISSING") from exc
            return {
                "state": "SOVEREIGN_REPLACEMENT_TRIGGERED",
                "decision": None,
                "replacement": signal,
            }

    def replacement_for_route(self, route_id: str) -> dict[str, Any] | None:
        rows = self.control.db.execute(
            "SELECT value_json,version FROM state WHERE namespace='fdof.sovereign_replacement' ORDER BY item_key"
        ).fetchall()
        for row in rows:
            value = json.loads(row["value_json"])
            if value.get("route_id") == route_id:
                return {**value, "version": int(row["version"])}
        return None

    def open_replacements(self) -> list[dict[str, Any]]:
        rows = self.control.db.execute(
            "SELECT value_json,version FROM state WHERE namespace='fdof.sovereign_replacement' ORDER BY item_key"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            value = json.loads(row["value_json"])
            if value.get("status") == "OPEN":
                result.append({**value, "version": int(row["version"])})
        return result

    def mark_replacement_verified(
        self,
        signal_id: str,
        *,
        executor_id: str,
        proof_id: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        if not proof_id:
            raise ConstraintError("REPLACEMENT_PROOF_REQUIRED")
        current = self.control.get_state("fdof.sovereign_replacement", signal_id)
        if current is None:
            raise KeyError(signal_id)
        executor_state = self.control.get_state("fdof.executor", executor_id)
        if executor_state is None:
            raise ConstraintError("REPLACEMENT_EXECUTOR_NOT_REGISTERED")
        executor = executor_state["value"]
        if not self._is_fuse_owned(executor):
            raise ConstraintError("REPLACEMENT_EXECUTOR_MUST_BE_FUSE_OWNED")
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        if self.health_state(executor_id, now_epoch=now_epoch)["state"] != "HEALTHY":
            raise ConstraintError("REPLACEMENT_EXECUTOR_NOT_HEALTHY")
        payload = dict(current["value"])
        if payload.get("status") == "FUSE_NATIVE_REPLACEMENT_VERIFIED":
            if payload.get("replacement_executor_id") != executor_id or payload.get("proof_id") != proof_id:
                raise ConstraintError("REPLACEMENT_ALREADY_VERIFIED_DIFFERENTLY")
            return {**payload, "version": int(current["version"]), "idempotent": True}
        payload.update(
            {
                "status": "FUSE_NATIVE_REPLACEMENT_VERIFIED",
                "replacement_executor_id": executor_id,
                "proof_id": proof_id,
                "verified_at_epoch": now_epoch,
                "external_dependency_role": "OPTIONAL_ADAPTER",
                "external_control_dependency_retired": True,
            }
        )
        version = self.control.cas_put(
            "fdof.sovereign_replacement",
            signal_id,
            payload,
            expected_version=int(current["version"]),
        )
        self.control.append_event(
            payload["mission_id"],
            "FDOF_SOVEREIGN_REPLACEMENT_VERIFIED",
            {
                "signal_id": signal_id,
                "replacement_executor_id": executor_id,
                "proof_id": proof_id,
                "external_dependency_role": "OPTIONAL_ADAPTER",
            },
        )
        return {**payload, "version": version, "idempotent": False}
