from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Callable

from .errors import ExpiredHandle, InvalidHandle
from .models import CapabilityClaims, CapabilityRequest


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise InvalidHandle("capability handle is malformed") from exc


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


class CapabilityTokenCodec:
    """Issues compact, HMAC-authenticated handles; the key is injected, never stored."""

    def __init__(
        self,
        key: bytes | bytearray,
        *,
        key_id: str,
        clock: Callable[[], float] = time.time,
        maximum_ttl: int = 900,
        clock_skew: int = 30,
    ) -> None:
        if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
            raise ValueError("token key must contain at least 32 bytes")
        if not key_id or len(key_id) > 128:
            raise ValueError("key_id is invalid")
        self._key = bytes(key)
        self.key_id = key_id
        self._clock = clock
        self.maximum_ttl = maximum_ttl
        self.clock_skew = clock_skew

    def issue(self, request: CapabilityRequest) -> tuple[str, CapabilityClaims]:
        now = int(self._clock())
        ttl = min(request.ttl_seconds, self.maximum_ttl)
        claims = CapabilityClaims(
            token_id=secrets.token_urlsafe(18),
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            operation_id=request.operation_id,
            subject=request.identity.subject,
            audience=request.identity.audience,
            authority=request.identity.authority.value,
            resource=request.secret.reference_id,
            connector=request.connector,
            action=request.action,
            issued_at=now,
            expires_at=now + ttl,
            nonce=secrets.token_urlsafe(18),
        )
        header = {"alg": "HS256", "kid": self.key_id, "typ": "SCB-1"}
        signing_input = f"{_b64encode(_canonical(header))}.{_b64encode(_canonical(claims.as_dict()))}"
        signature = hmac.new(self._key, signing_input.encode("ascii"), hashlib.sha256).digest()
        return f"{signing_input}.{_b64encode(signature)}", claims

    def verify(self, token: str, *, expected_subject: str, expected_audience: str) -> CapabilityClaims:
        try:
            encoded_header, encoded_claims, encoded_signature = token.split(".")
            header = json.loads(_b64decode(encoded_header))
            raw_claims = json.loads(_b64decode(encoded_claims))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidHandle("capability handle is malformed") from exc
        if header != {"alg": "HS256", "kid": self.key_id, "typ": "SCB-1"}:
            raise InvalidHandle("capability handle header is invalid")
        expected = hmac.new(
            self._key,
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(encoded_signature)):
            raise InvalidHandle("capability handle signature is invalid")
        try:
            claims = CapabilityClaims(**raw_claims)
        except (TypeError, ValueError) as exc:
            raise InvalidHandle("capability claims are invalid") from exc
        now = int(self._clock())
        if claims.issued_at > now + self.clock_skew:
            raise InvalidHandle("capability handle is not yet valid")
        if claims.expires_at <= now:
            raise ExpiredHandle("capability handle has expired")
        if claims.expires_at - claims.issued_at > self.maximum_ttl:
            raise InvalidHandle("capability handle exceeds maximum lifetime")
        if not hmac.compare_digest(claims.subject, expected_subject):
            raise InvalidHandle("capability subject mismatch")
        if not hmac.compare_digest(claims.audience, expected_audience):
            raise InvalidHandle("capability audience mismatch")
        return claims
