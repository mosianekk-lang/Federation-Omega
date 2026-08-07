from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from enum import Enum
from .receipt_auth import AuthenticatedReceipt

class IdentityDecision(str,Enum):
    VERIFIED="VERIFIED"
    STEP_UP_REQUIRED="STEP_UP_REQUIRED"
    HUMAN_REVIEW_REQUIRED="HUMAN_REVIEW_REQUIRED"
    NON_BIOMETRIC_FALLBACK="NON_BIOMETRIC_FALLBACK"

@dataclass(frozen=True)
class IdentityReceiptAssessment:
    decision:IdentityDecision
    reasons:tuple[str,...]
    evidence_digest:str
    provider_transaction_id:str

class IdentityReceiptGate:
    """Consumes only cryptographically authenticated provider receipts."""
    def assess(self,authenticated:AuthenticatedReceipt,consent_granted:bool)->IdentityReceiptAssessment:
        p=authenticated.payload
        tx=str(p.get("transaction_id",""))
        digest=hashlib.sha256(json.dumps({"provider":authenticated.provider,"payload_sha256":authenticated.payload_sha256,"key_id":authenticated.key_id},sort_keys=True).encode()).hexdigest()
        if not consent_granted:
            return IdentityReceiptAssessment(IdentityDecision.NON_BIOMETRIC_FALLBACK,("IDENTITY_PROVIDER_CONSENT_NOT_GRANTED",),digest,tx)
        if bool(p.get("raw_sensitive_media_received_by_evidenceops",False)):
            return IdentityReceiptAssessment(IdentityDecision.HUMAN_REVIEW_REQUIRED,("SENSITIVE_MEDIA_BOUNDARY_VIOLATION",),digest,tx)
        checks={
            "PROVIDER_VERIFICATION_FAILED":bool(p.get("verification_passed",False)),
            "LIVE_PRESENCE_CHECK_FAILED":bool(p.get("live_presence_check_passed",False)),
            "TRUSTED_REFERENCE_MATCH_FAILED":bool(p.get("trusted_reference_match_passed",False)),
            "DOCUMENT_CHECK_FAILED":bool(p.get("document_check_passed",False)),
            "DEVICE_ATTESTATION_FAILED":bool(p.get("device_attestation_passed",False)),
        }
        reasons=[k for k,v in checks.items() if not v]
        if str(p.get("provider_risk_level","")).upper() not in {"LOW","NORMAL"}:
            reasons.append("PROVIDER_RISK_REQUIRES_STEP_UP")
        if reasons:
            return IdentityReceiptAssessment(IdentityDecision.STEP_UP_REQUIRED,tuple(reasons),digest,tx)
        return IdentityReceiptAssessment(IdentityDecision.VERIFIED,("CRYPTOGRAPHIC_PROVIDER_RECEIPT_ACCEPTED",),digest,tx)
