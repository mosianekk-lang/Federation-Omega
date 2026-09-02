from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

try:
    from .fdof_v1 import FederationDistributedOperatingFabric
    from .sol_62_frontier_primitives import ConstraintError, FenceError, digest
except ImportError:
    from fdof_v1 import FederationDistributedOperatingFabric
    from sol_62_frontier_primitives import ConstraintError, FenceError, digest


FDOF_PROVIDER_BRIDGE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProviderExecutionRequest:
    execution_id: str
    mission_id: str
    transition_id: str
    route_id: str
    executor_id: str
    provider: str
    operation: str
    target: str
    payload: Mapping[str, Any]
    idempotency_key: str
    semantics: str = "IDEMPOTENT"
    consequential: bool = False
    expected_readback: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchReceipt:
    execution_id: str
    provider: str
    provider_request_id: str
    accepted: bool
    effect_uncertain: bool = False
    summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadbackReceipt:
    execution_id: str
    provider: str
    semantic_state: str
    verified: bool
    provider_correlation_id: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderAdapter:
    adapter_id: str
    provider: str
    dispatch: Callable[[ProviderExecutionRequest], DispatchReceipt]
    readback: Callable[[ProviderExecutionRequest, DispatchReceipt], ReadbackReceipt]
    rollback: Callable[[ProviderExecutionRequest, DispatchReceipt, ReadbackReceipt], Mapping[str, Any]] | None = None
    version: int = 1


class FederationProviderBridge:
    """Fenced provider-execution bridge for FDOF.

    The bridge deliberately keeps execution and verification separate:
    provider dispatch can only produce DISPATCH_REPORTED / EFFECT_UNKNOWN.
    VERIFIED requires an independent semantic readback receipt. It does not
    create provider authority, credentials, IAM grants, or paid resources.
    """

    def __init__(self, fdof: FederationDistributedOperatingFabric) -> None:
        self.fdof = fdof
        self.control = fdof.control
        self._adapters: dict[str, ProviderAdapter] = {}
        self._register_schema()

    def _register_schema(self) -> None:
        self.control.register_schema(
            "fdof.provider_execution",
            1,
            {
                "required": [
                    "execution_id",
                    "mission_id",
                    "transition_id",
                    "route_id",
                    "executor_id",
                    "provider",
                    "operation",
                    "target",
                    "idempotency_key",
                    "state",
                ],
                "dispatch_is_not_verification": True,
                "provider_native_readback_required_for_verified": True,
                "uncertain_effects_are_not_blindly_retried": True,
            },
        )

    def register_adapter(self, adapter: ProviderAdapter) -> None:
        if not adapter.adapter_id or not adapter.provider:
            raise ConstraintError("ADAPTER_ID_AND_PROVIDER_REQUIRED")
        if adapter.version < 1:
            raise ConstraintError("INVALID_ADAPTER_VERSION")
        existing = self._adapters.get(adapter.provider)
        if existing is not None and existing.adapter_id != adapter.adapter_id:
            raise ConstraintError("PROVIDER_ADAPTER_ALREADY_BOUND")
        self._adapters[adapter.provider] = adapter

    def _route(self, route_id: str) -> Mapping[str, Any]:
        route = self.control.get_state("fdof.route_decision", route_id)
        if route is None:
            raise ConstraintError("ROUTE_DECISION_MISSING")
        return route["value"]

    def _executor(self, executor_id: str) -> Mapping[str, Any]:
        row = self.control.get_state("fdof.executor", executor_id)
        if row is None:
            raise ConstraintError("EXECUTOR_NOT_REGISTERED")
        return row["value"]

    def _state(self, execution_id: str) -> Mapping[str, Any] | None:
        row = self.control.get_state("fdof.provider_execution", execution_id)
        return None if row is None else row["value"]

    def _put_state(self, execution_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        current = self.control.get_state("fdof.provider_execution", execution_id)
        if current is None:
            version = self.control.cas_put(
                "fdof.provider_execution", execution_id, dict(body), expected_version=0
            )
        else:
            version = self.control.cas_put(
                "fdof.provider_execution",
                execution_id,
                dict(body),
                expected_version=int(current["version"]),
            )
        return {"value": dict(body), "version": version}

    def execute(
        self,
        request: ProviderExecutionRequest,
        *,
        lease_epoch: int,
        fencing_token: int,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        route = self._route(request.route_id)
        if route["mission_id"] != request.mission_id or route["transition_id"] != request.transition_id:
            raise ConstraintError("ROUTE_MISSION_TRANSITION_MISMATCH")
        if route["executor_id"] != request.executor_id or route["provider"] != request.provider:
            raise ConstraintError("ROUTE_EXECUTOR_PROVIDER_MISMATCH")
        if route["operation"] != request.operation or route["target"] != request.target:
            raise ConstraintError("ROUTE_OPERATION_TARGET_MISMATCH")

        executor = self._executor(request.executor_id)
        if self.fdof.health_state(request.executor_id, now_epoch=now_epoch)["state"] != "HEALTHY":
            raise ConstraintError("EXECUTOR_NOT_HEALTHY_AT_DISPATCH_TIME")
        adapter = self._adapters.get(request.provider)
        if adapter is None:
            raise ConstraintError("PROVIDER_ADAPTER_NOT_REGISTERED")

        lease = self.control.db.execute(
            "SELECT * FROM leases WHERE resource_id=?", (f"transition:{request.transition_id}",)
        ).fetchone()
        if (
            not lease
            or lease["owner"] != request.executor_id
            or int(lease["epoch"]) != int(lease_epoch)
            or int(lease["fencing_token"]) != int(fencing_token)
            or int(lease["expires_at_epoch"]) <= now_epoch
        ):
            raise FenceError("STALE_FENCE")

        prior = self._state(request.execution_id)
        request_hash = digest(dataclasses.asdict(request))
        if prior is not None:
            if prior["request_sha256"] != request_hash:
                raise ConstraintError("EXECUTION_ID_REUSED_WITH_DIFFERENT_REQUEST")
            if prior["idempotency_key"] != request.idempotency_key:
                raise ConstraintError("IDEMPOTENCY_BINDING_MISMATCH")
            if prior["state"] in {"VERIFIED", "DISPATCH_REPORTED", "EFFECT_UNKNOWN"}:
                return dict(prior)

        body = {
            "execution_id": request.execution_id,
            "mission_id": request.mission_id,
            "transition_id": request.transition_id,
            "route_id": request.route_id,
            "executor_id": request.executor_id,
            "provider": request.provider,
            "operation": request.operation,
            "target": request.target,
            "idempotency_key": request.idempotency_key,
            "semantics": request.semantics,
            "request_sha256": request_hash,
            "fencing_token": int(fencing_token),
            "state": "DISPATCHING",
            "consequential": bool(request.consequential),
            "updated_at_epoch": now_epoch,
        }
        self._put_state(request.execution_id, body)

        try:
            receipt = adapter.dispatch(request)
        except Exception as exc:
            failed = {
                **body,
                "state": "EFFECT_UNKNOWN",
                "failure_class": exc.__class__.__name__,
                "updated_at_epoch": now_epoch,
            }
            self._put_state(request.execution_id, failed)
            self.control.append_event(
                request.mission_id,
                "FDOF_PROVIDER_EFFECT_UNKNOWN",
                {"execution_id": request.execution_id, "provider": request.provider},
            )
            return failed

        if receipt.execution_id != request.execution_id or receipt.provider != request.provider:
            raise ConstraintError("DISPATCH_RECEIPT_BINDING_MISMATCH")
        dispatched = {
            **body,
            "state": "EFFECT_UNKNOWN" if receipt.effect_uncertain else "DISPATCH_REPORTED",
            "provider_request_id": receipt.provider_request_id,
            "dispatch_accepted": bool(receipt.accepted),
            "dispatch_summary": dict(receipt.summary),
            "updated_at_epoch": now_epoch,
        }
        self._put_state(request.execution_id, dispatched)
        self.control.append_event(
            request.mission_id,
            "FDOF_PROVIDER_DISPATCH_REPORTED",
            {
                "execution_id": request.execution_id,
                "provider": request.provider,
                "provider_request_id": receipt.provider_request_id,
                "effect_uncertain": bool(receipt.effect_uncertain),
            },
        )
        return dispatched

    def verify(
        self,
        request: ProviderExecutionRequest,
        *,
        dispatch_receipt: DispatchReceipt,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        current = self._state(request.execution_id)
        if current is None:
            raise ConstraintError("EXECUTION_STATE_MISSING")
        if current["state"] not in {"DISPATCH_REPORTED", "EFFECT_UNKNOWN"}:
            raise ConstraintError("EXECUTION_NOT_READY_FOR_READBACK")
        adapter = self._adapters.get(request.provider)
        if adapter is None:
            raise ConstraintError("PROVIDER_ADAPTER_NOT_REGISTERED")

        readback = adapter.readback(request, dispatch_receipt)
        if readback.execution_id != request.execution_id or readback.provider != request.provider:
            raise ConstraintError("READBACK_RECEIPT_BINDING_MISMATCH")
        if not readback.verified:
            unresolved = {
                **current,
                "state": "EFFECT_UNKNOWN",
                "semantic_state": readback.semantic_state,
                "provider_correlation_id": readback.provider_correlation_id,
                "readback_evidence": dict(readback.evidence),
                "updated_at_epoch": now_epoch,
            }
            self._put_state(request.execution_id, unresolved)
            return unresolved

        verified = {
            **current,
            "state": "VERIFIED",
            "semantic_state": readback.semantic_state,
            "provider_correlation_id": readback.provider_correlation_id,
            "readback_evidence": dict(readback.evidence),
            "updated_at_epoch": now_epoch,
        }
        self._put_state(request.execution_id, verified)
        self.control.append_event(
            request.mission_id,
            "FDOF_PROVIDER_SEMANTIC_READBACK_VERIFIED",
            {
                "execution_id": request.execution_id,
                "provider": request.provider,
                "semantic_state": readback.semantic_state,
                "provider_correlation_id": readback.provider_correlation_id,
            },
        )
        return verified

    def rollback(
        self,
        request: ProviderExecutionRequest,
        *,
        dispatch_receipt: DispatchReceipt,
        readback_receipt: ReadbackReceipt,
    ) -> Mapping[str, Any]:
        adapter = self._adapters.get(request.provider)
        if adapter is None or adapter.rollback is None:
            raise ConstraintError("ROLLBACK_ADAPTER_NOT_AVAILABLE")
        if not request.consequential:
            raise ConstraintError("ROLLBACK_ONLY_FOR_CONSEQUENTIAL_EXECUTION")
        result = dict(adapter.rollback(request, dispatch_receipt, readback_receipt))
        self.control.append_event(
            request.mission_id,
            "FDOF_PROVIDER_ROLLBACK_REPORTED",
            {"execution_id": request.execution_id, "provider": request.provider},
        )
        return result
