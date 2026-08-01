from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

_OPERATION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class ConnectorError(RuntimeError):
    """Base error for the reference connector."""


class OperationConflict(ConnectorError):
    """Raised when an operation ID is reused with different input."""


class IntegrityError(ConnectorError):
    """Raised when stored bytes do not match the expected digest."""


class PathBoundaryError(ConnectorError):
    """Raised when a resource escapes the configured connector root."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConnectorRequest:
    operation_id: str
    action: str
    resource: str
    payload: Any | None = None
    expected_sha256: str | None = None

    def fingerprint(self) -> str:
        return sha256_text(
            canonical_json(
                {
                    "operation_id": self.operation_id,
                    "action": self.action,
                    "resource": self.resource,
                    "payload": self.payload,
                    "expected_sha256": self.expected_sha256,
                }
            )
        )


@dataclass(frozen=True)
class ConnectorReceipt:
    receipt_version: str
    operation_id: str
    action: str
    resource: str
    request_sha256: str
    result_sha256: str
    previous_receipt_sha256: str
    receipt_sha256: str
    state: str
    replayed: bool
    result: Any

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalRuntimeConnector:
    """A dependency-free, local JSON connector with replay-safe receipts."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._journal_path = self.root / ".connector_receipts.jsonl"

    def execute(self, request: ConnectorRequest) -> ConnectorReceipt:
        self._validate_request(request)
        request_sha = request.fingerprint()
        prior = self._receipt_for(request.operation_id)
        if prior is not None:
            if prior.request_sha256 != request_sha:
                raise OperationConflict(
                    f"operation_id {request.operation_id!r} was already used for different input"
                )
            return replace(prior, replayed=True)

        result = self._dispatch(request)
        result_sha = sha256_text(canonical_json(result))
        previous_sha = self._last_receipt_sha()
        unsigned = {
            "receipt_version": "ECTS-1.0",
            "operation_id": request.operation_id,
            "action": request.action,
            "resource": request.resource,
            "request_sha256": request_sha,
            "result_sha256": result_sha,
            "previous_receipt_sha256": previous_sha,
            "state": "COMPLETED",
            "result": result,
        }
        receipt_sha = sha256_text(canonical_json(unsigned))
        receipt = ConnectorReceipt(
            **unsigned,
            receipt_sha256=receipt_sha,
            replayed=False,
        )
        self._append_receipt(receipt)
        return receipt

    def verify_journal(self) -> bool:
        previous = "0" * 64
        for receipt in self._load_receipts():
            if receipt.previous_receipt_sha256 != previous:
                return False
            unsigned = {
                "receipt_version": receipt.receipt_version,
                "operation_id": receipt.operation_id,
                "action": receipt.action,
                "resource": receipt.resource,
                "request_sha256": receipt.request_sha256,
                "result_sha256": receipt.result_sha256,
                "previous_receipt_sha256": receipt.previous_receipt_sha256,
                "state": receipt.state,
                "result": receipt.result,
            }
            if sha256_text(canonical_json(unsigned)) != receipt.receipt_sha256:
                return False
            previous = receipt.receipt_sha256
        return True

    def _dispatch(self, request: ConnectorRequest) -> Any:
        path = self._resolve(request.resource)
        if request.action == "put_json":
            path.parent.mkdir(parents=True, exist_ok=True)
            encoded = canonical_json(request.payload) + "\n"
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(encoded, encoding="utf-8")
            os.replace(temp, path)
            return {
                "resource": request.resource,
                "content_sha256": sha256_text(encoded),
                "bytes": len(encoded.encode("utf-8")),
            }

        if request.action == "get_json":
            encoded = path.read_text(encoding="utf-8")
            actual = sha256_text(encoded)
            if request.expected_sha256 and request.expected_sha256 != actual:
                raise IntegrityError(
                    f"integrity mismatch for {request.resource}: "
                    f"expected {request.expected_sha256}, got {actual}"
                )
            return {
                "resource": request.resource,
                "content_sha256": actual,
                "value": json.loads(encoded),
            }

        if request.action == "list":
            if not path.exists():
                return {"resource": request.resource, "items": []}
            if not path.is_dir():
                raise ConnectorError(f"{request.resource!r} is not a directory")
            items = [
                item.relative_to(self.root).as_posix()
                for item in sorted(path.rglob("*"))
                if item.is_file() and item != self._journal_path
            ]
            return {"resource": request.resource, "items": items}

        raise ConnectorError(f"unsupported action: {request.action!r}")

    def _resolve(self, resource: str) -> Path:
        candidate = Path(resource)
        if candidate.is_absolute():
            raise PathBoundaryError("absolute paths are not permitted")
        resolved = (self.root / candidate).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise PathBoundaryError(f"resource escapes connector root: {resource!r}")
        return resolved

    def _validate_request(self, request: ConnectorRequest) -> None:
        if not _OPERATION_ID.fullmatch(request.operation_id):
            raise ConnectorError("operation_id must be 8-128 safe characters")
        if request.action not in {"put_json", "get_json", "list"}:
            raise ConnectorError(f"unsupported action: {request.action!r}")
        if request.action == "put_json" and request.payload is None:
            raise ConnectorError("put_json requires a payload")

    def _load_receipts(self) -> list[ConnectorReceipt]:
        if not self._journal_path.exists():
            return []
        receipts: list[ConnectorReceipt] = []
        for line in self._journal_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                receipts.append(ConnectorReceipt(**json.loads(line)))
        return receipts

    def _receipt_for(self, operation_id: str) -> ConnectorReceipt | None:
        for receipt in self._load_receipts():
            if receipt.operation_id == operation_id:
                return receipt
        return None

    def _last_receipt_sha(self) -> str:
        receipts = self._load_receipts()
        return receipts[-1].receipt_sha256 if receipts else "0" * 64

    def _append_receipt(self, receipt: ConnectorReceipt) -> None:
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(receipt.as_dict()) + "\n")
