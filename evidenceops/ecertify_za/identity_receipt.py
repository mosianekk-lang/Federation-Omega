from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass
from enum import Enum

class IdentityDecision(str, Enum):
    VERIFIED = "VERIFIED"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NON_BIOMETRIC_FALLBACK = "NON_BIOMETRIC_FALLBACK"

@dataclass(frozen=True)
class ProviderVerificationReceipt:
    provider: str
    transaction_id: str
    verification_passed: bool
    live_presence_check_passed: bool
    trusted_reference_match_passed: bool
    document_check_passed: bool
    device_attestation_passed: bool
    provider_risk_level: str
    policy_version: str
    issued_at: str
    signature_verified: bool
    raw_sensitive_media_received_by_evidenceops: bool = False

@dataclass(frozen=True)
class IdentityReceiptAssessment:
    decision: IdentityDecision
    reasons: tuple[str, ...]
    evidence_digest: str
    provider_transaction_id: str

class IdentityReceiptGate:
    """Validates signed identity-provider receipts. It performs no biometric matching itself."""
    @staticmethod
    def _digest(receipt: ProviderVerificationReceipt) -> str:
        return hashlib.sha256(json.dumps(asdict(receipt),sort_keys=True,separators=(",",":")).encode()).hexdigest()

    def assess(self, receipt: ProviderVerificationReceipt, consent_granted: bool) -> IdentityReceiptAssessment:
        reasons=[]
        digest=self._digest(receipt)
        if not consent_granted:
            return IdentityReceiptAssessment(IdentityDecision.NON_BIOMETRIC_FALLBACK,("IDENTITY_PROVIDER_CONSENT_NOT_GRANTED",),digest,receipt.transaction_id)
        if receipt.raw_sensitive_media_received_by_evidenceops:
            return IdentityReceiptAssessment(IdentityDecision.HUMAN_REVIEW_REQUIRED,("SENSITIVE_MEDIA_BOUNDARY_VIOLATION",),digest,receipt.transaction_id)
        if not receipt.signature_verified:
            return IdentityReceiptAssessment(IdentityDecision.HUMAN_REVIEW_REQUIRED,("PROVIDER_RECEIPT_SIGNATURE_NOT_VERIFIED",),digest,receipt.transaction_id)
        checks={
            "PROVIDER_VERIFICATION_FAILED":receipt.verification_passed,
            "LIVE_PRESENCE_CHECK_FAILED":receipt.live_presence_check_passed,
            "TRUSTED_REFERENCE_MATCH_FAILED":receipt.trusted_reference_match_passed,
            "DOCUMENT_CHECK_FAILED":receipt.document_check_passed,
            "DEVICE_ATTESTATION_FAILED":receipt.device_attestation_passed,
        }
        reasons.extend(k for k,v in checks.items() if not v)
        if receipt.provider_risk_level.upper() not in {"LOW","NORMAL"}:
            reasons.append("PROVIDER_RISK_REQUIRES_STEP_UP")
        if reasons:
            return IdentityReceiptAssessment(IdentityDecision.STEP_UP_REQUIRED,tuple(reasons),digest,receipt.transaction_id)
        return IdentityReceiptAssessment(IdentityDecision.VERIFIED,("SIGNED_PROVIDER_IDENTITY_RECEIPT_ACCEPTED",),digest,receipt.transaction_id)
