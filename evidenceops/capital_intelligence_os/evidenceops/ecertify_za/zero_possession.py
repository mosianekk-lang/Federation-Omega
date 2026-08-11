from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class IntegrityReceipt:
    verification_code: str
    document_sha256: str
    issued_at: int
    key_id: str
    public_label: str
    client_nonce_sha256: str
    signature_hex: str
    truth_boundary: tuple[str, ...]

class ZeroPossessionReceiptService:
    """Issue tamper-evident receipts without receiving or retaining document bytes.

    The browser computes SHA-256 locally. The server receives only the digest, a client
    nonce and minimal non-document metadata, then signs the resulting receipt. This is
    technical integrity/provenance evidence, not statutory certification or issuer proof.
    """

    PUBLIC_LABEL = "EVIDENCEOPS_DOCUMENT_INTEGRITY_RECEIPT"

    def __init__(self, signing_key: bytes, *, key_id: str = "ecertify-integrity-v1"):
        if len(signing_key) < 32:
            raise ValueError("INTEGRITY_SIGNING_KEY_TOO_SHORT")
        self.signing_key = signing_key
        self.key_id = key_id

    @staticmethod
    def _validate_hash(document_sha256: str) -> str:
        value = document_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("DOCUMENT_SHA256_INVALID")
        return value

    @staticmethod
    def _nonce_digest(client_nonce: str) -> str:
        nonce = client_nonce.strip()
        if len(nonce) < 16 or len(nonce) > 256:
            raise ValueError("CLIENT_NONCE_LENGTH_INVALID")
        return hashlib.sha256(nonce.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical(payload: dict) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _sign(self, payload: dict) -> str:
        return hmac.new(self.signing_key, self._canonical(payload), hashlib.sha256).hexdigest()

    def issue(self, *, document_sha256: str, client_nonce: str, now: int | None = None) -> IntegrityReceipt:
        digest = self._validate_hash(document_sha256)
        nonce_digest = self._nonce_digest(client_nonce)
        issued_at = int(time.time()) if now is None else int(now)
        verification_code = "EOZA-I-" + secrets.token_hex(8).upper()
        payload = {
            "verification_code": verification_code,
            "document_sha256": digest,
            "issued_at": issued_at,
            "key_id": self.key_id,
            "public_label": self.PUBLIC_LABEL,
            "client_nonce_sha256": nonce_digest,
            "truth_boundary": [
                "DOCUMENT_BYTES_NOT_RECEIVED_BY_EVIDENCEOPS_RECEIPT_SERVICE",
                "NOT_A_CERTIFIED_COPY",
                "NOT_ISSUER_VERIFIED_UNLESS_SEPARATE_SOURCE_PROOF_EXISTS",
                "NOT_A_GOVERNMENT_DOCUMENT",
            ],
        }
        signature = self._sign(payload)
        return IntegrityReceipt(signature_hex=signature, **payload)

    def verify(self, receipt: IntegrityReceipt) -> bool:
        payload = asdict(receipt)
        signature = payload.pop("signature_hex")
        payload["truth_boundary"] = list(payload["truth_boundary"])
        return hmac.compare_digest(self._sign(payload), signature)
