from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from typing import Any, Mapping

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import mcp_service as base_service
from .firestore_relay import FirestoreRelay
from .relay_protocol import canonical_json, sha256_hex
from .trust_spine_v21 import ECDSASigner

SCSF_PROTOCOL = "SCSF_V1"
SCSF_DEVICE_AUTH_MODE = "SCSF_ECDSA_P256"
SCSF_ENROLL_SCHEMA = "FUSE-ENROLL-V1"
SCSF_HEARTBEAT_SCHEMA = "FUSE-HEARTBEAT-V1"
SCSF_POLL_SCHEMA = "FUSE-POLL-V1"
SCSF_TASK_SCHEMA = "FUSE-TASK-V1"
SCSF_TASK_ENVELOPE_SCHEMA = "FUSE-TASK-ENVELOPE-V1"
SCSF_RESULT_SCHEMA = "FUSE-RESULT-V1"
SCSF_RESULT_ATTESTATION_SCHEMA = "FUSE-RESULT-ATTESTATION-V1"
SCSF_REQUEST_DOMAIN = "FUSE-REQ-V1"
SCSF_ALLOWED_TASKS = frozenset({
    "system_status", "self_canary", "hardware_profile", "compile_mission_topology",
    "hash_file", "directory_manifest", "heavy_sha256", "export_blackbox_bundle",
})
SCSF_ALLOWED_EFFECTS = frozenset({"A0", "A1"})
SCSF_ROUTES = frozenset({
    "/v1/agent/enroll", "/v1/agent/heartbeat", "/v1/agent/poll", "/v1/agent/complete",
})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(label + "_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(label + "_INVALID") from exc
    if parsed.tzinfo is None:
        raise ValueError(label + "_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _valid_hex(value: str, size: int = 64) -> bool:
    return len(value) == size and re.fullmatch(r"[0-9a-f]+", value) is not None


def _require_jwk(jwk: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(jwk, Mapping) or set(jwk) != {"kty", "crv", "x", "y"}:
        raise ValueError("P256_JWK_FIELDS_INVALID")
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise ValueError("P256_JWK_CURVE_INVALID")
    x, y = str(jwk.get("x") or ""), str(jwk.get("y") or "")
    try:
        xb, yb = _unb64u(x), _unb64u(y)
    except Exception as exc:
        raise ValueError("P256_JWK_COORDINATE_INVALID") from exc
    if len(xb) != 32 or len(yb) != 32:
        raise ValueError("P256_JWK_COORDINATE_INVALID")
    return x, y


def jwk_to_spki_b64(jwk: Mapping[str, Any]) -> str:
    x, y = _require_jwk(jwk)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(_unb64u(x), "big"), int.from_bytes(_unb64u(y), "big"), ec.SECP256R1()
    )
    key = numbers.public_key()
    return _b64u(key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))


def device_id_from_jwk(jwk: Mapping[str, Any]) -> str:
    x, y = _require_jwk(jwk)
    return "fuse-dev-" + hashlib.sha256((x + "." + y).encode("ascii")).hexdigest()[:32]


def scsf_signing_payload(*, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    if path not in SCSF_ROUTES or not method or not timestamp or not nonce:
        raise ValueError("SCSF_SIGNING_FIELDS_INVALID")
    return (SCSF_REQUEST_DOMAIN + "\n" + method.upper() + "\n" + path + "\n" + timestamp + "\n" + nonce + "\n" + sha256_hex(body)).encode("utf-8")


def verify_jwk_signature(jwk: Mapping[str, Any], payload: bytes, signature_b64: str) -> bool:
    return ECDSASigner.verify_spki_b64(jwk_to_spki_b64(jwk), payload, signature_b64)


class P256SoftwareControlSigner:
    """Test/development signer. Production server construction never auto-generates this key."""
    def __init__(self, key: Any):
        self._key = key

    @classmethod
    def generate(cls) -> "P256SoftwareControlSigner":
        from cryptography.hazmat.primitives.asymmetric import ec
        return cls(ec.generate_private_key(ec.SECP256R1()))

    def public_jwk(self) -> dict[str, str]:
        nums = self._key.public_key().public_numbers()
        return {
            "kty": "EC", "crv": "P-256",
            "x": _b64u(nums.x.to_bytes(32, "big")),
            "y": _b64u(nums.y.to_bytes(32, "big")),
        }

    def sign_b64(self, payload: bytes) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        der = self._key.sign(payload, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def validate_scsf_task(task: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(task, Mapping):
        raise ValueError("SCSF_TASK_OBJECT_REQUIRED")
    allowed = {"schema", "task_id", "mission_id", "correlation_id", "task_type", "issued_at", "expires_at", "nonce", "effect_class", "args"}
    unknown = sorted(set(task) - allowed)
    if unknown:
        raise ValueError("SCSF_TASK_UNKNOWN_FIELDS:" + ",".join(unknown))
    required = {"schema", "task_id", "task_type", "issued_at", "expires_at", "nonce", "effect_class", "args"}
    missing = sorted(k for k in required if k not in task)
    if missing:
        raise ValueError("SCSF_TASK_FIELDS_MISSING:" + ",".join(missing))
    if task.get("schema") != SCSF_TASK_SCHEMA:
        raise ValueError("SCSF_TASK_SCHEMA_INVALID")
    task_id = str(task.get("task_id") or "")
    nonce = str(task.get("nonce") or "")
    if re.fullmatch(r"[A-Za-z0-9._:-]{6,160}", task_id) is None:
        raise ValueError("SCSF_TASK_ID_INVALID")
    if re.fullmatch(r"[A-Za-z0-9._:-]{12,160}", nonce) is None:
        raise ValueError("SCSF_TASK_NONCE_INVALID")
    if task.get("task_type") not in SCSF_ALLOWED_TASKS:
        raise ValueError("SCSF_TASK_TYPE_NOT_ALLOWLISTED")
    if task.get("effect_class") not in SCSF_ALLOWED_EFFECTS:
        raise PermissionError("SCSF_TASK_EFFECT_EXCEEDS_A1")
    if not isinstance(task.get("args"), Mapping):
        raise ValueError("SCSF_TASK_ARGS_OBJECT_REQUIRED")
    issued = _parse_time(task["issued_at"], "SCSF_TASK_ISSUED_AT")
    expires = _parse_time(task["expires_at"], "SCSF_TASK_EXPIRES_AT")
    current = now or _now()
    if issued > current + timedelta(minutes=2):
        raise ValueError("SCSF_TASK_ISSUED_IN_FUTURE")
    if expires <= current:
        raise ValueError("SCSF_TASK_EXPIRED")
    if expires <= issued or expires - issued > timedelta(hours=1):
        raise ValueError("SCSF_TASK_TTL_INVALID")
    return dict(task)


def make_task_envelope(task: Mapping[str, Any], signer: P256SoftwareControlSigner, *, now: datetime | None = None) -> dict[str, Any]:
    validated = validate_scsf_task(task, now=now)
    payload = canonical_json(validated)
    return {
        "schema": SCSF_TASK_ENVELOPE_SCHEMA,
        "payload_b64": _b64u(payload),
        "payload_sha256": sha256_hex(payload),
        "signature_b64": signer.sign_b64(payload),
    }


def verify_task_envelope(envelope: Mapping[str, Any], control_jwk: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(envelope, Mapping) or set(envelope) != {"schema", "payload_b64", "payload_sha256", "signature_b64"}:
        raise ValueError("SCSF_TASK_ENVELOPE_FIELDS_INVALID")
    if envelope.get("schema") != SCSF_TASK_ENVELOPE_SCHEMA:
        raise ValueError("SCSF_TASK_ENVELOPE_SCHEMA_INVALID")
    try:
        payload = _unb64u(str(envelope.get("payload_b64") or ""))
    except Exception as exc:
        raise ValueError("SCSF_TASK_PAYLOAD_B64_INVALID") from exc
    if len(payload) > 196608 or sha256_hex(payload) != envelope.get("payload_sha256"):
        raise ValueError("SCSF_TASK_PAYLOAD_HASH_INVALID")
    if not verify_jwk_signature(control_jwk, payload, str(envelope.get("signature_b64") or "")):
        raise PermissionError("SCSF_TASK_SIGNATURE_INVALID")
    try:
        task = json.loads(payload)
    except Exception as exc:
        raise ValueError("SCSF_TASK_PAYLOAD_JSON_INVALID") from exc
    return validate_scsf_task(task, now=now)


class FirestoreSCSFStore:
    """SCSF adapter over the existing FirestoreRelay namespace. No second queue or datastore."""
    def __init__(self, relay: FirestoreRelay):
        self.relay = relay

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        snap = self.relay._collection(collection).document(key).get()
        return dict(snap.to_dict() or {}) if snap.exists else None

    def create(self, collection: str, key: str, value: Mapping[str, Any], *, replay_code: str) -> None:
        try:
            self.relay._collection(collection).document(key).create(dict(value))
        except AlreadyExists as exc:
            raise ValueError(replay_code) from exc

    def update(self, collection: str, key: str, value: Mapping[str, Any]) -> None:
        self.relay._collection(collection).document(key).update(dict(value))

    def list_for(self, collection: str, field: str, value: Any, *, limit: int = 100) -> list[dict[str, Any]]:
        out = []
        for snap in self.relay._collection(collection).where(field, "==", value).limit(limit).stream():
            row = dict(snap.to_dict() or {})
            row["_id"] = snap.id
            out.append(row)
        return out

    def consume_enrollment(self, *, grant_key: str, token_digest: str, device_id: str, device_record: Mapping[str, Any], now: datetime) -> dict[str, Any]:
        grant_ref = self.relay._collection("enrollments").document(grant_key)
        device_ref = self.relay._collection("devices").document(device_id)
        transaction = self.relay.client.transaction()

        @firestore.transactional
        def consume(txn):
            snap = grant_ref.get(transaction=txn)
            if not snap.exists:
                raise ValueError("SCSF_PAIRING_GRANT_UNKNOWN")
            grant = dict(snap.to_dict() or {})
            if grant.get("protocol") != SCSF_PROTOCOL:
                raise ValueError("SCSF_PAIRING_GRANT_PROTOCOL_INVALID")
            if grant.get("used"):
                raise ValueError("SCSF_PAIRING_GRANT_ALREADY_USED")
            expires = grant.get("expires_at")
            if not isinstance(expires, datetime) or now >= expires:
                raise ValueError("SCSF_PAIRING_GRANT_EXPIRED")
            if not hmac.compare_digest(str(grant.get("token_digest") or ""), token_digest):
                raise ValueError("SCSF_PAIRING_GRANT_INVALID")
            txn.update(grant_ref, {"used": True, "used_at": now, "device_id": device_id})
            txn.set(device_ref, dict(device_record))
            return grant

        return consume(transaction)

    def create_task(self, task_id: str, record: Mapping[str, Any]) -> None:
        ref = self.relay._collection("tasks").document(task_id)
        try:
            ref.create(dict(record))
        except AlreadyExists:
            existing = dict(ref.get().to_dict() or {})
            if canonical_json(existing.get("envelope")) != canonical_json(record.get("envelope")) or existing.get("device_id") != record.get("device_id"):
                raise ValueError("SCSF_TASK_ID_CONFLICT")

    def complete_task(self, *, task_id: str, device_id: str, attestation: Mapping[str, Any], now: datetime) -> bool:
        ref = self.relay._collection("tasks").document(task_id)
        transaction = self.relay.client.transaction()

        @firestore.transactional
        def finish(txn):
            snap = ref.get(transaction=txn)
            if not snap.exists:
                raise ValueError("SCSF_TASK_UNKNOWN")
            record = dict(snap.to_dict() or {})
            if record.get("protocol") != SCSF_PROTOCOL:
                raise ValueError("SCSF_TASK_PROTOCOL_INVALID")
            if record.get("device_id") != device_id:
                raise PermissionError("SCSF_TASK_DEVICE_MISMATCH")
            if record.get("completed"):
                if canonical_json(record.get("result_attestation")) == canonical_json(dict(attestation)):
                    return True
                raise ValueError("SCSF_RESULT_CONFLICT")
            txn.update(ref, {"completed": True, "completed_at": now, "result_attestation": dict(attestation)})
            return False

        return finish(transaction)


class SCSFRuntime:
    def __init__(self, *, store: Any, control_signer: P256SoftwareControlSigner | None, request_skew_seconds: int = 120):
        self.store = store
        self.control_signer = control_signer
        self.request_skew = timedelta(seconds=request_skew_seconds)
        if request_skew_seconds <= 0:
            raise ValueError("SCSF_REQUEST_SKEW_INVALID")

    def _require_signer(self) -> P256SoftwareControlSigner:
        if self.control_signer is None:
            raise RuntimeError("SCSF_CONTROL_SIGNER_UNCONFIGURED")
        return self.control_signer

    def issue_pairing_grant(self, *, now: datetime | None = None, ttl_seconds: int = 300) -> dict[str, Any]:
        signer = self._require_signer()
        current = now or _now()
        if not 30 <= ttl_seconds <= 900:
            raise ValueError("SCSF_PAIRING_TTL_INVALID")
        token = _b64u(secrets.token_bytes(32))
        digest = sha256_hex(token.encode("utf-8"))
        key = "scsf_" + digest
        expires = current + timedelta(seconds=ttl_seconds)
        jwk = signer.public_jwk()
        self.store.create("enrollments", key, {
            "protocol": SCSF_PROTOCOL, "token_digest": digest, "expires_at": expires,
            "used": False, "created_at": current, "control_signer_jwk": jwk,
        }, replay_code="SCSF_PAIRING_GRANT_COLLISION")
        return {"schema": "FUSE-PAIRING-GRANT-V1", "pairing_grant": token, "expires_at": _z(expires), "control_signer_jwk": jwk}

    def enroll(self, data: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        signer = self._require_signer()
        if not isinstance(data, Mapping) or set(data) != {"schema", "pairing_grant", "device_id", "x", "y"}:
            raise ValueError("SCSF_ENROLL_FIELDS_INVALID")
        if data.get("schema") != SCSF_ENROLL_SCHEMA:
            raise ValueError("SCSF_ENROLL_SCHEMA_INVALID")
        token = str(data.get("pairing_grant") or "")
        if len(token) < 32 or len(token) > 128:
            raise ValueError("SCSF_PAIRING_GRANT_INVALID")
        jwk = {"kty": "EC", "crv": "P-256", "x": str(data.get("x") or ""), "y": str(data.get("y") or "")}
        expected_id = device_id_from_jwk(jwk)
        device_id = str(data.get("device_id") or "")
        if not hmac.compare_digest(device_id, expected_id):
            raise ValueError("DEVICE_ID_KEY_MISMATCH")
        current = now or _now()
        digest = sha256_hex(token.encode("utf-8"))
        public_spki = jwk_to_spki_b64(jwk)
        control_jwk = signer.public_jwk()
        record = {
            "device_id": device_id, "protocol": SCSF_PROTOCOL, "auth_mode": SCSF_DEVICE_AUTH_MODE,
            "device_generation": 1, "public_key_spki_b64": public_spki,
            "x": jwk["x"], "y": jwk["y"], "enrolled_at": current, "last_seen_at": None,
            "last_heartbeat_at": None, "disabled": False, "control_signer_jwk": control_jwk,
        }
        grant = self.store.consume_enrollment(
            grant_key="scsf_" + digest, token_digest=digest, device_id=device_id,
            device_record=record, now=current,
        )
        if canonical_json(grant.get("control_signer_jwk")) != canonical_json(control_jwk):
            raise PermissionError("SCSF_CONTROL_SIGNER_DRIFT")
        return {"state": "PAIRED", "device_id": device_id, "control_signer_jwk": control_jwk}

    def verify_request(self, *, device_id: str, method: str, path: str, timestamp: str, nonce: str,
                       signature: str, key_x: str, key_y: str, body: bytes, now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        if not re.fullmatch(r"fuse-dev-[0-9a-f]{32}", device_id or ""):
            raise ValueError("SCSF_DEVICE_ID_INVALID")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{12,160}", nonce or ""):
            raise ValueError("SCSF_REQUEST_NONCE_INVALID")
        signed_at = _parse_time(timestamp, "SCSF_REQUEST_TIMESTAMP")
        if abs(current - signed_at) > self.request_skew:
            raise ValueError("SCSF_REQUEST_TIMESTAMP_OUTSIDE_WINDOW")
        device = self.store.get("devices", device_id)
        if not device or device.get("disabled") or device.get("protocol") != SCSF_PROTOCOL or device.get("auth_mode") != SCSF_DEVICE_AUTH_MODE:
            raise ValueError("SCSF_DEVICE_UNKNOWN")
        if key_x != device.get("x") or key_y != device.get("y"):
            raise PermissionError("SCSF_REQUEST_KEY_HEADER_MISMATCH")
        payload = scsf_signing_payload(method=method, path=path, timestamp=timestamp, nonce=nonce, body=body)
        if not ECDSASigner.verify_spki_b64(str(device.get("public_key_spki_b64") or ""), payload, signature):
            raise PermissionError("SCSF_REQUEST_SIGNATURE_INVALID")
        nonce_key = "scsf_" + sha256_hex((device_id + ":" + nonce).encode("utf-8"))
        self.store.create("nonces", nonce_key, {
            "device_id": device_id, "protocol": SCSF_PROTOCOL, "seen_at": current,
            "expires_at": current + timedelta(minutes=5),
        }, replay_code="REPLAY_DETECTED")
        self.store.update("devices", device_id, {"last_seen_at": current})
        device["last_seen_at"] = current
        return device

    def heartbeat(self, *, device: Mapping[str, Any], data: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(data, Mapping) or data.get("schema") != SCSF_HEARTBEAT_SCHEMA:
            raise ValueError("SCSF_HEARTBEAT_SCHEMA_INVALID")
        if not isinstance(data.get("capabilities"), Mapping):
            raise ValueError("SCSF_HEARTBEAT_CAPABILITIES_INVALID")
        chain = str(data.get("chain_head") or "")
        if not _valid_hex(chain):
            raise ValueError("SCSF_HEARTBEAT_CHAIN_HEAD_INVALID")
        current = now or _now()
        self.store.update("devices", str(device["device_id"]), {
            "last_heartbeat_at": current, "last_chain_head": chain, "capabilities": dict(data["capabilities"]),
        })
        return {"state": "HEARTBEAT_ACCEPTED", "device_id": device["device_id"], "server_time": _z(current)}

    def queue_task(self, *, device_id: str, task: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        signer = self._require_signer()
        device = self.store.get("devices", device_id)
        if not device or device.get("protocol") != SCSF_PROTOCOL or device.get("disabled"):
            raise ValueError("SCSF_DEVICE_UNKNOWN")
        envelope = make_task_envelope(task, signer, now=now)
        verified = verify_task_envelope(envelope, signer.public_jwk(), now=now)
        task_id = str(verified["task_id"])
        current = now or _now()
        self.store.create_task(task_id, {
            "protocol": SCSF_PROTOCOL, "device_id": device_id, "task_id": task_id,
            "task": verified, "envelope": envelope, "created_at": current, "completed": False,
        })
        return envelope

    def poll(self, *, device: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(data, Mapping) or data.get("schema") != SCSF_POLL_SCHEMA:
            raise ValueError("SCSF_POLL_SCHEMA_INVALID")
        chain = str(data.get("chain_head") or "")
        if not _valid_hex(chain):
            raise ValueError("SCSF_POLL_CHAIN_HEAD_INVALID")
        rows = self.store.list_for("tasks", "device_id", str(device["device_id"]), limit=100)
        pending = [r for r in rows if r.get("protocol") == SCSF_PROTOCOL and not r.get("completed")]
        if not pending:
            return {"state": "EMPTY"}
        pending.sort(key=lambda r: str(r.get("task_id") or r.get("_id") or ""))
        envelope = pending[0].get("envelope")
        if not isinstance(envelope, Mapping):
            raise ValueError("SCSF_TASK_ENVELOPE_MISSING")
        return {"state": "PENDING", "envelope": dict(envelope)}

    def complete(self, *, device: Mapping[str, Any], attestation: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        if not isinstance(attestation, Mapping) or set(attestation) != {"schema", "device_id", "task_id", "payload_b64", "payload_sha256", "signature_b64", "issued_at"}:
            raise ValueError("SCSF_RESULT_ATTESTATION_FIELDS_INVALID")
        if attestation.get("schema") != SCSF_RESULT_ATTESTATION_SCHEMA:
            raise ValueError("SCSF_RESULT_ATTESTATION_SCHEMA_INVALID")
        device_id = str(attestation.get("device_id") or "")
        task_id = str(attestation.get("task_id") or "")
        if device_id != device.get("device_id"):
            raise PermissionError("SCSF_RESULT_DEVICE_MISMATCH")
        try:
            payload = _unb64u(str(attestation.get("payload_b64") or ""))
        except Exception as exc:
            raise ValueError("SCSF_RESULT_PAYLOAD_B64_INVALID") from exc
        if sha256_hex(payload) != attestation.get("payload_sha256"):
            raise ValueError("SCSF_RESULT_PAYLOAD_HASH_INVALID")
        if not ECDSASigner.verify_spki_b64(str(device.get("public_key_spki_b64") or ""), payload, str(attestation.get("signature_b64") or "")):
            raise PermissionError("SCSF_RESULT_SIGNATURE_INVALID")
        try:
            result = json.loads(payload)
        except Exception as exc:
            raise ValueError("SCSF_RESULT_PAYLOAD_JSON_INVALID") from exc
        if not isinstance(result, Mapping) or result.get("schema") != SCSF_RESULT_SCHEMA:
            raise ValueError("SCSF_RESULT_SCHEMA_INVALID")
        if result.get("device_id") != device_id or result.get("task_id") != task_id:
            raise PermissionError("SCSF_RESULT_BINDING_MISMATCH")
        if not _valid_hex(str(result.get("chain_head") or "")):
            raise ValueError("SCSF_RESULT_CHAIN_HEAD_INVALID")
        completed = _parse_time(result.get("completed_at"), "SCSF_RESULT_COMPLETED_AT")
        issued = _parse_time(attestation.get("issued_at"), "SCSF_RESULT_ISSUED_AT")
        if abs(current - completed) > timedelta(minutes=5) or abs(current - issued) > timedelta(minutes=5):
            raise PermissionError("SCSF_RESULT_STALE")
        duplicate = self.store.complete_task(task_id=task_id, device_id=device_id, attestation=dict(attestation), now=current)
        return {"state": "ACCEPTED", "task_id": task_id, "duplicate": bool(duplicate)}


def _json_body(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"{}")
    except Exception as exc:
        raise ValueError("JSON_BODY_REQUIRED") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def _error(exc: Exception, status: int = 401) -> JSONResponse:
    return JSONResponse({"state": "FAILED_CLOSED", "error": str(exc)}, status_code=status)


def _auth(runtime: SCSFRuntime, request: Request, body: bytes) -> dict[str, Any]:
    return runtime.verify_request(
        device_id=request.headers.get("x-fuse-device-id", ""), method=request.method,
        path=request.url.path, timestamp=request.headers.get("x-fuse-timestamp", ""),
        nonce=request.headers.get("x-fuse-nonce", ""), signature=request.headers.get("x-fuse-signature", ""),
        key_x=request.headers.get("x-fuse-key-x", ""), key_y=request.headers.get("x-fuse-key-y", ""), body=body,
    )


def bind_scsf_routes(server: Any, runtime: SCSFRuntime) -> None:
    @server.custom_route("/v1/agent/enroll", methods=["POST"], include_in_schema=False)
    async def scsf_enroll(request: Request):
        try:
            body = await request.body()
            return JSONResponse(runtime.enroll(_json_body(body)))
        except RuntimeError as exc:
            return _error(exc, status=503)
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/v1/agent/heartbeat", methods=["POST"], include_in_schema=False)
    async def scsf_heartbeat(request: Request):
        body = await request.body()
        try:
            data = _json_body(body); device = _auth(runtime, request, body)
            return JSONResponse(runtime.heartbeat(device=device, data=data))
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/v1/agent/poll", methods=["POST"], include_in_schema=False)
    async def scsf_poll(request: Request):
        body = await request.body()
        try:
            data = _json_body(body); device = _auth(runtime, request, body)
            return JSONResponse(runtime.poll(device=device, data=data))
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/v1/agent/complete", methods=["POST"], include_in_schema=False)
    async def scsf_complete(request: Request):
        body = await request.body()
        try:
            data = _json_body(body); device = _auth(runtime, request, body)
            return JSONResponse(runtime.complete(device=device, attestation=data))
        except Exception as exc:
            return _error(exc)


def build_agent_only_server(*, relay: FirestoreRelay, control_signer: P256SoftwareControlSigner | None = None):
    server = base_service.build_agent_only_server(relay=relay)
    bind_scsf_routes(server, SCSFRuntime(store=FirestoreSCSFStore(relay), control_signer=control_signer))
    return server


def server_from_env():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("MISSING_REQUIRED_ENV:GOOGLE_CLOUD_PROJECT")
    relay = FirestoreRelay(project=project, root_secret=os.environ.get("FUSE_RELAY_ROOT_SECRET"))
    # Deliberately no ephemeral/default signer. Durable control-key custody is a separate proof gate.
    return build_agent_only_server(relay=relay, control_signer=None)


def main() -> None:
    server_from_env().run(
        transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
        stateless_http=True, json_response=True,
    )


if __name__ == "__main__":
    main()
