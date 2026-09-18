from __future__ import annotations

"""FDOF capability-activation receipt for FRCB v5.

This receipt represents a verified FDOF route plus a live SOL 6.2 transition
fence. It proves capability callability/control-plane activation only.

It does not prove provider dispatch, provider effect, provider semantic readback,
provider authority, or F130 terminal completion.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

SCHEMA = "FUSE-FDOF-CAPABILITY-ACTIVATION-RECEIPT-V1"
VERSION = "1.0.0"
PRODUCER_ID = "FDOF-V1+SOL62"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY_ORDER = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_BOUNDED_PROVIDER": 2,
    "A3_CONSEQUENTIAL": 3,
}


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FDOFCapabilityActivationReceipt:
    schema: str
    version: str
    producer_id: str
    mission_id: str
    route_id: str
    transition_id: str
    operation: str
    target: str
    required_capabilities: tuple[str, ...]
    request_authority_ceiling: str
    executor_id: str
    executor_provider: str
    executor_authority_ceiling: str
    route_score: int
    route_version: int
    request_sha256: str
    health_observation_id: str
    health_observed_at_epoch: int
    health_ttl_seconds: int
    health_proof_id: str
    health_evidence_class: str
    lease_resource_id: str
    lease_epoch: int
    fencing_token: int
    lease_expires_at_epoch: int
    issued_at_epoch: int
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
            "operation": self.operation,
            "target": self.target,
            "required_capabilities": list(self.required_capabilities),
            "request_authority_ceiling": self.request_authority_ceiling,
            "executor_id": self.executor_id,
            "executor_provider": self.executor_provider,
            "executor_authority_ceiling": self.executor_authority_ceiling,
            "route_score": self.route_score,
            "route_version": self.route_version,
            "request_sha256": self.request_sha256,
            "health_observation_id": self.health_observation_id,
            "health_observed_at_epoch": self.health_observed_at_epoch,
            "health_ttl_seconds": self.health_ttl_seconds,
            "health_proof_id": self.health_proof_id,
            "health_evidence_class": self.health_evidence_class,
            "lease_resource_id": self.lease_resource_id,
            "lease_epoch": self.lease_epoch,
            "fencing_token": self.fencing_token,
            "lease_expires_at_epoch": self.lease_expires_at_epoch,
            "issued_at_epoch": self.issued_at_epoch,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self, *, now_epoch: int) -> bool:
        boundary = dict(self.truth_boundary)
        request_rank = _AUTHORITY_ORDER.get(self.request_authority_ceiling, -1)
        executor_rank = _AUTHORITY_ORDER.get(self.executor_authority_ceiling, -1)
        health_age = int(self.issued_at_epoch) - int(self.health_observed_at_epoch)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.producer_id == PRODUCER_ID
            and self.mission_id.strip()
            and self.route_id.strip()
            and self.transition_id.strip()
            and self.operation.strip()
            and self.target.strip()
            and self.required_capabilities
            and len(self.required_capabilities) == len(set(self.required_capabilities))
            and request_rank >= 0
            and executor_rank >= request_rank
            and self.executor_id.strip()
            and self.executor_provider.strip()
            and self.route_score >= 0
            and self.route_version >= 1
            and bool(_HEX64.fullmatch(self.request_sha256))
            and self.health_observation_id.strip()
            and self.health_ttl_seconds >= 1
            and 0 <= health_age <= self.health_ttl_seconds
            and self.health_proof_id.strip()
            and self.health_evidence_class.strip()
            and self.lease_resource_id == f"transition:{self.transition_id}"
            and self.lease_epoch >= 1
            and self.fencing_token >= 1
            and self.issued_at_epoch < self.lease_expires_at_epoch
            and int(now_epoch) < self.lease_expires_at_epoch
            and boundary.get("fdof_route_selected") is True
            and boundary.get("fresh_healthy_executor_verified") is True
            and boundary.get("transition_fence_active") is True
            and boundary.get("sol62_event_chain_verified") is True
            and boundary.get("provider_dispatch_verified") is False
            and boundary.get("provider_effect_verified") is False
            and boundary.get("provider_semantic_readback_verified") is False
            and boundary.get("provider_authority_created") is False
            and boundary.get("external_effect_created") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


def build_fdof_activation_receipt(
    *,
    request: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    executor: Mapping[str, Any],
    health_observation: Mapping[str, Any],
    lease: Mapping[str, Any],
    fdof_status: Mapping[str, Any],
    issued_at_epoch: int,
) -> FDOFCapabilityActivationReceipt:
    mission_id = str(request.get("mission_id") or "")
    route_id = str(request.get("route_id") or "")
    transition_id = str(request.get("transition_id") or "")
    if route_decision.get("mission_id") != mission_id:
        raise ValueError("FDOF_ACTIVATION_ROUTE_MISSION_MISMATCH")
    if route_decision.get("route_id") != route_id:
        raise ValueError("FDOF_ACTIVATION_ROUTE_ID_MISMATCH")
    if route_decision.get("transition_id") != transition_id:
        raise ValueError("FDOF_ACTIVATION_TRANSITION_MISMATCH")
    if route_decision.get("operation") != request.get("operation"):
        raise ValueError("FDOF_ACTIVATION_OPERATION_MISMATCH")
    if route_decision.get("target") != request.get("target"):
        raise ValueError("FDOF_ACTIVATION_TARGET_MISMATCH")
    if route_decision.get("executor_id") != executor.get("executor_id"):
        raise ValueError("FDOF_ACTIVATION_EXECUTOR_MISMATCH")
    if route_decision.get("provider") != executor.get("provider"):
        raise ValueError("FDOF_ACTIVATION_PROVIDER_MISMATCH")
    if route_decision.get("health_state") != "HEALTHY":
        raise ValueError("FDOF_ACTIVATION_HEALTH_NOT_VERIFIED")
    if str(health_observation.get("executor_id") or "") != str(executor.get("executor_id") or ""):
        raise ValueError("FDOF_ACTIVATION_HEALTH_EXECUTOR_MISMATCH")
    if not str(health_observation.get("proof_id") or ""):
        raise ValueError("FDOF_ACTIVATION_HEALTH_PROOF_REQUIRED")
    if lease.get("resource_id") != f"transition:{transition_id}":
        raise ValueError("FDOF_ACTIVATION_LEASE_TRANSITION_MISMATCH")
    if lease.get("owner") != executor.get("executor_id"):
        raise ValueError("FDOF_ACTIVATION_LEASE_OWNER_MISMATCH")
    integrity = fdof_status.get("sol62_integrity")
    if not isinstance(integrity, Mapping) or integrity.get("event_chain_valid") is not True:
        raise ValueError("FDOF_ACTIVATION_SOL62_CHAIN_NOT_VERIFIED")

    required_capabilities = tuple(str(x) for x in request.get("required_capabilities", ()))
    boundary = MappingProxyType({
        "fdof_route_selected": True,
        "fresh_healthy_executor_verified": True,
        "transition_fence_active": True,
        "sol62_event_chain_verified": True,
        "provider_dispatch_verified": False,
        "provider_effect_verified": False,
        "provider_semantic_readback_verified": False,
        "provider_authority_created": False,
        "external_effect_created": False,
    })
    material = {
        "schema": SCHEMA,
        "version": VERSION,
        "producer_id": PRODUCER_ID,
        "mission_id": mission_id,
        "route_id": route_id,
        "transition_id": transition_id,
        "operation": str(request.get("operation") or ""),
        "target": str(request.get("target") or ""),
        "required_capabilities": list(required_capabilities),
        "request_authority_ceiling": str(request.get("authority_ceiling") or ""),
        "executor_id": str(executor.get("executor_id") or ""),
        "executor_provider": str(executor.get("provider") or ""),
        "executor_authority_ceiling": str(executor.get("authority_ceiling") or ""),
        "route_score": int(route_decision.get("score") or 0),
        "route_version": int(route_decision.get("version") or 0),
        "request_sha256": str(route_decision.get("request_sha256") or ""),
        "health_observation_id": str(health_observation.get("observation_id") or ""),
        "health_observed_at_epoch": int(health_observation.get("observed_at_epoch") or 0),
        "health_ttl_seconds": int(health_observation.get("ttl_seconds") or 0),
        "health_proof_id": str(health_observation.get("proof_id") or ""),
        "health_evidence_class": str(health_observation.get("evidence_class") or ""),
        "lease_resource_id": str(lease.get("resource_id") or ""),
        "lease_epoch": int(lease.get("epoch") or 0),
        "fencing_token": int(lease.get("fencing_token") or 0),
        "lease_expires_at_epoch": int(lease.get("expires_at_epoch") or 0),
        "issued_at_epoch": int(issued_at_epoch),
        "truth_boundary": dict(boundary),
    }
    receipt = FDOFCapabilityActivationReceipt(
        schema=SCHEMA,
        version=VERSION,
        producer_id=PRODUCER_ID,
        mission_id=mission_id,
        route_id=route_id,
        transition_id=transition_id,
        operation=str(request.get("operation") or ""),
        target=str(request.get("target") or ""),
        required_capabilities=required_capabilities,
        request_authority_ceiling=str(request.get("authority_ceiling") or ""),
        executor_id=str(executor.get("executor_id") or ""),
        executor_provider=str(executor.get("provider") or ""),
        executor_authority_ceiling=str(executor.get("authority_ceiling") or ""),
        route_score=int(route_decision.get("score") or 0),
        route_version=int(route_decision.get("version") or 0),
        request_sha256=str(route_decision.get("request_sha256") or ""),
        health_observation_id=str(health_observation.get("observation_id") or ""),
        health_observed_at_epoch=int(health_observation.get("observed_at_epoch") or 0),
        health_ttl_seconds=int(health_observation.get("ttl_seconds") or 0),
        health_proof_id=str(health_observation.get("proof_id") or ""),
        health_evidence_class=str(health_observation.get("evidence_class") or ""),
        lease_resource_id=str(lease.get("resource_id") or ""),
        lease_epoch=int(lease.get("epoch") or 0),
        fencing_token=int(lease.get("fencing_token") or 0),
        lease_expires_at_epoch=int(lease.get("expires_at_epoch") or 0),
        issued_at_epoch=int(issued_at_epoch),
        receipt_digest=_digest(material),
        truth_boundary=boundary,
    )
    if not receipt.verify(now_epoch=int(issued_at_epoch)):
        raise ValueError("FDOF_ACTIVATION_RECEIPT_SELF_VERIFICATION_FAILED")
    return receipt


class FDOFCapabilityActivationBinder:
    def bind(
        self,
        *,
        mission_id: str,
        receipt: FDOFCapabilityActivationReceipt,
        now_epoch: int,
        expected_target: str = "",
    ) -> FDOFCapabilityActivationReceipt:
        if not receipt.verify(now_epoch=int(now_epoch)):
            raise ValueError("FDOF_CAPABILITY_ACTIVATION_RECEIPT_INVALID_OR_STALE")
        if receipt.mission_id != mission_id:
            raise ValueError("FDOF_CAPABILITY_ACTIVATION_MISSION_MISMATCH")
        if expected_target and receipt.target != expected_target:
            raise ValueError("FDOF_CAPABILITY_ACTIVATION_TARGET_MISMATCH")
        return receipt


__all__ = [
    "FDOFCapabilityActivationBinder",
    "FDOFCapabilityActivationReceipt",
    "PRODUCER_ID",
    "SCHEMA",
    "VERSION",
    "build_fdof_activation_receipt",
]
