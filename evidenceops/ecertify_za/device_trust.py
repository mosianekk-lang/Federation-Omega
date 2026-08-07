from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from enum import Enum

class DeviceDecision(str,Enum):
    TRUSTED="TRUSTED"
    STEP_UP_REQUIRED="STEP_UP_REQUIRED"
    HUMAN_REVIEW_REQUIRED="HUMAN_REVIEW_REQUIRED"

@dataclass(frozen=True)
class DeviceAttestationReceipt:
    platform:str
    app_instance_id:str
    device_key_id:str
    attestation_verified:bool
    hardware_backed_key:bool
    app_integrity_passed:bool
    device_integrity_passed:bool
    nonce_verified:bool
    issued_at:int
    risk_signals:tuple[str,...]=()

@dataclass(frozen=True)
class DeviceAssessment:
    decision:DeviceDecision
    reasons:tuple[str,...]
    device_binding_digest:str

class DeviceTrustPolicy:
    """Provider-neutral device binding/step-up policy.

    Platform-specific adapters may bind Android Play Integrity or Apple App Attest
    receipts. This layer consumes only verified attestation outcomes.
    """
    def __init__(self,max_age_seconds:int=300):self.max_age_seconds=max_age_seconds
    def assess(self,receipt:DeviceAttestationReceipt,*,new_device:bool=False,recovery_event:bool=False,now:int|None=None)->DeviceAssessment:
        current=int(time.time()) if now is None else int(now);reasons=[]
        if receipt.platform.lower() not in {"android","ios","web"}:reasons.append("UNSUPPORTED_PLATFORM")
        if not receipt.attestation_verified:reasons.append("ATTESTATION_NOT_VERIFIED")
        if not receipt.app_integrity_passed:reasons.append("APP_INTEGRITY_FAILED")
        if not receipt.device_integrity_passed:reasons.append("DEVICE_INTEGRITY_FAILED")
        if not receipt.nonce_verified:reasons.append("NONCE_NOT_VERIFIED")
        if current-receipt.issued_at>self.max_age_seconds:reasons.append("ATTESTATION_EXPIRED")
        if receipt.issued_at>current+60:reasons.append("ATTESTATION_IN_FUTURE")
        if receipt.risk_signals:reasons.extend(f"RISK:{x}" for x in receipt.risk_signals)
        if reasons:
            decision=DeviceDecision.HUMAN_REVIEW_REQUIRED if any(x in reasons for x in ("ATTESTATION_NOT_VERIFIED","APP_INTEGRITY_FAILED","DEVICE_INTEGRITY_FAILED")) else DeviceDecision.STEP_UP_REQUIRED
        elif new_device or recovery_event or not receipt.hardware_backed_key:
            decision=DeviceDecision.STEP_UP_REQUIRED;reasons.append("HIGH_RISK_DEVICE_OR_RECOVERY_EVENT")
        else:decision=DeviceDecision.TRUSTED;reasons.append("DEVICE_ATTESTATION_ACCEPTED")
        digest=hashlib.sha256(json.dumps({"platform":receipt.platform,"app_instance_id":receipt.app_instance_id,"device_key_id":receipt.device_key_id,"issued_at":receipt.issued_at},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return DeviceAssessment(decision,tuple(reasons),digest)
