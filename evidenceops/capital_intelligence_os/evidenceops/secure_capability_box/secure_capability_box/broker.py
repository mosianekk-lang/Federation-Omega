from __future__ import annotations

import logging
from typing import Any

from .audit import digest_json, redact
from .connectors.base import CapabilityConnector
from .errors import ConnectorFailure, InvalidHandle, ProviderUnavailable, SecureBoxError
from .models import CapabilityRequest, ExecutionReceipt, SecretReference
from .policy import LeastPrivilegePolicy
from .providers.base import SecretProvider
from .store import SecureBoxStore
from .tokens import CapabilityTokenCodec

LOGGER = logging.getLogger("evidenceops.secure_capability_box")


class SecureCapabilityBroker:
    """The single effectful path from an authorized handle to a connector call."""

    def __init__(
        self,
        *,
        token_codec: CapabilityTokenCodec,
        policy: LeastPrivilegePolicy,
        store: SecureBoxStore,
        providers: list[SecretProvider] | tuple[SecretProvider, ...],
        connectors: list[CapabilityConnector] | tuple[CapabilityConnector, ...],
    ) -> None:
        self.token_codec = token_codec
        self.policy = policy
        self.store = store
        self.providers = {provider.name: provider for provider in providers}
        self.connectors = {connector.name: connector for connector in connectors}

    def issue(self, request: CapabilityRequest) -> str:
        self.policy.authorize(request)
        if request.secret.provider not in self.providers:
            raise ProviderUnavailable("secret provider is not configured")
        if request.connector not in self.connectors:
            raise ConnectorFailure("capability connector is not configured")
        token, claims = self.token_codec.issue(request)
        self.store.register(claims)
        LOGGER.info(
            "capability issued",
            extra={"operation_id": claims.operation_id, "token_id": claims.token_id, "mission_id": claims.mission_id},
        )
        return token

    def revoke(self, token: str, *, subject: str, audience: str, reason: str) -> int:
        claims = self.token_codec.verify(token, expected_subject=subject, expected_audience=audience)
        return self.store.revoke(claims.token_id, reason)

    def execute(
        self,
        token: str,
        *,
        subject: str,
        audience: str,
        payload: dict[str, Any] | None = None,
    ) -> ExecutionReceipt:
        payload = payload or {}
        if not isinstance(payload, dict):
            raise InvalidHandle("connector payload must be an object")
        claims = self.token_codec.verify(token, expected_subject=subject, expected_audience=audience)
        request_digest = digest_json({
            "operation_id": claims.operation_id,
            "mission_id": claims.mission_id,
            "mission_version": claims.mission_version,
            "subject": claims.subject,
            "audience": claims.audience,
            "resource": claims.resource,
            "connector": claims.connector,
            "action": claims.action,
            "payload": redact(payload),
        })
        prior = self.store.reserve(claims, request_digest)
        if prior is not None:
            return prior

        provider_name, resource, version = self._split_reference(claims.resource)
        provider = self.providers.get(provider_name)
        connector = self.connectors.get(claims.connector)
        if provider is None or connector is None:
            self.store.fail(claims, "MISSING_CONFIGURATION")
            raise ProviderUnavailable("required runtime binding is unavailable")

        secret_buffer: bytearray | None = None
        try:
            secret_buffer = provider.access(SecretReference(provider_name, resource, version))
            result = connector.execute(
                action=claims.action,
                credential=memoryview(secret_buffer),
                payload=payload,
                correlation_id=claims.operation_id,
            )
            safe_result = redact(result)
            receipt = ExecutionReceipt(
                operation_id=claims.operation_id,
                token_id=claims.token_id,
                mission_id=claims.mission_id,
                connector=claims.connector,
                action=claims.action,
                state="COMPLETED",
                result_digest=digest_json(safe_result),
                audit_sequence=0,
            )
            return self.store.complete(receipt, request_digest)
        except ProviderUnavailable as exc:
            self.store.fail(claims, type(exc).__name__)
            raise ProviderUnavailable("secret provider access failed") from None
        except ConnectorFailure as exc:
            self.store.fail(claims, type(exc).__name__)
            raise ConnectorFailure("connector execution failed") from None
        except SecureBoxError as exc:
            self.store.fail(claims, type(exc).__name__)
            raise type(exc)("capability execution failed") from None
        except Exception as exc:
            self.store.fail(claims, "EXTERNAL_API_FAILURE")
            raise ConnectorFailure("capability execution failed") from exc
        finally:
            if secret_buffer is not None:
                secret_buffer[:] = b"\x00" * len(secret_buffer)

    def readiness(self) -> dict[str, Any]:
        provider_states = {name: provider.readiness() for name, provider in self.providers.items()}
        connector_states = {name: connector.readiness() for name, connector in self.connectors.items()}
        production_ready = bool(provider_states and connector_states) and all(
            item.get("production_ready") is True
            for item in [*provider_states.values(), *connector_states.values()]
        )
        return {
            "state": "READY" if production_ready else "NOT_PRODUCTION_READY",
            "production_ready": production_ready,
            "store": self.store.health(),
            "providers": provider_states,
            "connectors": connector_states,
        }

    @staticmethod
    def _split_reference(reference: str) -> tuple[str, str, str]:
        try:
            provider, resource, version = reference.split(":", 2)
        except ValueError as exc:
            raise InvalidHandle("capability resource is malformed") from exc
        return provider, resource, version
