"""Provider interfaces and deterministic in-memory adapters for v3 testing."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
from typing import Any, Mapping, Protocol
import uuid

from .canonical import canonical_json_bytes, sha256_bytes
from .model import (
    PermanentProviderError,
    ProjectionReadback,
    ProviderObject,
    ProviderReadback,
    SignatureEnvelope,
    TemporaryProviderError,
)


class StorageAdapter(Protocol):
    def put_if_absent(
        self,
        *,
        content_key: str,
        destination_alias: str,
        object_name: str,
        content: bytes,
        media_type: str,
    ) -> ProviderObject: ...

    def readback(self, object_id: str) -> ProviderReadback: ...

    def delete_if_created(self, object_id: str) -> bool: ...


class RegistryProjection(Protocol):
    def commit(self, transaction: Mapping[str, Any], receipt: Mapping[str, Any]) -> None: ...

    def readback(self, transaction_id: str) -> ProjectionReadback: ...

    def repair(self, transaction: Mapping[str, Any], receipt: Mapping[str, Any]) -> None: ...


class ReceiptSigner(Protocol):
    signer_id: str
    key_reference: str

    def sign(self, payload: Mapping[str, Any]) -> SignatureEnvelope: ...

    def verify(self, payload: Mapping[str, Any], envelope: SignatureEnvelope) -> bool: ...


class InMemoryStorage:
    """Content-addressed private storage simulator.

    It deliberately exposes counters and fault injection so crash recovery,
    idempotency and drift handling can be tested without claiming provider use.
    """

    def __init__(self) -> None:
        self.by_key: dict[str, ProviderObject] = {}
        self.bytes_by_id: dict[str, bytes] = {}
        self.readback_overrides: dict[str, dict[str, Any]] = {}
        self.put_calls = 0
        self.delete_calls = 0
        self.fail_put_times = 0
        self.fail_read_times = 0

    def put_if_absent(
        self,
        *,
        content_key: str,
        destination_alias: str,
        object_name: str,
        content: bytes,
        media_type: str,
    ) -> ProviderObject:
        self.put_calls += 1
        if self.fail_put_times > 0:
            self.fail_put_times -= 1
            raise TemporaryProviderError("injected storage write outage")
        if content_key in self.by_key:
            existing = self.by_key[content_key]
            return ProviderObject(**{**asdict(existing), "created_new": False})
        object_id = f"MEM-{uuid.uuid4()}"
        value = ProviderObject(
            object_id=object_id,
            object_name=object_name,
            parent_ref=destination_alias,
            media_type=media_type,
            size_bytes=len(content),
            sha256=sha256_bytes(content),
            url=f"memory://{object_id}",
            revision="1",
            created_new=True,
        )
        self.by_key[content_key] = value
        self.bytes_by_id[object_id] = bytes(content)
        return value

    def readback(self, object_id: str) -> ProviderReadback:
        if self.fail_read_times > 0:
            self.fail_read_times -= 1
            raise TemporaryProviderError("injected storage readback outage")
        if object_id not in self.bytes_by_id:
            raise PermanentProviderError("provider object not found")
        original = next(value for value in self.by_key.values() if value.object_id == object_id)
        override = self.readback_overrides.get(object_id, {})
        return ProviderReadback(
            object_id=object_id,
            object_name=str(override.get("object_name", original.object_name)),
            parent_ref=str(override.get("parent_ref", original.parent_ref)),
            media_type=str(override.get("media_type", original.media_type)),
            size_bytes=int(override.get("size_bytes", original.size_bytes)),
            sha256=str(override.get("sha256", sha256_bytes(self.bytes_by_id[object_id]))),
            shared=bool(override.get("shared", False)),
            revision=str(override.get("revision", original.revision)),
            trashed=bool(override.get("trashed", False)),
        )

    def delete_if_created(self, object_id: str) -> bool:
        self.delete_calls += 1
        target_key = next(
            (key for key, value in self.by_key.items() if value.object_id == object_id), None
        )
        if target_key is None:
            return False
        self.by_key.pop(target_key, None)
        self.bytes_by_id.pop(object_id, None)
        self.readback_overrides.pop(object_id, None)
        return True


class InMemoryProjection:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.commit_calls = 0
        self.fail_commit_times = 0
        self.fail_read_times = 0

    def commit(self, transaction: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
        self.commit_calls += 1
        if self.fail_commit_times > 0:
            self.fail_commit_times -= 1
            raise TemporaryProviderError("injected registry projection outage")
        transaction_id = str(transaction["transaction_id"])
        object_id = str((transaction.get("provider_object") or {}).get("object_id", ""))
        self.rows[transaction_id] = {
            "transaction_id": transaction_id,
            "idempotency_key": str(transaction["idempotency_key"]),
            "object_id": object_id,
            "sha256": str(transaction["content_sha256"]),
            "status": "COMMITTED",
            "receipt": dict(receipt),
        }

    def readback(self, transaction_id: str) -> ProjectionReadback:
        if self.fail_read_times > 0:
            self.fail_read_times -= 1
            raise TemporaryProviderError("injected registry readback outage")
        row = self.rows.get(transaction_id)
        if not row:
            raise PermanentProviderError("registry projection row missing")
        return ProjectionReadback(
            transaction_id=str(row["transaction_id"]),
            idempotency_key=str(row["idempotency_key"]),
            object_id=str(row["object_id"]),
            sha256=str(row["sha256"]),
            status=str(row["status"]),
        )

    def repair(self, transaction: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
        self.commit(transaction, receipt)


class HMACReceiptSigner:
    """Deterministic test signer.

    Production policy requires a private external signer or KMS-backed asymmetric
    identity. This implementation exists for local/adversarial proof only and
    must never be treated as production signer authority.
    """

    algorithm = "HMAC-SHA256-TEST-ONLY"

    def __init__(self, key: bytes, *, signer_id: str = "LOCAL-TEST-SIGNER") -> None:
        if len(key) < 32:
            raise ValueError("test signer key must be at least 32 bytes")
        self._key = bytes(key)
        self.signer_id = signer_id
        self.key_reference = "TEST-ONLY-IN-MEMORY"

    def sign(self, payload: Mapping[str, Any]) -> SignatureEnvelope:
        encoded = canonical_json_bytes(payload)
        signature = hmac.new(self._key, encoded, hashlib.sha256).hexdigest()
        return SignatureEnvelope(
            algorithm=self.algorithm,
            signer_id=self.signer_id,
            key_reference=self.key_reference,
            signature=signature,
            signed_payload_sha256=sha256_bytes(encoded),
        )

    def verify(self, payload: Mapping[str, Any], envelope: SignatureEnvelope) -> bool:
        if envelope.algorithm != self.algorithm or envelope.signer_id != self.signer_id:
            return False
        expected = self.sign(payload)
        return hmac.compare_digest(expected.signature, envelope.signature) and hmac.compare_digest(
            expected.signed_payload_sha256, envelope.signed_payload_sha256
        )
