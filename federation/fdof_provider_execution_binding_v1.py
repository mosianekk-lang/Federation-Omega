from __future__ import annotations

"""Authority-bound provider execution/readback receipt for FRCB v6.

This module does not dispatch providers. It validates the durable result emitted by
the existing FDOF provider bridge against the exact V5 capability-activation
receipt and emits a deterministic convergence receipt.

The receipt proves provider dispatch + provider-native semantic readback for one
exact mission/route/transition/executor/provider/operation/target/request. It does
not grant provider authority and it does not prove F130 terminal completion.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from federation.fdof_capability_activation_binding_v1 import (
    FDOFCapabilityActivationReceipt,
)

SCHEMA = "FUSE-FDOF-PROVIDER-EXECUTION-READBACK-RECEIPT-V1"
VERSION = "1.0.0"
PRODUCER_ID = "FDOF-PROVIDER-BRIDGE-V1.1"


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FDOFProviderExecutionReceipt:
    schema: str
    version: str
    producer_id: str
    mission_id: str
    route_id: str
    transition_id: str
    execution_id: str
    executor_id: str
    provider: str
    operation: str
    target: str
    activation_receipt_digest: str
    activation_lease_epoch: int
    activation_fencing_token: int
    activation_issued_at_epoch: int
    activation_lease_expires_at_epoch: int
    request_sha256: str
    idempotency_key: str
    provider_request_id: str
    semantic_state: str
    provider_correlation_id: str
    readback_evidence_sha256: str
    verified_at_epoch: int
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "producer_id": self.producer_id,
            "mission_id": self.mission_id,
            "route_id": self.route_id,
            "transition_id": self.transition_id,
            "execution_id": self.execution_id,
            "executor_id": self.executor_id,
            "provider": self.provider,
            "operation": self.operation,
            "target": self.target,
            "activation_receipt_digest": self.activation_receipt_digest,
            "activation_lease_epoch": self.activation_lease_epoch,
            "activation_fencing_token": self.activation_fencing_token,
            "activation_issued_at_epoch": self.activation_issued_at_epoch,
            "activation_lease_expires_at_epoch": self.activation_lease_expires_at_epoch,
            "request_sha256": self.request_sha256,
            "idempotency_key": self.idempotency_key,
            "provider_request_id": self.provider_request_id,
            "semantic_state": self.semantic_state,
            "provider_correlation_id": self.provider_correlation_id,
            "readback_evidence_sha256": self.readback_evidence_sha256,
            "verified_at_epoch": self.verified_at_epoch,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.producer_id == PRODUCER_ID
            and self.mission_id.strip()
            and self.route_id.strip()
            and self.transition_id.strip()
            and self.execution_id.strip()
            and self.executor_id.strip()
            and self.provider.strip()
            and self.operation.strip()
            and self.target.strip()
            and self.activation_receipt_digest.startswith("sha256:")
            and self.activation_lease_epoch >= 1
            and self.activation_fencing_token >= 1
            and self.activation_issued_at_epoch <= self.verified_at_epoch
            and self.verified_at_epoch < self.activation_lease_expires_at_epoch
            and len(self.request_sha256) == 64
            and self.idempotency_key.strip()
            and self.provider_request_id.strip()
            and self.semantic_state.strip()
            and self.provider_correlation_id.strip()
            and self.readback_evidence_sha256.startswith("sha256:")
            and boundary.get("dispatch_accepted") is True
            and boundary.get("provider_execution_verified") is True
            and boundary.get("provider_native_readback_verified") is True
            and boundary.get("expected_semantic_state_verified") is True
            and boundary.get("provider_correlation_verified") is True
            and boundary.get("fdof_event_chain_verified") is True
            and boundary.get("provider_authority_created") is False
            and boundary.get("f130_terminal_completion_verified") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


def build_fdof_provider_execution_receipt(
    *,
    activation: FDOFCapabilityActivationReceipt,
    execution_state: Mapping[str, Any],
    fdof_status: Mapping[str, Any],
    verified_at_epoch: int,
) -> FDOFProviderExecutionReceipt:
    if not activation.verify(now_epoch=int(verified_at_epoch)):
        raise ValueError("FDOF_PROVIDER_EXECUTION_ACTIVATION_INVALID_OR_STALE")

    expected = {
        "mission_id": activation.mission_id,
        "route_id": activation.route_id,
        "transition_id": activation.transition_id,
        "executor_id": activation.executor_id,
        "provider": activation.executor_provider,
        "operation": activation.operation,
        "target": activation.target,
        "fencing_token": activation.fencing_token,
    }
    for field, value in expected.items():
        if execution_state.get(field) != value:
            raise ValueError(
                f"FDOF_PROVIDER_EXECUTION_{field.upper()}_MISMATCH:"
                f"{execution_state.get(field)}!={value}"
            )

    if execution_state.get("state") != "VERIFIED":
        raise ValueError("FDOF_PROVIDER_EXECUTION_NOT_VERIFIED")
    if execution_state.get("dispatch_accepted") is not True:
        raise ValueError("FDOF_PROVIDER_DISPATCH_NOT_ACCEPTED")
    if execution_state.get("readback_provider_native") is not True:
        raise ValueError("FDOF_PROVIDER_NATIVE_READBACK_REQUIRED")
    if execution_state.get("readback_expected_match") is not True:
        raise ValueError("FDOF_EXPECTED_SEMANTIC_STATE_MISMATCH")
    if execution_state.get("readback_correlation_present") is not True:
        raise ValueError("FDOF_PROVIDER_CORRELATION_REQUIRED")

    provider_request_id = str(execution_state.get("provider_request_id") or "").strip()
    correlation_id = str(execution_state.get("provider_correlation_id") or "").strip()
    semantic_state = str(execution_state.get("semantic_state") or "").strip()
    request_sha256 = str(execution_state.get("request_sha256") or "").strip()
    idempotency_key = str(execution_state.get("idempotency_key") or "").strip()
    execution_id = str(execution_state.get("execution_id") or "").strip()
    if not all(
        (
            provider_request_id,
            correlation_id,
            semantic_state,
            request_sha256,
            idempotency_key,
            execution_id,
        )
    ):
        raise ValueError("FDOF_PROVIDER_EXECUTION_IDENTITY_OR_READBACK_MISSING")

    integrity = fdof_status.get("sol62_integrity")
    if not isinstance(integrity, Mapping) or integrity.get("event_chain_valid") is not True:
        raise ValueError("FDOF_PROVIDER_EXECUTION_EVENT_CHAIN_NOT_VERIFIED")

    readback_evidence = execution_state.get("readback_evidence")
    if not isinstance(readback_evidence, Mapping):
        raise ValueError("FDOF_PROVIDER_READBACK_EVIDENCE_REQUIRED")

    boundary = MappingProxyType({
        "dispatch_accepted": True,
        "provider_execution_verified": True,
        "provider_native_readback_verified": True,
        "expected_semantic_state_verified": True,
        "provider_correlation_verified": True,
        "fdof_event_chain_verified": True,
        "provider_authority_created": False,
        "f130_terminal_completion_verified": False,
    })
    material = {
        "schema": SCHEMA,
        "version": VERSION,
        "producer_id": PRODUCER_ID,
        "mission_id": activation.mission_id,
        "route_id": activation.route_id,
        "transition_id": activation.transition_id,
        "execution_id": execution_id,
        "executor_id": activation.executor_id,
        "provider": activation.executor_provider,
        "operation": activation.operation,
        "target": activation.target,
        "activation_receipt_digest": activation.receipt_digest,
        "activation_lease_epoch": activation.lease_epoch,
        "activation_fencing_token": activation.fencing_token,
        "activation_issued_at_epoch": activation.issued_at_epoch,
        "activation_lease_expires_at_epoch": activation.lease_expires_at_epoch,
        "request_sha256": request_sha256,
        "idempotency_key": idempotency_key,
        "provider_request_id": provider_request_id,
        "semantic_state": semantic_state,
        "provider_correlation_id": correlation_id,
        "readback_evidence_sha256": _digest(dict(readback_evidence)),
        "verified_at_epoch": int(verified_at_epoch),
        "truth_boundary": dict(boundary),
    }
    receipt = FDOFProviderExecutionReceipt(
        schema=SCHEMA,
        version=VERSION,
        producer_id=PRODUCER_ID,
        mission_id=activation.mission_id,
        route_id=activation.route_id,
        transition_id=activation.transition_id,
        execution_id=execution_id,
        executor_id=activation.executor_id,
        provider=activation.executor_provider,
        operation=activation.operation,
        target=activation.target,
        activation_receipt_digest=activation.receipt_digest,
        activation_lease_epoch=activation.lease_epoch,
        activation_fencing_token=activation.fencing_token,
        activation_issued_at_epoch=activation.issued_at_epoch,
        activation_lease_expires_at_epoch=activation.lease_expires_at_epoch,
        request_sha256=request_sha256,
        idempotency_key=idempotency_key,
        provider_request_id=provider_request_id,
        semantic_state=semantic_state,
        provider_correlation_id=correlation_id,
        readback_evidence_sha256=_digest(dict(readback_evidence)),
        verified_at_epoch=int(verified_at_epoch),
        receipt_digest=_digest(material),
        truth_boundary=boundary,
    )
    if not receipt.verify():
        raise ValueError("FDOF_PROVIDER_EXECUTION_RECEIPT_SELF_VERIFICATION_FAILED")
    return receipt


class FDOFProviderExecutionBinder:
    def bind(
        self,
        *,
        mission_id: str,
        activation: FDOFCapabilityActivationReceipt,
        receipt: FDOFProviderExecutionReceipt,
    ) -> FDOFProviderExecutionReceipt:
        if not receipt.verify():
            raise ValueError("FDOF_PROVIDER_EXECUTION_RECEIPT_INVALID")
        if receipt.mission_id != mission_id:
            raise ValueError("FDOF_PROVIDER_EXECUTION_MISSION_MISMATCH")
        if receipt.activation_receipt_digest != activation.receipt_digest:
            raise ValueError("FDOF_PROVIDER_EXECUTION_ACTIVATION_RECEIPT_MISMATCH")

        expected = (
            ("route_id", activation.route_id),
            ("transition_id", activation.transition_id),
            ("executor_id", activation.executor_id),
            ("provider", activation.executor_provider),
            ("operation", activation.operation),
            ("target", activation.target),
            ("activation_lease_epoch", activation.lease_epoch),
            ("activation_fencing_token", activation.fencing_token),
        )
        for field, value in expected:
            if getattr(receipt, field) != value:
                raise ValueError(f"FDOF_PROVIDER_EXECUTION_{field.upper()}_MISMATCH")
        return receipt


__all__ = [
    "FDOFProviderExecutionBinder",
    "FDOFProviderExecutionReceipt",
    "PRODUCER_ID",
    "SCHEMA",
    "VERSION",
    "build_fdof_provider_execution_receipt",
]
