from __future__ import annotations

import unittest
from types import SimpleNamespace

from evidenceops_ai_ict_durable.gcp_kms import GoogleCloudKMSStateProtector


def crc(data: bytes) -> int:
    return sum(data) % (2**32)


class FakeKMSClient:
    def __init__(self):
        self.last_encrypt = None
        self.last_decrypt = None

    def encrypt(self, request):
        self.last_encrypt = request
        ciphertext = b"enc:" + request["plaintext"]
        return SimpleNamespace(
            verified_plaintext_crc32c=True,
            verified_additional_authenticated_data_crc32c=True,
            ciphertext=ciphertext,
            ciphertext_crc32c=crc(ciphertext),
            name=request["name"] + "/cryptoKeyVersions/1",
        )

    def decrypt(self, request):
        self.last_decrypt = request
        plaintext = request["ciphertext"][4:]
        return SimpleNamespace(
            plaintext=plaintext,
            plaintext_crc32c=crc(plaintext),
        )


class KMSProtectorTests(unittest.TestCase):
    def test_kms_protector_uses_aad_and_integrity_checks(self):
        key = "projects/p/locations/global/keyRings/r/cryptoKeys/k"
        client = FakeKMSClient()
        protector = GoogleCloudKMSStateProtector(key, client=client, crc32c=crc)
        ciphertext = protector.encrypt(b"state", aad=b"mission:v1")
        self.assertEqual(ciphertext, b"enc:state")
        self.assertEqual(
            client.last_encrypt["additional_authenticated_data"], b"mission:v1"
        )
        plaintext = protector.decrypt(ciphertext, aad=b"mission:v1")
        self.assertEqual(plaintext, b"state")
        self.assertEqual(
            client.last_decrypt["additional_authenticated_data"], b"mission:v1"
        )

    def test_invalid_key_resource_is_rejected(self):
        with self.assertRaises(ValueError):
            GoogleCloudKMSStateProtector("not-a-kms-resource", client=FakeKMSClient())

    def test_crc_mismatch_fails_closed(self):
        class BadClient(FakeKMSClient):
            def encrypt(self, request):
                response = super().encrypt(request)
                response.ciphertext_crc32c = 0
                return response

        protector = GoogleCloudKMSStateProtector(
            "projects/p/locations/global/keyRings/r/cryptoKeys/k",
            client=BadClient(),
            crc32c=crc,
        )
        with self.assertRaisesRegex(RuntimeError, "CRC32C"):
            protector.encrypt(b"state", aad=b"mission:v1")


if __name__ == "__main__":
    unittest.main()
