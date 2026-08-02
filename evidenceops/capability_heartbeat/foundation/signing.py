"""Deterministic in-process HMAC signing; keys are injected and never persisted."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
from typing import Any

from .contracts import (
    HeartbeatEnvelope,
    MAX_OBSERVATION_AGE_SECONDS,
    Receipt,
    SignerIdentity,
    SUPPORTED_SIGNING_VERSIONS,
    canonical_json,
    digest,
    parse_utc,
)
from .errors import SignatureError
from .privacy import require_code
from .registry import NodeRecord
from .stop_control import StopControl

FINGERPRINT_DOMAIN = "KDV-CAPABILITY-HEARTBEAT-SIGNER-FINGERPRINT-0.1"
ENVELOPE_DOMAIN = "KDV-CAPABILITY-HEARTBEAT-ENVELOPE-0.1"
RECEIPT_DOMAIN = "KDV-CAPABILITY-HEARTBEAT-RECEIPT-0.1"


class RuntimeSigner:
    """A local verifier boundary, not a credential provider or authority source."""

    __slots__ = ("_key", "node_id", "identity")

    def __init__(
        self,
        key: bytes,
        *,
        node_id: str,
        key_id: str,
        signing_version: str = "HMAC-0.1",
        rotation_generation: int = 0,
    ) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise SignatureError("RUNTIME_SIGNING_MATERIAL_TOO_SHORT")
        require_code(node_id, field="node_id")
        require_code(key_id, field="key_id")
        require_code(signing_version, field="signing_version")
        if signing_version not in SUPPORTED_SIGNING_VERSIONS:
            raise SignatureError("UNSUPPORTED_RUNTIME_SIGNING_VERSION")
        if (
            isinstance(rotation_generation, bool)
            or not isinstance(rotation_generation, int)
            or rotation_generation < 0
        ):
            raise SignatureError("INVALID_SIGNER_ROTATION_GENERATION")
        self._key = bytes(key)
        self.node_id = node_id
        fingerprint_body = {
            "domain": FINGERPRINT_DOMAIN,
            "node_id": node_id,
            "key_id": key_id,
            "signing_version": signing_version,
            "rotation_generation": rotation_generation,
        }
        fingerprint = "sha256:" + hmac.new(
            self._key,
            canonical_json(fingerprint_body).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.identity = SignerIdentity(
            key_id=key_id,
            fingerprint=fingerprint,
            signing_version=signing_version,
            rotation_generation=rotation_generation,
        )

    @property
    def key_id(self) -> str:
        return self.identity.key_id

    def _sign_body(self, domain: str, body: dict[str, Any]) -> str:
        payload = {"domain": domain, "body": body}
        value = hmac.new(
            self._key,
            canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return "hmac-sha256:" + value

    def assert_binding(self, *, node_record: NodeRecord, stop_control: StopControl) -> None:
        if not isinstance(node_record, NodeRecord):
            raise SignatureError("REGISTERED_NODE_RECORD_REQUIRED")
        if self.node_id != node_record.node_id:
            raise SignatureError("SIGNER_NODE_BINDING_MISMATCH")
        if self.identity != node_record.signer_identity:
            raise SignatureError("SIGNER_REGISTRY_BINDING_MISMATCH")
        if self.identity.rotation_generation != node_record.control_generation:
            raise SignatureError("SIGNER_ROTATION_GENERATION_MISMATCH")
        stop_control.assert_current(node_record.control_generation)

    def sign_envelope(self, envelope: HeartbeatEnvelope) -> HeartbeatEnvelope:
        if self.node_id != envelope.signing_node_id or self.identity != envelope.signer_identity:
            raise SignatureError("ENVELOPE_SIGNER_BINDING_MISMATCH")
        unsigned = replace(envelope, signature="hmac-sha256:" + "0" * 64)
        return replace(
            unsigned,
            signature=self._sign_body(ENVELOPE_DOMAIN, unsigned.signing_body()),
        )

    def verify_envelope(
        self,
        envelope: HeartbeatEnvelope,
        *,
        node_record: NodeRecord,
        stop_control: StopControl,
    ) -> None:
        self.assert_binding(node_record=node_record, stop_control=stop_control)
        if envelope.signing_node_id != node_record.node_id:
            raise SignatureError("ENVELOPE_SIGNING_NODE_MISMATCH")
        if envelope.signer_identity != node_record.signer_identity:
            raise SignatureError("ENVELOPE_REGISTRY_IDENTITY_MISMATCH")
        expected = self._sign_body(ENVELOPE_DOMAIN, envelope.signing_body())
        if not hmac.compare_digest(expected, envelope.signature):
            raise SignatureError("INVALID_ENVELOPE_SIGNATURE")

    def sign_receipt(self, receipt: Receipt) -> Receipt:
        if self.node_id != receipt.accepting_node_id or self.identity != receipt.signer_identity:
            raise SignatureError("RECEIPT_SIGNER_BINDING_MISMATCH")
        unsigned = replace(receipt, signature="hmac-sha256:" + "0" * 64)
        return replace(
            unsigned,
            signature=self._sign_body(RECEIPT_DOMAIN, unsigned.signing_body()),
        )

    def verify_receipt(
        self,
        receipt: Receipt,
        *,
        accepted_envelope: HeartbeatEnvelope,
        destination_record: NodeRecord,
        stop_control: StopControl,
        now: str,
    ) -> None:
        self.assert_binding(node_record=destination_record, stop_control=stop_control)
        if receipt.accepting_node_id != destination_record.node_id:
            raise SignatureError("RECEIPT_DESTINATION_NODE_MISMATCH")
        if receipt.signer_identity != destination_record.signer_identity:
            raise SignatureError("RECEIPT_REGISTRY_IDENTITY_MISMATCH")
        current = parse_utc(now, field="now")
        accepted = parse_utc(receipt.accepted_at, field="accepted_at")
        observed = parse_utc(accepted_envelope.observed_at, field="observed_at")
        expires = parse_utc(accepted_envelope.expires_at, field="expires_at")
        destination_observed = parse_utc(destination_record.observed_at, field="destination_observed_at")
        destination_expires = parse_utc(destination_record.expires_at, field="destination_expires_at")
        if destination_observed > current or destination_expires <= current:
            raise SignatureError("RECEIPT_DESTINATION_REGISTRATION_NOT_FRESH")
        if accepted < destination_observed or accepted >= destination_expires:
            raise SignatureError("RECEIPT_OUTSIDE_DESTINATION_REGISTRATION_WINDOW")
        if accepted > current:
            raise SignatureError("RECEIPT_FUTURE_DATED")
        if accepted < observed or accepted >= expires:
            raise SignatureError("RECEIPT_OUTSIDE_ENVELOPE_WINDOW")
        if current >= expires or (current - accepted).total_seconds() > MAX_OBSERVATION_AGE_SECONDS:
            raise SignatureError("RECEIPT_STALE_OR_ENVELOPE_EXPIRED")
        scope_matches = all(
            (
                receipt.envelope_id == accepted_envelope.envelope_id,
                receipt.owner_code == accepted_envelope.owner_code == destination_record.owner_code,
                receipt.matter_code == accepted_envelope.matter_code == destination_record.matter_code,
                receipt.control_generation
                == accepted_envelope.control_generation
                == destination_record.control_generation
                == stop_control.generation,
                receipt.semantic_hash
                == digest(self.receipt_semantic_value(accepted_envelope, destination_record)),
            )
        )
        if not scope_matches:
            raise SignatureError("RECEIPT_ACCEPTED_ENVELOPE_SCOPE_MISMATCH")
        expected_receipt_id = digest(
            {"kind": "HEARTBEAT_RECEIPT", "identity": receipt.identity_body()}
        )
        if receipt.receipt_id != expected_receipt_id:
            raise SignatureError("RECEIPT_IDENTITY_BINDING_MISMATCH")
        expected = self._sign_body(RECEIPT_DOMAIN, receipt.signing_body())
        if not hmac.compare_digest(expected, receipt.signature):
            raise SignatureError("INVALID_RECEIPT_SIGNATURE")

    def make_receipt(
        self,
        *,
        envelope: HeartbeatEnvelope,
        accepting_record: NodeRecord,
        stop_control: StopControl,
        accepted_at: str,
    ) -> Receipt:
        self.assert_binding(node_record=accepting_record, stop_control=stop_control)
        if not all(
            (
                envelope.owner_code == accepting_record.owner_code,
                envelope.matter_code == accepting_record.matter_code,
                envelope.control_generation
                == accepting_record.control_generation
                == stop_control.generation,
            )
        ):
            raise SignatureError("RECEIPT_CREATION_SCOPE_MISMATCH")
        accepted = parse_utc(accepted_at, field="accepted_at")
        observed = parse_utc(envelope.observed_at, field="observed_at")
        expires = parse_utc(envelope.expires_at, field="expires_at")
        if accepted < observed or accepted >= expires:
            raise SignatureError("RECEIPT_CREATION_OUTSIDE_ENVELOPE_WINDOW")
        semantic_hash = digest(self.receipt_semantic_value(envelope, accepting_record))
        placeholder_id = "sha256:" + "0" * 64
        placeholder = "hmac-sha256:" + "0" * 64
        provisional = Receipt(
            receipt_id=placeholder_id,
            envelope_id=envelope.envelope_id,
            accepting_node_id=accepting_record.node_id,
            signer_identity=self.identity,
            owner_code=envelope.owner_code,
            matter_code=envelope.matter_code,
            accepted_at=accepted_at,
            control_generation=envelope.control_generation,
            semantic_hash=semantic_hash,
            signature=placeholder,
        )
        receipt_id = digest(
            {"kind": "HEARTBEAT_RECEIPT", "identity": provisional.identity_body()}
        )
        return self.sign_receipt(replace(provisional, receipt_id=receipt_id))

    @staticmethod
    def receipt_semantic_value(
        envelope: HeartbeatEnvelope,
        destination_record: NodeRecord,
    ) -> dict[str, Any]:
        """Canonical acceptance fact independently recomputed by receipt verifiers."""
        return {
            "accepted": True,
            "destination_node_id": destination_record.node_id,
            "destination_signer_identity": destination_record.signer_identity,
            "envelope_id": envelope.envelope_id,
            "owner_code": envelope.owner_code,
            "matter_code": envelope.matter_code,
            "control_generation": envelope.control_generation,
        }
