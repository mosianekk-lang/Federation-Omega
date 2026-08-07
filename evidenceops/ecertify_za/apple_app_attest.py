from __future__ import annotations
from dataclasses import dataclass
from .device_trust import DeviceAttestationReceipt
from .evidence_ref import is_concrete_evidence_ref

@dataclass(frozen=True)
class AppleAppAttestConfig:
    app_id:str
    environment:str="production"
    allowed_validation_categories:tuple[int,...]=(4,)

@dataclass(frozen=True)
class AppleVerifiedAssertion:
    app_id:str
    app_instance_id:str
    key_id:str
    environment:str
    challenge:str
    assertion_counter:int
    validation_category:int
    bundle_version:str
    issued_at:int
    provider_evidence_ref:str

class AppleAppAttestAdapter:
    """Normalize a private-runtime verified Apple App Attest assertion.

    The private verifier must perform Apple's certificate-chain/attestation/assertion
    cryptographic validation first. This layer then checks transaction/app binding,
    environment and monotonic counter semantics before producing device-trust evidence.
    """
    def __init__(self,config:AppleAppAttestConfig):self.config=config
    def assess(self,result:AppleVerifiedAssertion,*,expected_challenge:str,previous_counter:int=0)->DeviceAttestationReceipt:
        risk=[];evidence_ok=is_concrete_evidence_ref(result.provider_evidence_ref)
        app_ok=result.app_id==self.config.app_id
        challenge_ok=result.challenge==expected_challenge
        env_ok=result.environment==self.config.environment
        counter_ok=result.assertion_counter>previous_counter and result.assertion_counter>0
        category_ok=result.validation_category in self.config.allowed_validation_categories
        if not evidence_ok:risk.append("APPLE_PROVIDER_VERIFICATION_EVIDENCE_MISSING")
        if not app_ok:risk.append("APPLE_APP_ID_MISMATCH")
        if not challenge_ok:risk.append("APPLE_CHALLENGE_MISMATCH")
        if not env_ok:risk.append("APPLE_ATTEST_ENVIRONMENT_MISMATCH")
        if not counter_ok:risk.append("APPLE_ASSERTION_COUNTER_NOT_MONOTONIC")
        if not category_ok:risk.append("APPLE_VALIDATION_CATEGORY_NOT_ALLOWED")
        verified=bool(evidence_ok and app_ok and challenge_ok and env_ok and counter_ok and category_ok)
        return DeviceAttestationReceipt(platform="ios",app_instance_id=result.app_instance_id,device_key_id=result.key_id,attestation_verified=verified,hardware_backed_key=verified,app_integrity_passed=bool(app_ok and env_ok and category_ok),device_integrity_passed=verified,nonce_verified=challenge_ok,issued_at=result.issued_at,strong_platform_integrity=verified,risk_signals=tuple(risk))
