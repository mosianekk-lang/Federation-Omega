from __future__ import annotations
import base64,hashlib,hmac,json,time
from dataclasses import dataclass
from datetime import datetime,timezone
from .provider_adapter import ProviderCapabilities
from .receipt_auth import AuthenticatedReceipt,ReceiptEnvelope
from .replay import ReplayGuard,SQLiteReplayGuard

@dataclass(frozen=True)
class SmileIDConfig:
    partner_id:str
    signature_key:bytes
    key_id:str="smile-signature-key"
    max_age_seconds:int=300

class SmileIDProviderAdapter:
    """Smile ID callback adapter based on the provider's documented callback-signature contract.

    This adapter covers identity-authority-backed Biometric KYC-style results. Device
    integrity is intentionally not inferred from the provider callback and must be
    assessed independently by the EvidenceOps device-trust layer.
    """
    capabilities=ProviderCapabilities(
        provider_id="smile-id",
        south_africa_supported=True,
        one_to_one_identity_verification=True,
        live_presence_check=True,
        trusted_reference_check=True,
        document_verification=True,
        signed_receipts=True,
        raw_biometric_media_required_by_evidenceops=False,
        production_evidence_ref="UNBOUND_PROVIDER_CONTRACT_AND_PRODUCTION_READBACK",
    )
    def __init__(self,config:SmileIDConfig,replay_guard:ReplayGuard|None=None):
        self.config=config;self.replay_guard=replay_guard or SQLiteReplayGuard()

    @staticmethod
    def _epoch(value:str)->int:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    def _verify_signature(self,timestamp:str,signature:str)->bool:
        material=(timestamp+self.config.partner_id+"sid_request").encode()
        expected=base64.b64encode(hmac.new(self.config.signature_key,material,hashlib.sha256).digest()).decode()
        return hmac.compare_digest(expected,signature)

    @staticmethod
    def _transaction_id(callback:dict)->str:
        partner=callback.get("PartnerParams") or callback.get("partner_params") or {}
        return str(callback.get("SmileJobID") or callback.get("smile_job_id") or partner.get("job_id") or "").strip()

    @staticmethod
    def _contains_sensitive_media(callback:dict)->bool:
        compact={str(k).replace("_","").lower() for k in callback}
        return bool(compact & {"imagelinks","images","selfieimage","idphotoimage","kycreceipt"})

    def authenticate_callback(self,callback:dict,now:int|None=None)->AuthenticatedReceipt:
        timestamp=str(callback.get("timestamp","")).strip();signature=str(callback.get("signature","")).strip()
        if not timestamp or not signature:raise ValueError("SMILE_CALLBACK_SIGNATURE_FIELDS_MISSING")
        if not self._verify_signature(timestamp,signature):raise ValueError("SMILE_CALLBACK_SIGNATURE_INVALID")
        current=int(time.time()) if now is None else int(now);issued=self._epoch(timestamp)
        if issued>current+60:raise ValueError("SMILE_CALLBACK_ISSUED_IN_FUTURE")
        if current-issued>self.config.max_age_seconds:raise ValueError("SMILE_CALLBACK_EXPIRED")
        transaction_id=self._transaction_id(callback)
        if not transaction_id:raise ValueError("SMILE_CALLBACK_TRANSACTION_ID_MISSING")
        if not self.replay_guard.claim("smile-id",transaction_id):raise ValueError("SMILE_CALLBACK_REPLAY_DETECTED")

        actions=dict(callback.get("Actions") or callback.get("actions") or {})
        machine_liveness=str(actions.get("Liveness_Check","Not Applicable"))
        human_liveness=str(actions.get("Human_Review_Liveness_Check","Not Applicable"))
        liveness_passed=machine_liveness=="Passed" or human_liveness=="Passed"
        id_verified=str(actions.get("Verify_ID_Number","Not Applicable"))=="Verified"
        authority_compare=str(actions.get("Selfie_To_ID_Authority_Compare","Not Applicable"))=="Completed"
        verify_document=str(actions.get("Verify_Document","Not Applicable"))
        document_passed=verify_document=="Passed" if verify_document!="Not Applicable" else id_verified
        sensitive_media=self._contains_sensitive_media(callback)
        result_code=str(callback.get("ResultCode") or callback.get("result_code") or "")
        result_text=str(callback.get("ResultText") or callback.get("result_text") or "")
        verified=bool(liveness_passed and id_verified and authority_compare and document_passed and not sensitive_media)
        normalised={
            "transaction_id":transaction_id,
            "issued_at":timestamp,
            "verification_passed":verified,
            "live_presence_check_passed":liveness_passed,
            "trusted_reference_match_passed":bool(id_verified and authority_compare),
            "document_check_passed":document_passed,
            "provider_risk_level":"LOW" if verified else "REVIEW",
            "policy_version":"smile-id-biometric-kyc-callback-v1",
            "raw_sensitive_media_received_by_evidenceops":sensitive_media,
            "provider_result_code":result_code,
            "provider_result_text":result_text,
        }
        digest=hashlib.sha256(json.dumps(normalised,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        return AuthenticatedReceipt("smile-id",normalised,self.config.key_id,digest)

    def authenticate(self,envelope:ReceiptEnvelope)->AuthenticatedReceipt:
        return self.authenticate_callback(envelope.payload)

    def health(self)->dict[str,object]:
        return {"provider":"smile-id","adapter":"configured","production_evidence_bound":self.capabilities.production_evidence_ref!="UNBOUND_PROVIDER_CONTRACT_AND_PRODUCTION_READBACK"}
