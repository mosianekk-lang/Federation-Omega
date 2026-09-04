"""Rotatable, secret-reference-only HMAC authentication for inbound webhooks."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

SIGNATURE_VERSION = "MODISA-HMAC-V2"
ALLOWED_SECRET_SCHEMES = (
    "env://",
    "gcp-secret://",
    "azure-keyvault://",
    "aws-secretsmanager://",
)
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
OPAQUE_ID = re.compile(r"^[A-Za-z0-9._/@:-]{3,512}$")
GCP_SECRET_RESOURCE = re.compile(
    r"^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,30})/"
    r"secrets/[A-Za-z0-9_-]{1,255}/"
    r"versions/[1-9][0-9]*$"
)
NONCE = re.compile(r"^[A-Za-z0-9._~-]{16,256}$")
SIGNATURE = re.compile(r"^[0-9a-fA-F]{64}$")
METHOD = re.compile(r"^[A-Z]{3,16}$")


class WebhookAuthError(RuntimeError):
    """The inbound request could not be authenticated safely."""


@dataclass(frozen=True)
class SecretReference:
    scheme: str
    identifier: str

    @classmethod
    def parse(cls, value: str) -> SecretReference:
        if not value or value != value.strip() or "\n" in value or "\r" in value:
            raise ValueError("Secret reference must be a single opaque URI")
        for prefix in ALLOWED_SECRET_SCHEMES:
            if value.startswith(prefix):
                identifier = value[len(prefix) :]
                if prefix == "env://":
                    if not ENV_NAME.fullmatch(identifier):
                        raise ValueError("Environment secret reference has an invalid variable name")
                elif prefix == "gcp-secret://" and not GCP_SECRET_RESOURCE.fullmatch(identifier):
                    raise ValueError(
                        "Google Secret Manager references require a complete numeric version"
                    )
                elif prefix != "gcp-secret://" and not OPAQUE_ID.fullmatch(identifier):
                    raise ValueError("Secret-manager reference has an invalid opaque identifier")
                return cls(scheme=prefix[:-3], identifier=identifier)
        raise ValueError("Raw secrets and unsupported secret-reference schemes are forbidden")


class SecretResolver(Protocol):
    def resolve(self, reference: SecretReference) -> bytes:
        """Resolve a secret in memory without persisting or logging it."""


class EnvironmentSecretResolver:
    """Resolve only ``env://`` references; provider managers require provider adapters."""

    kind = "environment"
    provider_proven = False

    def resolve(self, reference: SecretReference) -> bytes:
        if reference.scheme != "env":
            raise WebhookAuthError("No provider secret-manager resolver is configured")
        value = os.environ.get(reference.identifier)
        if value is None:
            raise WebhookAuthError("Referenced webhook secret is unavailable")
        secret = value.encode("utf-8")
        if len(secret) < 32:
            raise WebhookAuthError("Referenced webhook secret must contain at least 32 bytes")
        return secret


class WebhookAuthPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key_id: str = Field(min_length=3, max_length=200)
    secret_ref: str
    max_clock_skew_seconds: int = Field(default=300, ge=30, le=3600)

    @field_validator("secret_ref")
    @classmethod
    def validate_secret_ref(cls, value: str) -> str:
        SecretReference.parse(value)
        return value


class WebhookAuthReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_id: str = Field(default="MODISA_WEBHOOK_AUTH_RECEIPT_V1", alias="schema")
    signature_version: str = SIGNATURE_VERSION
    key_id: str
    timestamp: int
    nonce_sha256: str
    body_sha256: str
    secret_ref_scheme: str
    signature_valid: bool = True
    replay_protected: bool = True
    secret_material_persisted: bool = False


def canonical_request(
    *, key_id: str, timestamp: int, nonce: str, method: str, path: str, body: bytes
) -> str:
    if not 3 <= len(key_id) <= 200 or "\n" in key_id or "\r" in key_id:
        raise WebhookAuthError("Webhook key identity is not canonical")
    if not METHOD.fullmatch(method):
        raise WebhookAuthError("HTTP method must be canonical uppercase ASCII")
    if not path.startswith("/") or "\n" in path or "\r" in path or " " in path:
        raise WebhookAuthError("Request path is not canonical")
    if not NONCE.fullmatch(nonce):
        raise WebhookAuthError("Webhook nonce is malformed or too short")
    body_sha256 = hashlib.sha256(body).hexdigest()
    return (
        f"{SIGNATURE_VERSION}\n{key_id}\n{timestamp}\n{nonce}\n{method}\n{path}\n{body_sha256}"
    )


def sign_request(
    secret: bytes,
    *,
    key_id: str,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body: bytes,
) -> str:
    if len(secret) < 32:
        raise WebhookAuthError("Webhook signing secret must contain at least 32 bytes")
    message = canonical_request(
        key_id=key_id, timestamp=timestamp, nonce=nonce, method=method, path=path, body=body
    )
    return hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()


class WebhookAuthenticator:
    def __init__(
        self,
        policy: WebhookAuthPolicy,
        resolver: SecretResolver,
        nonce_store: NonceStore,
    ) -> None:
        self.policy = policy
        self.resolver = resolver
        self.nonce_store = nonce_store
        self.reference = SecretReference.parse(policy.secret_ref)

    def verify(
        self,
        *,
        key_id: str,
        timestamp: int,
        nonce: str,
        signature: str,
        method: str,
        path: str,
        body: bytes,
        now: int | None = None,
    ) -> WebhookAuthReceipt:
        observed_now = int(time.time()) if now is None else now
        if not hmac.compare_digest(self.policy.key_id, key_id):
            raise WebhookAuthError("Webhook key identity does not match active policy")
        if abs(observed_now - timestamp) > self.policy.max_clock_skew_seconds:
            raise WebhookAuthError("Webhook timestamp is outside the permitted clock-skew window")
        if not SIGNATURE.fullmatch(signature):
            raise WebhookAuthError("Webhook signature is malformed")
        message = canonical_request(
            key_id=key_id,
            timestamp=timestamp,
            nonce=nonce,
            method=method,
            path=path,
            body=body,
        )
        secret = self.resolver.resolve(self.reference)
        expected = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            raise WebhookAuthError("Webhook signature verification failed")

        nonce_sha256 = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        expires_at = timestamp + self.policy.max_clock_skew_seconds
        if not self.nonce_store.consume_once(
            key_id=self.policy.key_id,
            nonce_sha256=nonce_sha256,
            expires_at=expires_at,
            now=observed_now,
        ):
            raise WebhookAuthError("Webhook replay detected")
        return WebhookAuthReceipt(
            key_id=self.policy.key_id,
            timestamp=timestamp,
            nonce_sha256=nonce_sha256,
            body_sha256=hashlib.sha256(body).hexdigest(),
            secret_ref_scheme=self.reference.scheme,
        )


# Backward-compatible imports for v2.4 callers.
from .nonce_stores import NonceStore, SQLiteNonceStore  # noqa: E402,F401
