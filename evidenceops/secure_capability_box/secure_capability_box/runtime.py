"""Fail-closed runtime assembly for the private Secure Capability Box service."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path

from .broker import SecureCapabilityBroker
from .connectors.federation_omega import FederationOmegaConnector
from .errors import InvalidRequest
from .models import ActionClass, AuthorityClass, CapabilityRequest, SecretReference, WorkloadIdentity
from .policy import LeastPrivilegePolicy, PolicyRule
from .providers.google_secret_manager import GoogleSecretManagerProvider
from .store import SecureBoxStore
from .tokens import CapabilityTokenCodec


def _required(env: dict[str, str], name: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        raise RuntimeError(f"required runtime setting {name} is absent")
    return value


def _signing_key(env: dict[str, str]) -> bytes:
    raw = _required(env, "SCB_SIGNING_KEY")
    try:
        value = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeError("SCB_SIGNING_KEY must be URL-safe base64") from exc
    if len(value) < 32:
        raise RuntimeError("SCB_SIGNING_KEY must decode to at least 32 bytes")
    return value


@dataclass(frozen=True)
class RuntimeConfig:
    api_token: str
    subject: str
    audience: str
    authority: AuthorityClass
    secret: SecretReference
    allowed_actions: tuple[str, ...]
    database_path: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "RuntimeConfig":
        values = dict(os.environ if env is None else env)
        version = _required(values, "SCB_SECRET_VERSION")
        if version.lower() == "latest" or not version.isdigit():
            raise RuntimeError("SCB_SECRET_VERSION must be an exact numeric version")
        actions = tuple(
            item.strip() for item in _required(values, "SCB_ALLOWED_ACTIONS").split(",") if item.strip()
        )
        if not actions or len(set(actions)) != len(actions):
            raise RuntimeError("SCB_ALLOWED_ACTIONS must contain unique actions")
        return cls(
            api_token=_required(values, "SCB_API_TOKEN"),
            subject=_required(values, "SCB_SUBJECT"),
            audience=_required(values, "SCB_AUDIENCE"),
            authority=AuthorityClass(_required(values, "SCB_AUTHORITY")),
            secret=SecretReference(
                "google-secret-manager",
                f"projects/{_required(values, 'SCB_SECRET_PROJECT')}/secrets/{_required(values, 'SCB_SECRET_NAME')}",
                version,
            ),
            allowed_actions=actions,
            database_path=values.get("SCB_DB_PATH", "/tmp/secure-capability-box.sqlite"),
        )


class SecureBoxRuntime:
    def __init__(self, config: RuntimeConfig, broker: SecureCapabilityBroker) -> None:
        self.config = config
        self.broker = broker

    def request(self, *, mission_id: str, mission_version: int, operation_id: str, action: str, ttl_seconds: int) -> CapabilityRequest:
        if action not in self.config.allowed_actions:
            raise InvalidRequest("action is not allowed by runtime configuration")
        return CapabilityRequest(
            mission_id=mission_id,
            mission_version=mission_version,
            operation_id=operation_id,
            identity=WorkloadIdentity(self.config.subject, self.config.audience, self.config.authority),
            secret=self.config.secret,
            connector="federation-omega",
            action=action,
            ttl_seconds=ttl_seconds,
        )


def build_runtime(
    env: dict[str, str] | None = None,
    *,
    provider=None,
    connector=None,
) -> SecureBoxRuntime:
    values = dict(os.environ if env is None else env)
    config = RuntimeConfig.from_env(values)
    store_path = Path(config.database_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    provider = provider or GoogleSecretManagerProvider()
    connector = connector or FederationOmegaConnector(_required(values, "FO_OPERATOR_URL"))
    prefix = config.secret.reference_id.rsplit(":", 1)[0] + ":"
    rules = [
        PolicyRule("federation-omega", action, prefix, config.authority, ActionClass.READ)
        for action in config.allowed_actions
    ]
    broker = SecureCapabilityBroker(
        token_codec=CapabilityTokenCodec(_signing_key(values), key_id=_required(values, "SCB_KEY_ID")),
        policy=LeastPrivilegePolicy(rules),
        store=SecureBoxStore(store_path),
        providers=[provider],
        connectors=[connector],
    )
    return SecureBoxRuntime(config, broker)
