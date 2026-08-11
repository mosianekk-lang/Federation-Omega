from __future__ import annotations
import time
from dataclasses import dataclass
from .device_trust import DeviceAttestationReceipt
from .evidence_ref import is_concrete_evidence_ref

@dataclass(frozen=True)
class PlayIntegrityConfig:
    package_name:str
    max_age_millis:int=120000

class PlayIntegrityVerdictAdapter:
    """Normalize a server-decrypted, provider-verified Play Integrity verdict.

    Token decryption/provider authentication happens in the private runtime using
    Google Play's server-side API. This adapter validates request binding and verdict
    semantics before producing EvidenceOps device-trust evidence.
    """
    def __init__(self,config:PlayIntegrityConfig):self.config=config
    def assess(self,payload:dict,*,expected_request_hash:str,app_instance_id:str,provider_evidence_ref:str,high_risk:bool=False,now_millis:int|None=None)->DeviceAttestationReceipt:
        request=dict(payload.get("requestDetails") or {});app=dict(payload.get("appIntegrity") or {});device=dict(payload.get("deviceIntegrity") or {})
        current=int(time.time()*1000) if now_millis is None else int(now_millis);risk=[]
        provider_verified=is_concrete_evidence_ref(provider_evidence_ref)
        package_ok=str(request.get("requestPackageName",""))==self.config.package_name
        request_hash_ok=str(request.get("requestHash",""))==expected_request_hash
        try:issued_ms=int(request.get("timestampMillis",0))
        except Exception:issued_ms=0
        fresh=issued_ms>0 and 0<=current-issued_ms<=self.config.max_age_millis
        if not fresh:risk.append("PLAY_INTEGRITY_VERDICT_STALE_OR_FUTURE")
        app_ok=str(app.get("appRecognitionVerdict",""))=="PLAY_RECOGNIZED" and str(app.get("packageName",self.config.package_name))==self.config.package_name
        labels=set(device.get("deviceRecognitionVerdict") or ())
        device_ok="MEETS_DEVICE_INTEGRITY" in labels
        strong="MEETS_STRONG_INTEGRITY" in labels
        if high_risk and not strong:risk.append("MEETS_STRONG_INTEGRITY_REQUIRED")
        if not provider_verified:risk.append("GOOGLE_PROVIDER_VERIFICATION_EVIDENCE_MISSING")
        if not package_ok:risk.append("PLAY_REQUEST_PACKAGE_MISMATCH")
        if not request_hash_ok:risk.append("PLAY_REQUEST_HASH_MISMATCH")
        return DeviceAttestationReceipt(platform="android",app_instance_id=app_instance_id,device_key_id="",attestation_verified=bool(provider_verified and package_ok and request_hash_ok and fresh),hardware_backed_key=False,app_integrity_passed=app_ok,device_integrity_passed=bool(device_ok and (strong if high_risk else True)),nonce_verified=request_hash_ok,issued_at=issued_ms//1000 if issued_ms else 0,strong_platform_integrity=strong,risk_signals=tuple(risk))
