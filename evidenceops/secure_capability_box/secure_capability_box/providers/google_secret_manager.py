from __future__ import annotations

import re

from ..errors import InvalidRequest, ProviderUnavailable
from ..models import SecretReference

_GSM_RESOURCE = re.compile(r"^projects/[A-Za-z0-9._-]+/secrets/[A-Za-z0-9._-]+$")


class GoogleSecretManagerProvider:
    """ADC/service-identity adapter for exact Google Secret Manager versions."""

    name = "google-secret-manager"

    def __init__(self, client=None) -> None:
        if client is None:
            try:
                from google.cloud import secretmanager
            except ImportError as exc:
                raise ProviderUnavailable("google-cloud-secret-manager is not installed") from exc
            client = secretmanager.SecretManagerServiceClient()
        self._client = client

    def access(self, reference: SecretReference) -> bytearray:
        if reference.provider != self.name or not _GSM_RESOURCE.fullmatch(reference.resource):
            raise InvalidRequest("Google Secret Manager reference is invalid")
        name = f"{reference.resource}/versions/{reference.version}"
        try:
            response = self._client.access_secret_version(request={"name": name})
            payload = bytes(response.payload.data)
            expected_crc = getattr(response.payload, "data_crc32c", None)
            if expected_crc is not None:
                try:
                    import google_crc32c
                except ImportError as exc:
                    raise ProviderUnavailable("google-crc32c is required for payload verification") from exc
                actual_crc = int(google_crc32c.Checksum(payload).hexdigest(), 16)
                if actual_crc != int(expected_crc):
                    raise ProviderUnavailable("secret payload integrity verification failed")
            return bytearray(payload)
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise ProviderUnavailable("secret provider access failed") from exc

    def readiness(self) -> dict[str, object]:
        return {"state": "CONFIGURED", "production_ready": True, "authentication": "ADC"}
