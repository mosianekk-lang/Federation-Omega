from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Mapping

from google.api_core.exceptions import AlreadyExists
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import mcp_service as base_service
from .firestore_relay import FirestoreRelay
from .relay_protocol import canonical_json, sha256_hex, signing_payload, _parse_utc_z, _require_id
from .trust_spine_v21 import ECDSASigner, PostureEnvelope, parse_utc, relay_mode

PAIRING_GRANT_SCHEMA = "FUSE-WINDOWS-PAIRING-GRANT-V1"
PAIRING_CHALLENGE_SCHEMA = "FUSE-WINDOWS-PAIRING-CHALLENGE-V1"
PAIRING_CREDENTIAL_SCHEMA = "FUSE-WINDOWS-PAIRING-CREDENTIAL-V1"
BOUND_REQUEST_SCHEMA = "FUSE-WINDOWS-BOUND-REQUEST-V1"
IDENTITY_SCHEMA = "FUSE-WINDOWS-SHORT-IDENTITY-V1"
EXECUTION_LEASE_SCHEMA = "FUSE-WINDOWS-EXECUTION-LEASE-V2"
RESULT_ATTESTATION_SCHEMA = "FUSE-WINDOWS-RESULT-ATTESTATION-V1"
POSTURE_SCHEMA = "FUSE-WINDOWS-POSTURE-V1"
PAIRING_AUTH_MODE = "ECDSA_P256_PAIRING_V1"
PAIRING_ROUTES = frozenset({
    "/agent/enroll/start",
    "/agent/enroll/complete",
    "/agent/identity/renew",
    "/agent/posture",
    "/agent/runtime/poll",
    "/agent/runtime/complete",
})
ZERO_CHAIN = "0" * 64


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _token(prefix: str, size: int = 24) -> str:
    return prefix + base64.urlsafe_b64encode(secrets.token_bytes(size)).decode("ascii").rstrip("=")


def _dt(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(label + "_TIMEZONE_REQUIRED")
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        return _parse_utc_z(value, label)
    raise ValueError(label + "_INVALID")


def _valid_hex(value: str, length: int) -> bool:
    if len(value) != length:
        return False
    try:
        int(value, 16)
        return True
    except Exception:
        return False


def _validate_p256_spki(value: str) -> None:
    if not value:
        raise ValueError("DEVICE_PUBLIC_KEY_REQUIRED")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        key = serialization.load_der_public_key(raw)
        if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
            raise ValueError("DEVICE_PUBLIC_KEY_INVALID")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("DEVICE_PUBLIC_KEY_INVALID") from exc


class FirestorePairingStore:
    """Adapter over the existing relay namespace; no second datastore or authority root."""

    def __init__(self, relay: FirestoreRelay):
        self.relay = relay

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        snap = self.relay._collection(collection).document(key).get()
        if not snap.exists:
            return None
        return dict(snap.to_dict() or {})

    def create(self, collection: str, key: str, value: Mapping[str, Any], *, replay_code: str) -> None:
        try:
            self.relay._collection(collection).document(key).create(dict(value))
        except AlreadyExists as exc:
            raise ValueError(replay_code) from exc

    def update(self, collection: str, key: str, value: Mapping[str, Any]) -> None:
        self.relay._collection(collection).document(key).update(dict(value))


class PairingRuntime:
    """Bounded pairing/fencing layer for the existing outbound-only relay.

    Device private keys never enter this object. Durable state remains in the existing
    relay namespace and every workstation interaction is outbound HTTPS to the relay.
    """

    def __init__(
        self,
        *,
        relay: Any,
        source_epoch: str,
        policy_epoch: str,
        store: Any | None = None,
        pairing_ttl_seconds: int = 300,
        challenge_ttl_seconds: int = 120,
        identity_ttl_seconds: int = 600,
        request_skew_seconds: int = 60,
    ) -> None:
        self.relay = relay
        self.store = store or FirestorePairingStore(relay)
        self.source_epoch = str(source_epoch or "")
        self.policy_epoch = str(policy_epoch or "")
        self.pairing_ttl = timedelta(seconds=pairing_ttl_seconds)
        self.challenge_ttl = timedelta(seconds=challenge_ttl_seconds)
        self.identity_ttl = timedelta(seconds=identity_ttl_seconds)
        self.request_skew = timedelta(seconds=request_skew_seconds)
        if min(pairing_ttl_seconds, challenge_ttl_seconds, identity_ttl_seconds, request_skew_seconds) <= 0:
            raise ValueError("PAIRING_TTL_INVALID")

    def _require_epochs_configured(self) -> None:
        if not self.source_epoch:
            raise RuntimeError("PAIRING_SOURCE_EPOCH_UNCONFIGURED")
        if not self.policy_epoch:
            raise RuntimeError("PAIRING_POLICY_EPOCH_UNCONFIGURED")

    def issue_pairing_grant(self, *, now: datetime | None = None) -> dict[str, Any]:
        self._require_epochs_configured()
        current = now or _now()
        grant_id = _token("pgr_", 12)
        token = _token("pgt_", 32)
        expires = current + self.pairing_ttl
        self.store.create(
            "pairing_grants",
            grant_id,
            {
                "token_digest": sha256_hex(token.encode()),
                "source_epoch": self.source_epoch,
                "policy_epoch": self.policy_epoch,
                "created_at": current,
                "expires_at": expires,
                "used": False,
            },
            replay_code="PAIRING_GRANT_ID_COLLISION",
        )
        return {
            "schema": PAIRING_GRANT_SCHEMA,
            "pairing_grant_id": grant_id,
            "pairing_token": token,
            "source_epoch": self.source_epoch,
            "policy_epoch": self.policy_epoch,
            "issued_at": _z(current),
            "expires_at": _z(expires),
            "max_uses": 1,
        }

    def _grant(self, grant_id: str, token: str, *, now: datetime) -> dict[str, Any]:
        _require_id(grant_id, "PAIRING_GRANT_ID")
        grant = self.store.get("pairing_grants", grant_id)
        if not grant:
            raise ValueError("PAIRING_GRANT_UNKNOWN")
        if grant.get("used"):
            raise ValueError("PAIRING_GRANT_ALREADY_USED")
        if now >= _dt(grant.get("expires_at"), "PAIRING_GRANT_EXPIRES_AT"):
            raise ValueError("PAIRING_GRANT_EXPIRED")
        if not hmac.compare_digest(sha256_hex(str(token).encode()), str(grant.get("token_digest") or "")):
            raise ValueError("PAIRING_GRANT_TOKEN_INVALID")
        if grant.get("source_epoch") != self.source_epoch:
            raise PermissionError("SOURCE_EPOCH_FENCE")
        if grant.get("policy_epoch") != self.policy_epoch:
            raise PermissionError("POLICY_EPOCH_FENCE")
        return grant

    def start_pairing(
        self,
        *,
        pairing_grant_id: str,
        pairing_token: str,
        device_label: str,
        public_key_spki_b64: str,
        device_generation: int,
        source_epoch: str,
        policy_epoch: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._require_epochs_configured()
        current = now or _now()
        self._grant(pairing_grant_id, pairing_token, now=current)
        _require_id(device_label, "DEVICE_LABEL")
        _validate_p256_spki(public_key_spki_b64)
        if int(device_generation) != 1:
            raise PermissionError("DEVICE_GENERATION_FENCE")
        if source_epoch != self.source_epoch:
            raise PermissionError("SOURCE_EPOCH_FENCE")
        if policy_epoch != self.policy_epoch:
            raise PermissionError("POLICY_EPOCH_FENCE")
        challenge_id = _token("pch_", 12)
        expires = current + self.challenge_ttl
        payload = {
            "schema": PAIRING_CHALLENGE_SCHEMA,
            "challenge_id": challenge_id,
            "pairing_grant_id": pairing_grant_id,
            "device_label_sha256": sha256_hex(device_label.encode()),
            "public_key_spki_sha256": sha256_hex(public_key_spki_b64.encode()),
            "device_generation": 1,
            "source_epoch": self.source_epoch,
            "policy_epoch": self.policy_epoch,
            "nonce": _token("pcn_", 24),
            "issued_at": _z(current),
            "expires_at": _z(expires),
        }
        self.store.create(
            "pairing_challenges",
            challenge_id,
            {
                "payload": payload,
                "public_key_spki_b64": public_key_spki_b64,
                "expires_at": expires,
                "used": False,
            },
            replay_code="PAIRING_CHALLENGE_ID_COLLISION",
        )
        return {"state": "CHALLENGE_ISSUED", "challenge": payload}

    def complete_pairing(
        self,
        *,
        pairing_grant_id: str,
        pairing_token: str,
        challenge_id: str,
        challenge_signature_b64: str,
        device_label: str,
        public_key_spki_b64: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._require_epochs_configured()
        current = now or _now()
        self._grant(pairing_grant_id, pairing_token, now=current)
        _require_id(challenge_id, "PAIRING_CHALLENGE_ID")
        _require_id(device_label, "DEVICE_LABEL")
        _validate_p256_spki(public_key_spki_b64)
        challenge = self.store.get("pairing_challenges", challenge_id)
        if not challenge:
            raise ValueError("PAIRING_CHALLENGE_UNKNOWN")
        if challenge.get("used"):
            raise ValueError("PAIRING_CHALLENGE_ALREADY_USED")
        if current >= _dt(challenge.get("expires_at"), "PAIRING_CHALLENGE_EXPIRES_AT"):
            raise ValueError("PAIRING_CHALLENGE_EXPIRED")
        payload = challenge.get("payload")
        if not isinstance(payload, Mapping) or payload.get("challenge_id") != challenge_id:
            raise ValueError("PAIRING_CHALLENGE_MALFORMED")
        if payload.get("pairing_grant_id") != pairing_grant_id:
            raise PermissionError("PAIRING_CHALLENGE_GRANT_MISMATCH")
        if payload.get("device_label_sha256") != sha256_hex(device_label.encode()):
            raise PermissionError("PAIRING_CHALLENGE_DEVICE_MISMATCH")
        if payload.get("public_key_spki_sha256") != sha256_hex(public_key_spki_b64.encode()):
            raise PermissionError("PAIRING_CHALLENGE_KEY_MISMATCH")
        if challenge.get("public_key_spki_b64") != public_key_spki_b64:
            raise PermissionError("PAIRING_CHALLENGE_KEY_MISMATCH")
        if payload.get("source_epoch") != self.source_epoch:
            raise PermissionError("SOURCE_EPOCH_FENCE")
        if payload.get("policy_epoch") != self.policy_epoch:
            raise PermissionError("POLICY_EPOCH_FENCE")
        if not ECDSASigner.verify_spki_b64(public_key_spki_b64, canonical_json(dict(payload)), challenge_signature_b64):
            raise PermissionError("PAIRING_POSSESSION_PROOF_INVALID")

        device_id = "dev_" + sha256_hex(canonical_json({
            "pairing_grant_id": pairing_grant_id,
            "device_label_sha256": payload["device_label_sha256"],
        }))[:24]
        self.store.create(
            "pairing_consumptions",
            pairing_grant_id,
            {"device_id": device_id, "consumed_at": current},
            replay_code="PAIRING_GRANT_REPLAY",
        )
        identity_id = _token("idn_", 18)
        identity_expires = current + self.identity_ttl
        self.store.create(
            "devices",
            device_id,
            {
                "device_id": device_id,
                "label_sha256": payload["device_label_sha256"],
                "public_key_spki_b64": public_key_spki_b64,
                "auth_mode": PAIRING_AUTH_MODE,
                "pairing_version": 1,
                "device_generation": 1,
                "source_epoch": self.source_epoch,
                "policy_epoch": self.policy_epoch,
                "current_identity_id": identity_id,
                "identity_expires_at": identity_expires,
                "identity_rotation": 0,
                "previous_identity_sha256": None,
                "receipt_chain_head": ZERO_CHAIN,
                "receipt_chain_sequence": 0,
                "enrolled_at": current,
                "last_seen_at": None,
                "last_posture_at": None,
                "posture_score": None,
                "disabled": False,
            },
            replay_code="PAIRING_DEVICE_ALREADY_EXISTS",
        )
        self.store.update("pairing_grants", pairing_grant_id, {"used": True, "used_at": current, "device_id": device_id})
        self.store.update("pairing_challenges", challenge_id, {"used": True, "used_at": current, "device_id": device_id})
        return {
            "state": "PAIRED",
            "credential": {
                "schema": PAIRING_CREDENTIAL_SCHEMA,
                "device_id": device_id,
                "device_generation": 1,
                "public_key_spki_b64": public_key_spki_b64,
                "auth_mode": PAIRING_AUTH_MODE,
                "source_epoch": self.source_epoch,
                "policy_epoch": self.policy_epoch,
            },
            "identity": self._identity_public(device_id=device_id, identity_id=identity_id, expires_at=identity_expires, rotation=0),
            "recovery_cursor": ZERO_CHAIN,
        }

    def _identity_public(self, *, device_id: str, identity_id: str, expires_at: datetime, rotation: int) -> dict[str, Any]:
        return {
            "schema": IDENTITY_SCHEMA,
            "identity_id": identity_id,
            "device_id": device_id,
            "device_generation": 1,
            "source_epoch": self.source_epoch,
            "policy_epoch": self.policy_epoch,
            "rotation": int(rotation),
            "expires_at": _z(expires_at),
        }

    def verify_bound_request(
        self,
        *,
        device_id: str,
        method: str,
        path: str,
        timestamp: str,
        nonce: str,
        signature: str,
        body: bytes,
        binding: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._require_epochs_configured()
        current = now or _now()
        _require_id(device_id, "DEVICE_ID")
        _require_id(nonce, "NONCE")
        signed_at = _parse_utc_z(timestamp, "REQUEST_TIMESTAMP")
        if abs(current - signed_at) > self.request_skew:
            raise ValueError("REQUEST_TIMESTAMP_OUTSIDE_WINDOW")
        device = self.store.get("devices", device_id)
        if not device or device.get("disabled"):
            raise ValueError("DEVICE_UNKNOWN")
        if device.get("auth_mode") != PAIRING_AUTH_MODE:
            raise PermissionError("PAIRING_AUTH_MODE_REQUIRED")
        public_key = str(device.get("public_key_spki_b64") or "")
        payload = signing_payload(method=method, path=path, timestamp=timestamp, nonce=nonce, body=body)
        if not ECDSASigner.verify_spki_b64(public_key, payload, signature):
            raise PermissionError("REQUEST_SIGNATURE_INVALID")
        nonce_id = sha256_hex((device_id + ":" + nonce).encode())
        self.store.create(
            "nonces",
            nonce_id,
            {"device_id": device_id, "seen_at": current, "expires_at": current + timedelta(minutes=5)},
            replay_code="REPLAY_DETECTED",
        )
        if not isinstance(binding, Mapping) or binding.get("schema") != BOUND_REQUEST_SCHEMA:
            raise ValueError("BOUND_REQUEST_REQUIRED")
        if binding.get("device_id") != device_id:
            raise PermissionError("DEVICE_ID_FENCE")
        if int(binding.get("device_generation", -1)) != int(device.get("device_generation", -2)):
            raise PermissionError("DEVICE_GENERATION_FENCE")
        if binding.get("source_epoch") != self.source_epoch or device.get("source_epoch") != self.source_epoch:
            raise PermissionError("SOURCE_EPOCH_FENCE")
        if binding.get("policy_epoch") != self.policy_epoch or device.get("policy_epoch") != self.policy_epoch:
            raise PermissionError("POLICY_EPOCH_FENCE")
        if binding.get("identity_id") != device.get("current_identity_id"):
            raise PermissionError("IDENTITY_FENCE")
        if current >= _dt(device.get("identity_expires_at"), "IDENTITY_EXPIRES_AT"):
            raise PermissionError("IDENTITY_EXPIRED")
        cursor = str(binding.get("recovery_cursor") or "")
        if not _valid_hex(cursor, 64):
            raise ValueError("RECOVERY_CURSOR_INVALID")
        self.store.update("devices", device_id, {"last_seen_at": current})
        device["last_seen_at"] = current
        return device

    def renew_identity(self, *, device: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        device_id = str(device["device_id"])
        old_id = str(device["current_identity_id"])
        new_id = _token("idn_", 18)
        rotation = int(device.get("identity_rotation") or 0) + 1
        expires = current + self.identity_ttl
        self.store.update(
            "devices",
            device_id,
            {
                "previous_identity_sha256": sha256_hex(old_id.encode()),
                "current_identity_id": new_id,
                "identity_expires_at": expires,
                "identity_rotation": rotation,
            },
        )
        return self._identity_public(device_id=device_id, identity_id=new_id, expires_at=expires, rotation=rotation)

    def accept_posture(self, *, device: Mapping[str, Any], posture: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        if not isinstance(posture, Mapping) or posture.get("schema") != POSTURE_SCHEMA:
            raise ValueError("POSTURE_SCHEMA_INVALID")
        try:
            p = PostureEnvelope(**dict(posture))
        except Exception as exc:
            raise ValueError("POSTURE_MALFORMED") from exc
        if p.device_id != device.get("device_id"):
            raise PermissionError("POSTURE_DEVICE_FENCE")
        if int(p.device_generation) != int(device.get("device_generation")):
            raise PermissionError("POSTURE_GENERATION_FENCE")
        if p.tpm_state != "TPM_PLATFORM":
            raise PermissionError("TPM_PLATFORM_REQUIRED")
        if p.key_status != "ACTIVE":
            raise PermissionError("POSTURE_KEY_NOT_ACTIVE")
        if not _valid_hex(str(p.agent_sha256), 64):
            raise ValueError("POSTURE_AGENT_SHA256_INVALID")
        observed = parse_utc(p.observed_at)
        if abs(current - observed) > timedelta(minutes=5):
            raise PermissionError("POSTURE_STALE")
        score = p.score()
        self.store.update(
            "devices",
            str(device["device_id"]),
            {"last_posture_at": current, "posture_score": score, "last_posture": dict(posture)},
        )
        return {"state": "POSTURE_ACCEPTED", "posture_score": score, "observed_at": p.observed_at}

    def poll(self, *, device: Mapping[str, Any], binding: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        head = str(device.get("receipt_chain_head") or ZERO_CHAIN)
        if binding.get("recovery_cursor") != head:
            raise PermissionError("RECOVERY_CURSOR_MISMATCH")
        item = self.relay.poll(device_id=str(device["device_id"]), now=current)
        if item is None:
            return {"state": "EMPTY", "recovery_cursor": head}
        task, lease = item
        return {
            "state": "LEASED",
            "task": task,
            "lease": {
                "schema": EXECUTION_LEASE_SCHEMA,
                "task_id": lease.task_id,
                "device_id": lease.device_id,
                "device_generation": int(device["device_generation"]),
                "source_epoch": self.source_epoch,
                "policy_epoch": self.policy_epoch,
                "lease_token": lease.lease_token,
                "leased_at": lease.leased_at,
                "expires_at": lease.expires_at,
            },
            "recovery_cursor": head,
        }

    def complete(
        self,
        *,
        device: Mapping[str, Any],
        binding: Mapping[str, Any],
        task_id: str,
        lease: Mapping[str, Any],
        receipt: Mapping[str, Any],
        result_attestation: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or _now()
        device_id = str(device["device_id"])
        if not isinstance(lease, Mapping) or lease.get("schema") != EXECUTION_LEASE_SCHEMA:
            raise ValueError("EXECUTION_LEASE_MALFORMED")
        if lease.get("task_id") != task_id or lease.get("device_id") != device_id:
            raise PermissionError("LEASE_TASK_DEVICE_FENCE")
        if int(lease.get("device_generation", -1)) != int(device["device_generation"]):
            raise PermissionError("LEASE_GENERATION_FENCE")
        if lease.get("source_epoch") != self.source_epoch:
            raise PermissionError("LEASE_SOURCE_FENCE")
        if lease.get("policy_epoch") != self.policy_epoch:
            raise PermissionError("LEASE_POLICY_FENCE")
        if current >= _dt(lease.get("expires_at"), "LEASE_EXPIRES_AT"):
            raise PermissionError("LEASE_EXPIRED")
        lease_token = str(lease.get("lease_token") or "")
        if not lease_token:
            raise ValueError("LEASE_TOKEN_REQUIRED")
        if not isinstance(receipt, Mapping):
            raise ValueError("RECEIPT_OBJECT_REQUIRED")
        if not isinstance(result_attestation, Mapping):
            raise ValueError("RESULT_ATTESTATION_REQUIRED")

        att = dict(result_attestation)
        sig = str(att.pop("signature_b64", ""))
        if att.get("schema") != RESULT_ATTESTATION_SCHEMA:
            raise ValueError("RESULT_ATTESTATION_SCHEMA_INVALID")
        expected = {
            "device_id": device_id,
            "device_generation": int(device["device_generation"]),
            "identity_id": str(device["current_identity_id"]),
            "task_id": task_id,
            "source_epoch": self.source_epoch,
            "policy_epoch": self.policy_epoch,
        }
        for key, value in expected.items():
            if att.get(key) != value:
                raise PermissionError("RESULT_ATTESTATION_" + key.upper() + "_FENCE")
        if att.get("result_sha256") != receipt.get("result_sha256"):
            raise PermissionError("RESULT_ATTESTATION_RESULT_HASH_MISMATCH")
        receipt_sha = sha256_hex(canonical_json(dict(receipt)))
        if att.get("receipt_sha256") != receipt_sha:
            raise PermissionError("RESULT_ATTESTATION_RECEIPT_HASH_MISMATCH")
        prev = str(att.get("previous_receipt_sha256") or "")
        if not _valid_hex(prev, 64):
            raise ValueError("RESULT_ATTESTATION_PREDECESSOR_INVALID")
        if str(binding.get("recovery_cursor") or "") != prev:
            raise PermissionError("RECOVERY_CURSOR_MISMATCH")
        issued = _parse_utc_z(str(att.get("issued_at") or ""), "RESULT_ATTESTATION_ISSUED_AT")
        if abs(current - issued) > timedelta(minutes=5):
            raise PermissionError("RESULT_ATTESTATION_STALE")
        public_key = str(device.get("public_key_spki_b64") or "")
        if not ECDSASigner.verify_spki_b64(public_key, canonical_json(att), sig):
            raise PermissionError("RESULT_ATTESTATION_SIGNATURE_INVALID")
        att_with_sig = dict(att)
        att_with_sig["signature_b64"] = sig
        att_hash = sha256_hex(canonical_json(att_with_sig))
        head = str(device.get("receipt_chain_head") or ZERO_CHAIN)
        duplicate = head == att_hash
        if not duplicate and prev != head:
            raise PermissionError("RECEIPT_CHAIN_PREDECESSOR_INVALID")

        stored_receipt = dict(receipt)
        stored_receipt["device_result_attestation"] = att_with_sig
        stored_receipt["device_result_attestation_sha256"] = att_hash
        stored = self.relay.complete(
            device_id=device_id,
            task_id=task_id,
            lease_token=lease_token,
            receipt=stored_receipt,
        )
        if not duplicate:
            self.store.update(
                "devices",
                device_id,
                {
                    "receipt_chain_head": att_hash,
                    "receipt_chain_sequence": int(device.get("receipt_chain_sequence") or 0) + 1,
                    "last_completed_task_id": task_id,
                    "last_completed_at": current,
                },
            )
        return {"state": "ACCEPTED", "task_id": stored["task_id"], "recovery_cursor": att_hash, "duplicate": duplicate}


def _runtime_from_env(relay: Any) -> PairingRuntime:
    return PairingRuntime(
        relay=relay,
        source_epoch=os.environ.get("FUSE_WINDOWS_SOURCE_EPOCH", ""),
        policy_epoch=os.environ.get("FUSE_WINDOWS_POLICY_EPOCH", ""),
    )


def _error(exc: Exception, status: int = 401) -> JSONResponse:
    return JSONResponse({"state": "FAILED_CLOSED", "error": str(exc)}, status_code=status)


def _body_json(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"{}")
    except Exception as exc:
        raise ValueError("JSON_BODY_REQUIRED") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def _bound(runtime: PairingRuntime, request: Request, body: bytes, data: Mapping[str, Any]) -> dict[str, Any]:
    return runtime.verify_bound_request(
        device_id=request.headers.get("x-fuse-device-id", ""),
        method=request.method,
        path=request.url.path,
        timestamp=request.headers.get("x-fuse-timestamp", ""),
        nonce=request.headers.get("x-fuse-nonce", ""),
        signature=request.headers.get("x-fuse-signature", ""),
        body=body,
        binding=data.get("binding") or {},
    )


def bind_pairing_routes(server: MCPServer, runtime: PairingRuntime) -> None:
    @server.custom_route("/agent/enroll/start", methods=["POST"], include_in_schema=False)
    async def pairing_start(request: Request):
        try:
            d = await request.json()
            out = runtime.start_pairing(
                pairing_grant_id=str(d.get("pairing_grant_id") or ""),
                pairing_token=str(d.get("pairing_token") or ""),
                device_label=str(d.get("device_label") or ""),
                public_key_spki_b64=str(d.get("public_key_spki_b64") or ""),
                device_generation=int(d.get("device_generation", 0)),
                source_epoch=str(d.get("source_epoch") or ""),
                policy_epoch=str(d.get("policy_epoch") or ""),
            )
            return JSONResponse(out, status_code=201)
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/agent/enroll/complete", methods=["POST"], include_in_schema=False)
    async def pairing_complete(request: Request):
        try:
            d = await request.json()
            out = runtime.complete_pairing(
                pairing_grant_id=str(d.get("pairing_grant_id") or ""),
                pairing_token=str(d.get("pairing_token") or ""),
                challenge_id=str(d.get("challenge_id") or ""),
                challenge_signature_b64=str(d.get("challenge_signature_b64") or ""),
                device_label=str(d.get("device_label") or ""),
                public_key_spki_b64=str(d.get("public_key_spki_b64") or ""),
            )
            return JSONResponse(out, status_code=201)
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/agent/identity/renew", methods=["POST"], include_in_schema=False)
    async def identity_renew(request: Request):
        body = await request.body()
        try:
            d = _body_json(body)
            device = _bound(runtime, request, body, d)
            return JSONResponse({"state": "IDENTITY_RENEWED", "identity": runtime.renew_identity(device=device)})
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/agent/posture", methods=["POST"], include_in_schema=False)
    async def posture(request: Request):
        body = await request.body()
        try:
            d = _body_json(body)
            device = _bound(runtime, request, body, d)
            return JSONResponse(runtime.accept_posture(device=device, posture=d.get("posture") or {}))
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/agent/runtime/poll", methods=["POST"], include_in_schema=False)
    async def runtime_poll(request: Request):
        body = await request.body()
        try:
            d = _body_json(body)
            device = _bound(runtime, request, body, d)
            return JSONResponse(runtime.poll(device=device, binding=d.get("binding") or {}))
        except Exception as exc:
            return _error(exc)

    @server.custom_route("/agent/runtime/complete", methods=["POST"], include_in_schema=False)
    async def runtime_complete(request: Request):
        body = await request.body()
        try:
            d = _body_json(body)
            device = _bound(runtime, request, body, d)
            return JSONResponse(runtime.complete(
                device=device,
                binding=d.get("binding") or {},
                task_id=str(d.get("task_id") or ""),
                lease=d.get("lease") or {},
                receipt=d.get("receipt") or {},
                result_attestation=d.get("result_attestation") or {},
            ))
        except Exception as exc:
            return _error(exc)


def build_server(*, relay: Any, issuer: str, resource_url: str, jwks_url: str) -> MCPServer:
    server = base_service.build_server(relay=relay, issuer=issuer, resource_url=resource_url, jwks_url=jwks_url)
    runtime = _runtime_from_env(relay)
    bind_pairing_routes(server, runtime)

    @server.tool(
        title="Issue TPM/CNG Windows pairing grant",
        description="Issue a five-minute single-use possession-proof pairing grant.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )
    def fuse_issue_windows_pairing_grant() -> dict[str, Any]:
        base_service._require_scope()
        return runtime.issue_pairing_grant()

    return server


def build_agent_only_server(*, relay: Any) -> MCPServer:
    server = base_service.build_agent_only_server(relay=relay)
    bind_pairing_routes(server, _runtime_from_env(relay))
    return server


def server_from_env() -> MCPServer:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        raise RuntimeError("MISSING_REQUIRED_ENV:GOOGLE_CLOUD_PROJECT")
    relay = FirestoreRelay(project=os.environ["GOOGLE_CLOUD_PROJECT"], root_secret=os.environ.get("FUSE_RELAY_ROOT_SECRET"))
    issuer = os.environ.get("FUSE_OIDC_ISSUER")
    jwks = os.environ.get("FUSE_OIDC_JWKS_URL")
    mode = relay_mode(oidc_issuer=issuer, oidc_jwks_url=jwks)
    if mode == "AGENT_ONLY_BOOTSTRAP":
        return build_agent_only_server(relay=relay)
    resource = os.environ.get("FUSE_MCP_RESOURCE_URL")
    if not resource:
        raise RuntimeError("MISSING_REQUIRED_ENV:FUSE_MCP_RESOURCE_URL")
    return build_server(relay=relay, issuer=str(issuer), resource_url=resource, jwks_url=str(jwks))


def main() -> None:
    server_from_env().run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
