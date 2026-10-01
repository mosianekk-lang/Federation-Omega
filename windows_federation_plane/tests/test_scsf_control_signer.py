from __future__ import annotations

import base64
import copy
import hashlib
import os
import unittest
from unittest.mock import patch

from federation_windows_plane.relay_protocol import canonical_json
from federation_windows_plane.scsf_control_signer import (
    GoogleKMSP256ControlSigner,
    P256SoftwareControlSigner,
    control_signer_from_env,
)

RESOURCE = "projects/p/locations/global/keyRings/fuse/cryptoKeys/control/cryptoKeyVersions/1"


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP_{self.status}")

    def json(self):
        return copy.deepcopy(self.payload)


class FakeKMSSession:
    def __init__(self, key, *, algorithm="EC_SIGN_P256_SHA256", corrupt_signature=False):
        from cryptography.hazmat.primitives import serialization
        self.key = key
        self.algorithm = algorithm
        self.corrupt_signature = corrupt_signature
        self.calls = []
        self.pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def get(self, url, timeout):
        self.calls.append(("GET", url))
        return FakeResponse({"algorithm": self.algorithm, "pem": self.pem})

    def post(self, url, json, timeout):
        self.calls.append(("POST", url, copy.deepcopy(json)))
        digest = base64.b64decode(json["digest"]["sha256"])
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        der = self.key.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        if self.corrupt_signature:
            der = b"not-der"
        return FakeResponse({"signature": base64.b64encode(der).decode("ascii")})


class SCSFControlSignerTests(unittest.TestCase):
    def _key_and_fingerprint(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        software = P256SoftwareControlSigner(key)
        fingerprint = hashlib.sha256(canonical_json(software.public_jwk())).hexdigest()
        return key, software, fingerprint

    def test_kms_signer_validates_p256_fingerprint_and_der_to_p1363(self):
        key, software, fingerprint = self._key_and_fingerprint()
        session = FakeKMSSession(key)
        signer = GoogleKMSP256ControlSigner(
            RESOURCE,
            expected_jwk_sha256=fingerprint,
            session=session,
        )
        self.assertEqual(signer.public_jwk(), software.public_jwk())
        signature = signer.sign_b64(b"fuse-control-test")
        raw = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        self.assertEqual(len(raw), 64)
        self.assertTrue(any(call[0] == "GET" for call in session.calls))
        post = next(call for call in session.calls if call[0] == "POST")
        sent_digest = base64.b64decode(post[2]["digest"]["sha256"])
        self.assertEqual(sent_digest, hashlib.sha256(b"fuse-control-test").digest())

    def test_kms_signer_rejects_wrong_algorithm_fingerprint_and_bad_signature(self):
        key, _, fingerprint = self._key_and_fingerprint()
        with self.assertRaisesRegex(RuntimeError, "ALGORITHM_INVALID"):
            GoogleKMSP256ControlSigner(
                RESOURCE,
                expected_jwk_sha256=fingerprint,
                session=FakeKMSSession(key, algorithm="RSA_SIGN_PKCS1_2048_SHA256"),
            ).public_jwk()
        with self.assertRaisesRegex(RuntimeError, "PUBLIC_KEY_DRIFT"):
            GoogleKMSP256ControlSigner(
                RESOURCE,
                expected_jwk_sha256="0" * 64,
                session=FakeKMSSession(key),
            ).public_jwk()
        with self.assertRaisesRegex(RuntimeError, "SIGNATURE_INVALID"):
            GoogleKMSP256ControlSigner(
                RESOURCE,
                expected_jwk_sha256=fingerprint,
                session=FakeKMSSession(key, corrupt_signature=True),
            ).sign_b64(b"x")

    def test_env_binding_is_explicit_and_never_generates_default_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(control_signer_from_env())
        with patch.dict(os.environ, {"FUSE_SCSF_CONTROL_KMS_KEY_VERSION": RESOURCE}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "PUBLIC_JWK_SHA256_REQUIRED"):
                control_signer_from_env()

    def test_env_binding_reads_and_pins_provider_public_key(self):
        key, software, fingerprint = self._key_and_fingerprint()
        session = FakeKMSSession(key)
        with patch.dict(os.environ, {
            "FUSE_SCSF_CONTROL_KMS_KEY_VERSION": RESOURCE,
            "FUSE_SCSF_CONTROL_KMS_PUBLIC_JWK_SHA256": fingerprint,
        }, clear=True):
            signer = control_signer_from_env(session=session)
        self.assertIsNotNone(signer)
        self.assertEqual(signer.public_jwk(), software.public_jwk())


if __name__ == "__main__":
    unittest.main()
