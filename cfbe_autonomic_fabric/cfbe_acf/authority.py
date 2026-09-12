from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Any

from .models import ExecutionContract
from .store import FabricStore
from .util import canonical_json, digest_json, parse_utc, utc_now


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class FormationPermitAuthority:
    """Trusted permit verifier; issuance is exposed for isolated test/control planes only."""

    def __init__(self, *, store: FabricStore, signing_key: bytes, authority_id: str):
        if len(signing_key) < 32:
            raise ValueError("Formation signing key must contain at least 256 bits")
        if not authority_id.strip():
            raise ValueError("Formation authority identity required")
        self.store = store
        self._signing_key = signing_key
        self.authority_id = authority_id

    def issue(self, contract: ExecutionContract, *, ttl_seconds: int = 60) -> str:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds < 1 or ttl_seconds > 300:
            raise ValueError("permit TTL must be between 1 and 300 seconds")
        self.store.assert_mission_authority(
            mission_id=contract.mission_id,
            mission_version=contract.mission_version,
            authority_class=contract.authority_class,
            maximum_cost=contract.maximum_incremental_cost,
        )
        issued = parse_utc(utc_now())
        expires = issued + timedelta(seconds=ttl_seconds)
        claims = {
            "schema": "CFBE-ACF-FORMATION-PERMIT-V1",
            "permit_id": secrets.token_hex(16),
            "authority_id": self.authority_id,
            "contract_hash": contract.fingerprint,
            "mission_id": contract.mission_id,
            "mission_version": contract.mission_version,
            "action_id": contract.id,
            "provider_id": contract.provider_id,
            "route_fingerprint": contract.route_fingerprint,
            "executor_identity": contract.executor_identity,
            "authority_class": contract.authority_class,
            "maximum_incremental_cost": contract.maximum_incremental_cost,
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
        }
        payload = canonical_json(claims).encode("utf-8")
        signature = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        token = _encode(payload) + "." + _encode(signature)
        self.store.register_formation_permit(
            token_hash=digest_json(token),
            contract_hash=contract.fingerprint,
            mission_id=contract.mission_id,
            action_id=contract.id,
            issued_at=claims["issued_at"],
            expires_at=claims["expires_at"],
        )
        return token

    def validate(self, token: str, contract: ExecutionContract) -> dict[str, Any]:
        """Validate signature and immutable bindings without mutating permit state."""
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            payload = _decode(encoded_payload)
            supplied = _decode(encoded_signature)
            claims = json.loads(payload)
        except Exception as exc:
            raise PermissionError("malformed Formation permit") from exc
        expected = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise PermissionError("Formation permit signature invalid")
        expected_bindings = {
            "schema": "CFBE-ACF-FORMATION-PERMIT-V1",
            "authority_id": self.authority_id,
            "contract_hash": contract.fingerprint,
            "mission_id": contract.mission_id,
            "mission_version": contract.mission_version,
            "action_id": contract.id,
            "provider_id": contract.provider_id,
            "route_fingerprint": contract.route_fingerprint,
            "executor_identity": contract.executor_identity,
            "authority_class": contract.authority_class,
            "maximum_incremental_cost": contract.maximum_incremental_cost,
        }
        if any(claims.get(key) != value for key, value in expected_bindings.items()):
            raise PermissionError("Formation permit binding mismatch")
        if parse_utc(str(claims.get("expires_at", ""))) <= parse_utc(utc_now()):
            raise PermissionError("Formation permit expired")
        return claims
