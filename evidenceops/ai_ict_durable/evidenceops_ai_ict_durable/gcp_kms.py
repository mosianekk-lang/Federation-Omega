from __future__ import annotations

import os
from typing import Any, Callable


def _default_crc32c(data: bytes) -> int:
    try:
        import google_crc32c
    except Exception as exc:
        raise RuntimeError("google-crc32c is required for KMS integrity checks") from exc
    return int(google_crc32c.value(data))


class GoogleCloudKMSStateProtector:
    """Cloud KMS symmetric protector using ADC service identity and AAD.

    The key material is never exported. CRC32C request/response verification is
    mandatory, and mission/version AAD must match during decrypt.
    """

    def __init__(
        self,
        key_id: str,
        *,
        client: Any = None,
        crc32c: Callable[[bytes], int] | None = None,
    ):
        if "/cryptoKeys/" not in key_id:
            raise ValueError("key_id must be a Cloud KMS CryptoKey resource name")
        self.key_id = key_id
        self._client = client
        self._crc32c = crc32c or _default_crc32c

    @classmethod
    def from_environment(cls, *, client: Any = None):
        key_id = os.getenv("EO_STATE_KMS_KEY")
        if not key_id:
            raise RuntimeError("EO_STATE_KMS_KEY is not configured")
        return cls(key_id, client=client)

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import kms_v1
            except Exception as exc:
                raise RuntimeError("google-cloud-kms is unavailable") from exc
            self._client = kms_v1.KeyManagementServiceClient()
        return self._client

    @staticmethod
    def _value(field: Any) -> int:
        return int(getattr(field, "value", field))

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> bytes:
        response = self._get_client().encrypt(
            request={
                "name": self.key_id,
                "plaintext": plaintext,
                "additional_authenticated_data": aad,
                "plaintext_crc32c": self._crc32c(plaintext),
                "additional_authenticated_data_crc32c": self._crc32c(aad),
            }
        )
        if not bool(response.verified_plaintext_crc32c):
            raise RuntimeError("KMS rejected plaintext CRC32C verification")
        if hasattr(response, "verified_additional_authenticated_data_crc32c") and not bool(
            response.verified_additional_authenticated_data_crc32c
        ):
            raise RuntimeError("KMS rejected AAD CRC32C verification")
        ciphertext = bytes(response.ciphertext)
        if self._value(response.ciphertext_crc32c) != self._crc32c(ciphertext):
            raise RuntimeError("KMS encrypt response failed CRC32C verification")
        if getattr(response, "name", self.key_id) and not str(response.name).startswith(self.key_id):
            raise RuntimeError("KMS encrypted with an unexpected key version")
        return ciphertext

    def decrypt(self, ciphertext: bytes, *, aad: bytes) -> bytes:
        response = self._get_client().decrypt(
            request={
                "name": self.key_id,
                "ciphertext": ciphertext,
                "additional_authenticated_data": aad,
                "ciphertext_crc32c": self._crc32c(ciphertext),
                "additional_authenticated_data_crc32c": self._crc32c(aad),
            }
        )
        plaintext = bytes(response.plaintext)
        if self._value(response.plaintext_crc32c) != self._crc32c(plaintext):
            raise RuntimeError("KMS decrypt response failed CRC32C verification")
        return plaintext
