from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    operation: str
    execute: bool
    readback: bool
    rollback: bool
    authority_state: str
    owner_reserved: bool = False


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    provider: str
    operation: str
    payload: dict[str, Any]
    idempotency_key: str
    expected_readback: dict[str, Any] = field(default_factory=dict)
    consequential: bool = False
    owner_authorised: bool = False


@dataclass
class ProviderReceipt:
    request_id: str
    provider: str
    operation: str
    status: str
    execution_ref: str
    readback: dict[str, Any]
    rollback_ref: str | None
    idempotency_key: str
    sha256: str = ""


class ProviderAdapter:
    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        raise NotImplementedError

    def readback(self, execution_ref: str) -> dict[str, Any]:
        raise NotImplementedError

    def rollback(self, execution_ref: str) -> dict[str, Any]:
        raise NotImplementedError


class InMemoryAdapter(ProviderAdapter):
    """Deterministic reference adapter used only for provider-neutral proof."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        ref = f"exec-{len(self.store)+1:06d}"
        self.store[ref] = {"payload": request.payload, "active": True}
        return {"execution_ref": ref}

    def readback(self, execution_ref: str) -> dict[str, Any]:
        return dict(self.store[execution_ref])

    def rollback(self, execution_ref: str) -> dict[str, Any]:
        self.store[execution_ref]["active"] = False
        return {"rolled_back": True, "execution_ref": execution_ref}


class ProviderExecutionBridge:
    """Fail-closed execution bridge with receipt, readback and rollback controls."""

    def __init__(self) -> None:
        self.capabilities: dict[str, ProviderCapability] = {}
        self.adapters: dict[str, ProviderAdapter] = {}
        self.receipts_by_idempotency: dict[str, ProviderReceipt] = {}

    def register_capability(self, capability: ProviderCapability) -> None:
        self.capabilities[f"{capability.provider}:{capability.operation}"] = capability

    def register_adapter(self, provider: str, adapter: ProviderAdapter) -> None:
        self.adapters[provider] = adapter

    def admit(self, request: ExecutionRequest) -> dict[str, Any]:
        capability = self.capabilities.get(f"{request.provider}:{request.operation}")
        if capability is None:
            return {"admitted": False, "state": "PROVIDER_BLOCKED", "reason": "CAPABILITY_NOT_REGISTERED"}
        if capability.authority_state != "VERIFIED":
            return {"admitted": False, "state": capability.authority_state, "reason": "AUTHORITY_NOT_VERIFIED"}
        if capability.owner_reserved and not request.owner_authorised:
            return {"admitted": False, "state": "OWNER_AUTHORITY_REQUIRED", "reason": "OWNER_RESERVED_OPERATION"}
        if request.consequential and not capability.rollback:
            return {"admitted": False, "state": "OWNER_APPROVAL_REQUIRED", "reason": "ROLLBACK_NOT_AVAILABLE"}
        if not capability.execute:
            return {"admitted": False, "state": "READ_ONLY", "reason": "EXECUTION_NOT_SUPPORTED"}
        if not capability.readback:
            return {"admitted": False, "state": "PROVIDER_BLOCKED", "reason": "READBACK_REQUIRED"}
        if request.provider not in self.adapters:
            return {"admitted": False, "state": "PROVIDER_BLOCKED", "reason": "ADAPTER_NOT_REGISTERED"}
        return {"admitted": True, "state": "ADMITTED"}

    def execute(self, request: ExecutionRequest) -> ProviderReceipt:
        existing = self.receipts_by_idempotency.get(request.idempotency_key)
        if existing is not None:
            return existing
        admission = self.admit(request)
        if not admission["admitted"]:
            raise RuntimeError(admission["state"])
        adapter = self.adapters[request.provider]
        execution_ref = str(adapter.execute(request)["execution_ref"])
        readback = adapter.readback(execution_ref)
        mismatches = {
            key: {"expected": expected, "actual": readback.get(key)}
            for key, expected in request.expected_readback.items()
            if readback.get(key) != expected
        }
        if mismatches:
            capability = self.capabilities[f"{request.provider}:{request.operation}"]
            if capability.rollback:
                adapter.rollback(execution_ref)
            raise RuntimeError(f"READBACK_MISMATCH:{json.dumps(mismatches, sort_keys=True)}")
        capability = self.capabilities[f"{request.provider}:{request.operation}"]
        receipt = ProviderReceipt(
            request_id=request.request_id,
            provider=request.provider,
            operation=request.operation,
            status="VERIFIED_EXECUTED",
            execution_ref=execution_ref,
            readback=readback,
            rollback_ref=execution_ref if capability.rollback else None,
            idempotency_key=request.idempotency_key,
        )
        receipt.sha256 = digest(asdict(receipt) | {"sha256": ""})
        self.receipts_by_idempotency[request.idempotency_key] = receipt
        return receipt

    def rollback(self, receipt: ProviderReceipt, *, owner_authorised: bool = False) -> dict[str, Any]:
        capability = self.capabilities[f"{receipt.provider}:{receipt.operation}"]
        if not capability.rollback:
            raise RuntimeError("ROLLBACK_NOT_AVAILABLE")
        if capability.owner_reserved and not owner_authorised:
            raise RuntimeError("OWNER_AUTHORITY_REQUIRED")
        result = self.adapters[receipt.provider].rollback(receipt.execution_ref)
        return {"status": "ROLLED_BACK", "result": result, "readback": self.adapters[receipt.provider].readback(receipt.execution_ref)}
