from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import secrets
import threading
from typing import Any, Mapping


TASK_SCHEMA = "FEDERATION-WINDOWS-TASK-V1"
RECEIPT_SCHEMA = "FEDERATION-WINDOWS-RECEIPT-V1"
RELAY_ENROLLMENT_SCHEMA = "FUSE-WINDOWS-RELAY-ENROLLMENT-V1"
RELAY_LEASE_SCHEMA = "FUSE-WINDOWS-RELAY-LEASE-V1"
ALLOWED_TASKS = frozenset({"health", "inventory", "hash_workspace_file"})
ALLOWED_EFFECT = "READ_ONLY"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _token(num_bytes: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(num_bytes)).decode("ascii").rstrip("=")


def _require_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f"{label}_INVALID")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    if value[0] not in allowed or any(ch not in allowed for ch in value):
        raise ValueError(f"{label}_INVALID")
    return value


def _parse_utc_z(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label}_MUST_BE_UTC_Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except Exception as exc:
        raise ValueError(f"{label}_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label}_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def validate_task_mapping(task: Mapping[str, Any], *, now: datetime | None = None) -> None:
    if not isinstance(task, Mapping):
        raise ValueError("TASK_OBJECT_REQUIRED")
    expected = {
        "schema", "task_id", "correlation_id", "issued_by", "task_type",
        "issued_at", "expires_at", "parameters", "effect",
    }
    unknown = sorted(set(task) - expected)
    if unknown:
        raise ValueError("UNKNOWN_TASK_FIELDS:" + ",".join(unknown))
    required = expected - {"parameters", "effect"}
    missing = sorted(key for key in required if task.get(key) in (None, ""))
    if missing:
        raise ValueError("TASK_FIELDS_MISSING:" + ",".join(missing))
    if task["schema"] != TASK_SCHEMA:
        raise ValueError("TASK_SCHEMA_INVALID")
    _require_id(str(task["task_id"]), "TASK_ID")
    _require_id(str(task["correlation_id"]), "CORRELATION_ID")
    if task["issued_by"] != "FUSE/FDOF":
        raise ValueError("TASK_ISSUER_INVALID")
    if task["task_type"] not in ALLOWED_TASKS:
        raise ValueError("TASK_TYPE_NOT_ALLOWLISTED")
    if task.get("effect", ALLOWED_EFFECT) != ALLOWED_EFFECT:
        raise ValueError("TASK_EFFECT_NOT_AUTHORIZED")
    if not isinstance(task.get("parameters") or {}, Mapping):
        raise ValueError("TASK_PARAMETERS_OBJECT_REQUIRED")
    issued = _parse_utc_z(str(task["issued_at"]), "TASK_ISSUED_AT")
    expires = _parse_utc_z(str(task["expires_at"]), "TASK_EXPIRES_AT")
    current = now or utc_now()
    if expires <= issued:
        raise ValueError("TASK_TIME_WINDOW_INVALID")
    if current >= expires:
        raise ValueError("TASK_EXPIRED")
    if issued > current:
        raise ValueError("TASK_NOT_YET_VALID")
    if (expires - issued).total_seconds() > 900:
        raise ValueError("TASK_TTL_EXCEEDS_900_SECONDS")


def validate_receipt_mapping(receipt: Mapping[str, Any]) -> None:
    if not isinstance(receipt, Mapping):
        raise ValueError("RECEIPT_OBJECT_REQUIRED")
    required = {
        "schema", "task_id", "correlation_id", "task_type", "state",
        "started_at", "completed_at", "runner", "task", "result",
        "task_sha256", "result_sha256", "effect",
    }
    missing = sorted(key for key in required if receipt.get(key) in (None, ""))
    if missing:
        raise ValueError("RECEIPT_FIELDS_MISSING:" + ",".join(missing))
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise ValueError("RECEIPT_SCHEMA_INVALID")
    if receipt["effect"] != ALLOWED_EFFECT:
        raise ValueError("RECEIPT_EFFECT_INVALID")
    if receipt["state"] != "COMPLETED_VERIFIED_LOCAL":
        raise ValueError("RECEIPT_STATE_INVALID")
    if receipt["task_type"] not in ALLOWED_TASKS:
        raise ValueError("RECEIPT_TASK_TYPE_INVALID")
    runner = receipt["runner"]
    if not isinstance(runner, Mapping) or runner.get("os") != "Windows":
        raise ValueError("WINDOWS_RUNNER_NOT_PROVEN")
    task = receipt["task"]
    result = receipt["result"]
    if not isinstance(task, Mapping) or not isinstance(result, Mapping):
        raise ValueError("RECEIPT_HASH_INPUT_INVALID")
    expected_task_hash = sha256_hex(canonical_json(task))
    expected_result_hash = sha256_hex(canonical_json(result))
    if not hmac.compare_digest(str(receipt["task_sha256"]), expected_task_hash):
        raise ValueError("TASK_HASH_MISMATCH")
    if not hmac.compare_digest(str(receipt["result_sha256"]), expected_result_hash):
        raise ValueError("RESULT_HASH_MISMATCH")


@dataclass(frozen=True)
class EnrollmentGrant:
    schema: str
    enrollment_id: str
    enrollment_token: str
    issued_at: str
    expires_at: str
    max_uses: int = 1

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeviceCredential:
    schema: str
    device_id: str
    device_secret: str
    enrolled_at: str

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelayLease:
    schema: str
    task_id: str
    device_id: str
    lease_token: str
    leased_at: str
    expires_at: str

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _EnrollmentRecord:
    token_digest: str
    expires_at: datetime
    used: bool = False


@dataclass
class _TaskRecord:
    task: dict[str, Any]
    device_id: str
    lease_token_digest: str | None = None
    lease_expires_at: datetime | None = None
    completed: bool = False
    receipt: dict[str, Any] | None = None


class ReplayWindow:
    """In-memory replay window. Production storage must provide equivalent atomic semantics."""

    def __init__(self, ttl_seconds: int = 120):
        if ttl_seconds <= 0:
            raise ValueError("REPLAY_TTL_INVALID")
        self.ttl = timedelta(seconds=ttl_seconds)
        self._seen: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def consume(self, device_id: str, nonce: str, *, now: datetime) -> None:
        _require_id(device_id, "DEVICE_ID")
        _require_id(nonce, "NONCE")
        with self._lock:
            cutoff = now - self.ttl
            self._seen = {key: seen_at for key, seen_at in self._seen.items() if seen_at >= cutoff}
            key = (device_id, nonce)
            if key in self._seen:
                raise ValueError("REPLAY_DETECTED")
            self._seen[key] = now


def signing_payload(
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    if not method or not path or not timestamp or not nonce:
        raise ValueError("SIGNING_FIELDS_REQUIRED")
    return b"\n".join(
        (
            method.upper().encode("ascii"),
            path.encode("utf-8"),
            timestamp.encode("ascii"),
            nonce.encode("ascii"),
            sha256_hex(body).encode("ascii"),
        )
    )


def sign_request(
    secret: str,
    *,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> str:
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("DEVICE_SECRET_TOO_SHORT")
    payload = signing_payload(method=method, path=path, timestamp=timestamp, nonce=nonce, body=body)
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


class SovereignRelay:
    """
    Source-level relay/enrollment state machine for an outbound-only Windows agent.

    This class deliberately contains no public listener, cloud deployment, OAuth flow, secret-manager
    binding, or inbound workstation socket. A hosted transport may bind these methods later, but the
    security invariants are enforced here first.
    """

    def __init__(
        self,
        *,
        enrollment_ttl_seconds: int = 300,
        request_skew_seconds: int = 60,
        lease_ttl_seconds: int = 120,
    ):
        if min(enrollment_ttl_seconds, request_skew_seconds, lease_ttl_seconds) <= 0:
            raise ValueError("TTL_INVALID")
        self.enrollment_ttl = timedelta(seconds=enrollment_ttl_seconds)
        self.request_skew = timedelta(seconds=request_skew_seconds)
        self.lease_ttl = timedelta(seconds=lease_ttl_seconds)
        self._enrollments: dict[str, _EnrollmentRecord] = {}
        self._device_secrets: dict[str, str] = {}
        self._tasks: dict[str, _TaskRecord] = {}
        self._queue: list[str] = []
        self._replay = ReplayWindow(ttl_seconds=max(120, request_skew_seconds * 2))
        self._lock = threading.RLock()

    def issue_enrollment(self, *, now: datetime | None = None) -> EnrollmentGrant:
        current = now or utc_now()
        enrollment_id = "enr_" + _token(12)
        token = _token(32)
        expires = current + self.enrollment_ttl
        with self._lock:
            self._enrollments[enrollment_id] = _EnrollmentRecord(
                token_digest=sha256_hex(token.encode("utf-8")),
                expires_at=expires,
            )
        return EnrollmentGrant(
            schema=RELAY_ENROLLMENT_SCHEMA,
            enrollment_id=enrollment_id,
            enrollment_token=token,
            issued_at=current.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
        )

    def enroll(
        self,
        *,
        enrollment_id: str,
        enrollment_token: str,
        device_label: str,
        now: datetime | None = None,
    ) -> DeviceCredential:
        current = now or utc_now()
        _require_id(enrollment_id, "ENROLLMENT_ID")
        _require_id(device_label, "DEVICE_LABEL")
        presented = sha256_hex(enrollment_token.encode("utf-8"))
        with self._lock:
            record = self._enrollments.get(enrollment_id)
            if record is None:
                raise ValueError("ENROLLMENT_UNKNOWN")
            if record.used:
                raise ValueError("ENROLLMENT_ALREADY_USED")
            if current >= record.expires_at:
                raise ValueError("ENROLLMENT_EXPIRED")
            if not hmac.compare_digest(presented, record.token_digest):
                raise ValueError("ENROLLMENT_TOKEN_INVALID")
            record.used = True
            device_id = "dev_" + sha256_hex(
                canonical_json({"enrollment_id": enrollment_id, "device_label": device_label})
            )[:24]
            secret = _token(48)
            self._device_secrets[device_id] = secret
        return DeviceCredential(
            schema="FUSE-WINDOWS-DEVICE-CREDENTIAL-V1",
            device_id=device_id,
            device_secret=secret,
            enrolled_at=current.isoformat().replace("+00:00", "Z"),
        )

    def verify_device_request(
        self,
        *,
        device_id: str,
        method: str,
        path: str,
        timestamp: str,
        nonce: str,
        signature: str,
        body: bytes = b"",
        now: datetime | None = None,
    ) -> None:
        current = now or utc_now()
        secret = self._device_secrets.get(device_id)
        if secret is None:
            raise ValueError("DEVICE_UNKNOWN")
        try:
            signed_at = _parse_utc_z(timestamp, "REQUEST_TIMESTAMP")
        except ValueError as exc:
            raise ValueError("REQUEST_TIMESTAMP_INVALID") from exc
        if abs(current - signed_at) > self.request_skew:
            raise ValueError("REQUEST_TIMESTAMP_OUTSIDE_WINDOW")
        expected = sign_request(
            secret,
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError("REQUEST_SIGNATURE_INVALID")
        self._replay.consume(device_id, nonce, now=current)

    def submit_task(
        self, *, device_id: str, task: Mapping[str, Any], now: datetime | None = None
    ) -> str:
        if device_id not in self._device_secrets:
            raise ValueError("DEVICE_UNKNOWN")
        validate_task_mapping(task, now=now)
        task_id = str(task["task_id"])
        with self._lock:
            if task_id in self._tasks:
                existing = self._tasks[task_id]
                if canonical_json(existing.task) == canonical_json(dict(task)) and existing.device_id == device_id:
                    return task_id
                raise ValueError("TASK_ID_COLLISION")
            self._tasks[task_id] = _TaskRecord(task=dict(task), device_id=device_id)
            self._queue.append(task_id)
        return task_id

    def poll(
        self,
        *,
        device_id: str,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], RelayLease] | None:
        current = now or utc_now()
        with self._lock:
            for task_id in list(self._queue):
                record = self._tasks[task_id]
                if record.device_id != device_id or record.completed:
                    continue
                if record.lease_expires_at is not None and current < record.lease_expires_at:
                    continue
                lease_token = _token(32)
                record.lease_token_digest = sha256_hex(lease_token.encode("utf-8"))
                record.lease_expires_at = current + self.lease_ttl
                return dict(record.task), RelayLease(
                    schema=RELAY_LEASE_SCHEMA,
                    task_id=task_id,
                    device_id=device_id,
                    lease_token=lease_token,
                    leased_at=current.isoformat().replace("+00:00", "Z"),
                    expires_at=record.lease_expires_at.isoformat().replace("+00:00", "Z"),
                )
        return None

    def complete(
        self,
        *,
        device_id: str,
        task_id: str,
        lease_token: str,
        receipt: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or utc_now()
        validate_receipt_mapping(receipt)
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise ValueError("TASK_UNKNOWN")
            if record.device_id != device_id:
                raise ValueError("TASK_DEVICE_MISMATCH")
            if record.completed:
                if record.receipt is not None and canonical_json(record.receipt) == canonical_json(dict(receipt)):
                    return dict(record.receipt)
                raise ValueError("TASK_ALREADY_COMPLETED")
            if record.lease_expires_at is None or current >= record.lease_expires_at:
                raise ValueError("LEASE_EXPIRED")
            presented = sha256_hex(lease_token.encode("utf-8"))
            if record.lease_token_digest is None or not hmac.compare_digest(presented, record.lease_token_digest):
                raise ValueError("LEASE_TOKEN_INVALID")
            if receipt["task_id"] != task_id:
                raise ValueError("RECEIPT_TASK_ID_MISMATCH")
            if receipt["correlation_id"] != record.task["correlation_id"]:
                raise ValueError("RECEIPT_CORRELATION_MISMATCH")
            if receipt["task_type"] != record.task["task_type"]:
                raise ValueError("RECEIPT_TASK_TYPE_MISMATCH")
            record.completed = True
            record.receipt = dict(receipt)
            if task_id in self._queue:
                self._queue.remove(task_id)
            return dict(record.receipt)

    def status(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise ValueError("TASK_UNKNOWN")
            return {
                "task_id": task_id,
                "device_id": record.device_id,
                "completed": record.completed,
                "receipt_sha256": (
                    sha256_hex(canonical_json(record.receipt)) if record.receipt is not None else None
                ),
                "effect": ALLOWED_EFFECT,
            }
