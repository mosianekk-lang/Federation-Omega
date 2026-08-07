from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from enum import Enum
from .device_trust import DeviceAssessment,DeviceDecision
from .identity_receipt import IdentityDecision,IdentityReceiptAssessment

class HumanVerificationDecision(str,Enum):
    VERIFIED="VERIFIED"
    STEP_UP_REQUIRED="STEP_UP_REQUIRED"
    HUMAN_REVIEW_REQUIRED="HUMAN_REVIEW_REQUIRED"
    NON_BIOMETRIC_FALLBACK="NON_BIOMETRIC_FALLBACK"

@dataclass(frozen=True)
class HumanVerificationAssessment:
    decision:HumanVerificationDecision
    reasons:tuple[str,...]
    evidence_digest:str

class HumanVerificationOrchestrator:
    """Combine independent identity-provider and device-trust evidence.

    Trust does not transfer between domains: provider identity success cannot prove
    device integrity, and a trusted device cannot cure failed identity proofing.
    """
    def assess(self,identity:IdentityReceiptAssessment,device:DeviceAssessment)->HumanVerificationAssessment:
        reasons=tuple(identity.reasons)+tuple(device.reasons)
        digest=hashlib.sha256(json.dumps({"identity":identity.evidence_digest,"device":device.device_binding_digest},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if identity.decision==IdentityDecision.NON_BIOMETRIC_FALLBACK:
            return HumanVerificationAssessment(HumanVerificationDecision.NON_BIOMETRIC_FALLBACK,reasons,digest)
        if identity.decision==IdentityDecision.HUMAN_REVIEW_REQUIRED or device.decision==DeviceDecision.HUMAN_REVIEW_REQUIRED:
            return HumanVerificationAssessment(HumanVerificationDecision.HUMAN_REVIEW_REQUIRED,reasons,digest)
        if identity.decision==IdentityDecision.VERIFIED and device.decision==DeviceDecision.TRUSTED:
            return HumanVerificationAssessment(HumanVerificationDecision.VERIFIED,reasons,digest)
        return HumanVerificationAssessment(HumanVerificationDecision.STEP_UP_REQUIRED,reasons,digest)
