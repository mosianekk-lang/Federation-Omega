from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
from typing import Any, Mapping

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from .relay_protocol import (
    DeviceCredential,
    EnrollmentGrant,
    RelayLease,
    canonical_json,
    sha256_hex,
    sign_request,
    validate_receipt_mapping,
    validate_task_mapping,
    _parse_utc_z,
    _require_id,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _token(size: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(size)).decode("ascii").rstrip("=")


def _assert_receipt_matches_task(
    receipt: Mapping[str, Any], task: Mapping[str, Any]
) -> None:
    """Reject receipts that substitute any part of the authorized task envelope."""
    receipt_task = receipt.get("task")
    if not isinstance(receipt_task, Mapping):
        raise ValueError("RECEIPT_TASK_MISSING")
    if canonical_json(dict(receipt_task)) != canonical_json(dict(task)):
        raise ValueError("RECEIPT_TASK_MISMATCH")


class FirestoreRelay:
    """Durable relay using Firestore transactions and a Cloud Run injected root key."""

    def __init__(
        self,
        *,
        project: str,
        root_secret: str,
        namespace: str = "fuse_windows_relay_v1",
        enrollment_ttl_seconds: int = 300,
        request_skew_seconds: int = 60,
        lease_ttl_seconds: int = 120,
        client: firestore.Client | None = None,
    ) -> None:
        if len(root_secret) < 32:
            raise ValueError("RELAY_ROOT_SECRET_TOO_SHORT")
        self.client = client or firestore.Client(project=project)
        self.root_secret = root_secret.encode("utf-8")
        self.root = self.client.collection(namespace)
        self.enrollment_ttl = timedelta(seconds=enrollment_ttl_seconds)
        self.request_skew = timedelta(seconds=request_skew_seconds)
        self.lease_ttl = timedelta(seconds=lease_ttl_seconds)

    def _collection(self, name: str):
        return self.root.document("state").collection(name)

    def _device_secret(self, device_id: str) -> str:
        digest = hmac.new(self.root_secret, ("device:" + device_id).encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def issue_enrollment(self, *, now: datetime | None = None) -> EnrollmentGrant:
        current = now or _now()
        enrollment_id = "enr_" + _token(12)
        token = _token(32)
        expires = current + self.enrollment_ttl
        self._collection("enrollments").document(enrollment_id).create({
            "token_digest": sha256_hex(token.encode()),
            "expires_at": expires,
            "used": False,
            "created_at": current,
        })
        return EnrollmentGrant(
            schema="FUSE-WINDOWS-RELAY-ENROLLMENT-V1",
            enrollment_id=enrollment_id,
            enrollment_token=token,
            issued_at=_z(current),
            expires_at=_z(expires),
        )

    def enroll(self, *, enrollment_id: str, enrollment_token: str, device_label: str) -> DeviceCredential:
        current = _now()
        _require_id(enrollment_id, "ENROLLMENT_ID")
        _require_id(device_label, "DEVICE_LABEL")
        enrollment = self._collection("enrollments").document(enrollment_id)
        device_id = "dev_" + sha256_hex(canonical_json({
            "enrollment_id": enrollment_id,
            "device_label": device_label,
        }))[:24]
        device = self._collection("devices").document(device_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def use_grant(txn):
            snapshot = enrollment.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("ENROLLMENT_UNKNOWN")
            record = snapshot.to_dict() or {}
            if record.get("used"):
                raise ValueError("ENROLLMENT_ALREADY_USED")
            expires = record.get("expires_at")
            if not isinstance(expires, datetime) or current >= expires:
                raise ValueError("ENROLLMENT_EXPIRED")
            presented = sha256_hex(enrollment_token.encode())
            if not hmac.compare_digest(presented, str(record.get("token_digest") or "")):
                raise ValueError("ENROLLMENT_TOKEN_INVALID")
            txn.update(enrollment, {"used": True, "used_at": current, "device_id": device_id})
            txn.set(device, {
                "device_id": device_id,
                "label_sha256": sha256_hex(device_label.encode()),
                "enrolled_at": current,
                "last_seen_at": None,
                "disabled": False,
            })

        use_grant(transaction)
        return DeviceCredential(
            schema="FUSE-WINDOWS-DEVICE-CREDENTIAL-V1",
            device_id=device_id,
            device_secret=self._device_secret(device_id),
            enrolled_at=_z(current),
        )

    def verify_device_request(
        self, *, device_id: str, method: str, path: str, timestamp: str,
        nonce: str, signature: str, body: bytes = b"", now: datetime | None = None,
    ) -> None:
        current = now or _now()
        _require_id(device_id, "DEVICE_ID")
        _require_id(nonce, "NONCE")
        try:
            signed_at = _parse_utc_z(timestamp, "REQUEST_TIMESTAMP")
        except ValueError as exc:
            raise ValueError("REQUEST_TIMESTAMP_INVALID") from exc
        if abs(current - signed_at) > self.request_skew:
            raise ValueError("REQUEST_TIMESTAMP_OUTSIDE_WINDOW")
        device = self._collection("devices").document(device_id).get()
        if not device.exists or (device.to_dict() or {}).get("disabled"):
            raise ValueError("DEVICE_UNKNOWN")
        expected = sign_request(
            self._device_secret(device_id), method=method, path=path,
            timestamp=timestamp, nonce=nonce, body=body,
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError("REQUEST_SIGNATURE_INVALID")
        nonce_id = sha256_hex((device_id + ":" + nonce).encode())
        try:
            self._collection("nonces").document(nonce_id).create({
                "device_id": device_id, "seen_at": current,
                "expires_at": current + timedelta(minutes=5),
            })
        except AlreadyExists as exc:
            raise ValueError("REPLAY_DETECTED") from exc
        self._collection("devices").document(device_id).update({"last_seen_at": current})

    def submit_task(self, *, device_id: str, task: Mapping[str, Any], now: datetime | None = None) -> str:
        current = now or _now()
        _require_id(device_id, "DEVICE_ID")
        validate_task_mapping(task, now=current)
        device = self._collection("devices").document(device_id).get()
        if not device.exists or (device.to_dict() or {}).get("disabled"):
            raise ValueError("DEVICE_UNKNOWN")
        task_id = str(task["task_id"])
        ref = self._collection("tasks").document(task_id)
        payload = {
            "task": dict(task), "device_id": device_id, "created_at": current,
            "completed": False, "lease_token_digest": None, "lease_expires_at": None,
        }
        try:
            ref.create(payload)
        except AlreadyExists:
            existing = ref.get().to_dict() or {}
            if existing.get("device_id") != device_id or canonical_json(existing.get("task")) != canonical_json(dict(task)):
                raise ValueError("TASK_ID_COLLISION")
        return task_id

    def poll(self, *, device_id: str, now: datetime | None = None):
        current = now or _now()
        query = self._collection("tasks").where("device_id", "==", device_id).limit(100)
        for snapshot in query.stream():
            if (snapshot.to_dict() or {}).get("completed"):
                continue
            ref = snapshot.reference
            transaction = self.client.transaction()
            lease_token = _token(32)

            @firestore.transactional
            def try_lease(txn):
                fresh = ref.get(transaction=txn)
                record = fresh.to_dict() or {}
                expiry = record.get("lease_expires_at")
                if record.get("completed") or (isinstance(expiry, datetime) and current < expiry):
                    return None
                lease_expires = current + self.lease_ttl
                txn.update(ref, {
                    "lease_token_digest": sha256_hex(lease_token.encode()),
                    "lease_expires_at": lease_expires,
                    "leased_at": current,
                })
                return record.get("task"), lease_expires

            leased = try_lease(transaction)
            if leased:
                task, expiry = leased
                return dict(task), RelayLease(
                    schema="FUSE-WINDOWS-RELAY-LEASE-V1",
                    task_id=str(task["task_id"]), device_id=device_id,
                    lease_token=lease_token, leased_at=_z(current), expires_at=_z(expiry),
                )
        return None

    def complete(self, *, device_id: str, task_id: str, lease_token: str, receipt: Mapping[str, Any]):
        validate_receipt_mapping(receipt)
        current = _now()
        ref = self._collection("tasks").document(task_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def finish(txn):
            snapshot = ref.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("TASK_UNKNOWN")
            record = snapshot.to_dict() or {}
            if record.get("device_id") != device_id:
                raise ValueError("TASK_DEVICE_MISMATCH")
            if record.get("completed"):
                if canonical_json(record.get("receipt")) == canonical_json(dict(receipt)):
                    return dict(receipt)
                raise ValueError("TASK_ALREADY_COMPLETED")
            expiry = record.get("lease_expires_at")
            if not isinstance(expiry, datetime) or current >= expiry:
                raise ValueError("LEASE_EXPIRED")
            if not hmac.compare_digest(
                sha256_hex(lease_token.encode()), str(record.get("lease_token_digest") or "")
            ):
                raise ValueError("LEASE_TOKEN_INVALID")
            task = record.get("task") or {}
            if any(receipt.get(k) != task.get(k) for k in ("task_id", "correlation_id", "task_type")):
                raise ValueError("RECEIPT_TASK_BINDING_MISMATCH")
            _assert_receipt_matches_task(receipt, task)
            txn.update(ref, {"completed": True, "completed_at": current, "receipt": dict(receipt)})
            return dict(receipt)

        return finish(transaction)

    def status(self, task_id: str) -> dict[str, Any]:
        _require_id(task_id, "TASK_ID")
        snapshot = self._collection("tasks").document(task_id).get()
        if not snapshot.exists:
            raise ValueError("TASK_UNKNOWN")
        record = snapshot.to_dict() or {}
        receipt = record.get("receipt")
        return {
            "task_id": task_id,
            "device_id": record.get("device_id"),
            "completed": bool(record.get("completed")),
            "receipt_sha256": sha256_hex(canonical_json(receipt)) if receipt else None,
            "effect": "READ_ONLY",
        }

    def list_devices(self) -> list[dict[str, Any]]:
        devices = []
        for snapshot in self._collection("devices").limit(100).stream():
            record = snapshot.to_dict() or {}
            devices.append({
                "device_id": record.get("device_id"),
                "enrolled_at": _z(record["enrolled_at"]) if record.get("enrolled_at") else None,
                "last_seen_at": _z(record["last_seen_at"]) if record.get("last_seen_at") else None,
                "disabled": bool(record.get("disabled")),
            })
        return devices
