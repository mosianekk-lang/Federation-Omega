"""Provider secret resolvers for MODISA webhook authentication.

The Google adapter is deliberately read-only, exact-resource allowlisted and
version pinned. It resolves once into an in-memory cache so unauthenticated
webhook traffic cannot amplify Secret Manager calls.
"""

from __future__ import annotations

import importlib
import threading
from collections.abc import Callable
from typing import Any, Protocol

from .webhook_auth import GCP_SECRET_RESOURCE, SecretReference, WebhookAuthError


class SecretManagerAccessClient(Protocol):
    def access_secret_version(
        self,
        *,
        request: dict[str, str],
        retry: object | None,
        timeout: float,
    ) -> object: ...


def validate_gcp_secret_resource(name: str) -> str:
    if not GCP_SECRET_RESOURCE.fullmatch(name):
        raise WebhookAuthError(
            "Google Secret Manager reference must name an exact numeric secret version"
        )
    return name


def _load_google_dependencies() -> tuple[SecretManagerAccessClient, Callable[[bytes], int]]:
    try:
        secretmanager = importlib.import_module("google.cloud.secretmanager_v1")
        google_crc32c = importlib.import_module("google_crc32c")
        client = secretmanager.SecretManagerServiceClient()
        checksum = google_crc32c.value
    except Exception:
        raise WebhookAuthError(
            "Google Secret Manager adapter is unavailable in this runtime"
        ) from None
    return client, checksum


class GoogleSecretManagerResolver:
    """Resolve one allowlisted, numerically pinned Secret Manager version."""

    kind = "google_secret_manager"

    def __init__(
        self,
        *,
        allowed_resource: str,
        client: SecretManagerAccessClient | None = None,
        checksum_crc32c: Callable[[bytes], int] | None = None,
        timeout_seconds: float = 5.0,
        max_secret_bytes: int = 65_536,
    ) -> None:
        self.allowed_resource = validate_gcp_secret_resource(allowed_resource)
        if not 0.1 <= timeout_seconds <= 30.0:
            raise ValueError("Secret Manager timeout must be between 0.1 and 30 seconds")
        if not 32 <= max_secret_bytes <= 65_536:
            raise ValueError("Secret Manager payload limit must be between 32 and 65536 bytes")
        if client is None or checksum_crc32c is None:
            default_client, default_checksum = _load_google_dependencies()
            client = client or default_client
            checksum_crc32c = checksum_crc32c or default_checksum
        self._client = client
        self._checksum_crc32c = checksum_crc32c
        self._timeout_seconds = timeout_seconds
        self._max_secret_bytes = max_secret_bytes
        self._cache: dict[str, bytes] = {}
        self._lock = threading.Lock()

    @property
    def provider_proven(self) -> bool:
        return self.allowed_resource in self._cache

    def resolve(self, reference: SecretReference) -> bytes:
        if reference.scheme != "gcp-secret":
            raise WebhookAuthError("Google Secret Manager resolver received the wrong scheme")
        resource = validate_gcp_secret_resource(reference.identifier)
        if resource != self.allowed_resource:
            raise WebhookAuthError("Google Secret Manager resource is outside the allowlist")
        cached = self._cache.get(resource)
        if cached is not None:
            return cached

        with self._lock:
            cached = self._cache.get(resource)
            if cached is not None:
                return cached
            try:
                response: Any = self._client.access_secret_version(
                    request={"name": resource},
                    retry=None,
                    timeout=self._timeout_seconds,
                )
                if str(response.name) != resource:
                    raise ValueError("resource identity mismatch")
                payload = response.payload
                data = bytes(payload.data)
                expected_crc32c = payload.data_crc32c
                if not isinstance(expected_crc32c, int):
                    raise ValueError("missing checksum")
                if self._checksum_crc32c(data) != expected_crc32c:
                    raise ValueError("checksum mismatch")
                if not 32 <= len(data) <= self._max_secret_bytes:
                    raise ValueError("secret length outside policy")
            except Exception:
                raise WebhookAuthError("Google Secret Manager access failed safely") from None
            self._cache[resource] = data
            return data
