from __future__ import annotations

import base64
import hashlib
import os
import re
from typing import Any, Protocol

from .relay_protocol import canonical_json


KMS_ALGORITHM = "EC_SIGN_P256_SHA256"
KMS_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
KMS_RESOURCE_RE = re.compile(
    r"^projects/[A-Za-z0-9._-]+/locations/[A-Za-z0-9._-]+/keyRings/[A-Za-z0-9._-]+/cryptoKeys/[A-Za-z0-9._-]+/cryptoKeyVersions/[1-9][0-9]*$"
)


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _valid_hex(value: str, size: int = 64) -> bool:
    return len(value) == size and re.fullmatch(r"[0-9a-f]+", value) is not None


class SCSFControlSigner(Protocol):
    def public_jwk(self) -> dict[str, str]: ...
    def sign_b64(self, payload: bytes) -> str: ...


class P256SoftwareControlSigner:
    """Test/dev signer only. Production startup must never auto-generate this key."""

    def __init__(self, key: Any):
        self._key = key

    @classmethod
    def generate(cls) -> "P256SoftwareControlSigner":
        from cryptography.hazmat.primitives.asymmetric import ec
        return cls(ec.generate_private_key(ec.SECP256R1()))

    def public_jwk(self) -> dict[str, str]:
        nums = self._key.public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64u(nums.x.to_bytes(32, "big")),
            "y": _b64u(nums.y.to_bytes(32, "big")),
        }

    def sign_b64(self, payload: bytes) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        der = self._key.sign(payload, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


class GoogleKMSP256ControlSigner:
    """Non-exportable P-256 custody adapter via authenticated Cloud KMS REST."""

    def __init__(
        self,
        key_version_resource: str,
        *,
        expected_jwk_sha256: str,
        session: Any | None = None,
    ):
        if KMS_RESOURCE_RE.fullmatch(key_version_resource or "") is None:
            raise ValueError("SCSF_KMS_KEY_VERSION_INVALID")
        if not _valid_hex(expected_jwk_sha256):
            raise ValueError("SCSF_KMS_PUBLIC_JWK_SHA256_INVALID")
        self.key_version_resource = key_version_resource
        self.expected_jwk_sha256 = expected_jwk_sha256
        self._session = session
        self._jwk: dict[str, str] | None = None

    @property
    def _base_url(self) -> str:
        return "https://cloudkms.googleapis.com/v1/" + self.key_version_resource

    def _authorized_session(self):
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=[KMS_SCOPE])
            self._session = AuthorizedSession(credentials)
        return self._session

    def public_jwk(self) -> dict[str, str]:
        if self._jwk is not None:
            return dict(self._jwk)
        response = self._authorized_session().get(self._base_url + "/publicKey", timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("algorithm") != KMS_ALGORITHM:
            raise RuntimeError("SCSF_KMS_ALGORITHM_INVALID")
        pem = data.get("pem")
        if not isinstance(pem, str) or "BEGIN PUBLIC KEY" not in pem:
            raise RuntimeError("SCSF_KMS_PUBLIC_KEY_MISSING")

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        try:
            key = serialization.load_pem_public_key(pem.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("SCSF_KMS_PUBLIC_KEY_INVALID") from exc
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise RuntimeError("SCSF_KMS_PUBLIC_KEY_CURVE_INVALID")
        nums = key.public_numbers()
        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64u(nums.x.to_bytes(32, "big")),
            "y": _b64u(nums.y.to_bytes(32, "big")),
        }
        fingerprint = hashlib.sha256(canonical_json(jwk)).hexdigest()
        if fingerprint != self.expected_jwk_sha256:
            raise RuntimeError("SCSF_KMS_PUBLIC_KEY_DRIFT")
        self._jwk = jwk
        return dict(jwk)

    def sign_b64(self, payload: bytes) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

        jwk = self.public_jwk()
        digest = hashlib.sha256(payload).digest()
        response = self._authorized_session().post(
            self._base_url + ":asymmetricSign",
            json={"digest": {"sha256": base64.b64encode(digest).decode("ascii")}},
            timeout=15,
        )
        response.raise_for_status()
        signature = response.json().get("signature")
        if not isinstance(signature, str):
            raise RuntimeError("SCSF_KMS_SIGNATURE_MISSING")
        try:
            der = base64.b64decode(signature, validate=True)
            r, s = decode_dss_signature(der)
            p1363 = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        except Exception as exc:
            raise RuntimeError("SCSF_KMS_SIGNATURE_INVALID") from exc

        x = int.from_bytes(_unb64u(jwk["x"]), "big")
        y = int.from_bytes(_unb64u(jwk["y"]), "big")
        public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
        try:
            public_key.verify(encode_dss_signature(r, s), payload, ec.ECDSA(hashes.SHA256()))
        except Exception as exc:
            raise RuntimeError("SCSF_KMS_SIGNATURE_SELF_VERIFY_FAILED") from exc
        return _b64u(p1363)


def control_signer_from_env(*, session: Any | None = None) -> SCSFControlSigner | None:
    resource = os.environ.get("FUSE_SCSF_CONTROL_KMS_KEY_VERSION", "").strip()
    fingerprint = os.environ.get("FUSE_SCSF_CONTROL_KMS_PUBLIC_JWK_SHA256", "").strip().lower()
    if not resource and not fingerprint:
        return None
    if not resource:
        raise RuntimeError("SCSF_CONTROL_KMS_KEY_VERSION_REQUIRED")
    if not fingerprint:
        raise RuntimeError("SCSF_CONTROL_KMS_PUBLIC_JWK_SHA256_REQUIRED")
    signer = GoogleKMSP256ControlSigner(
        resource,
        expected_jwk_sha256=fingerprint,
        session=session,
    )
    signer.public_jwk()
    return signer
