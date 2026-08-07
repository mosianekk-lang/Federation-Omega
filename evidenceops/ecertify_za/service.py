from __future__ import annotations
import hashlib,secrets
from dataclasses import asdict,replace
from .commissioner_authority import CommissionerAuthorityAssessment
from .identity_receipt import IdentityDecision,IdentityReceiptGate
from .legal import CertificationRouteEngine
from .legal_completion import CommissionerEvent,LegalCompletionDecision,LegalCompletionGate
from .ledger import HashChainLedger
from .models import AssuranceLane,CertificationRoute,VerificationRecord
from .receipt_auth import AuthenticatedReceipt,HMACReceiptAuthenticator,ReceiptEnvelope
from .recipient_acceptance import RecipientAcceptanceAssessment

class ECertifyService:
    def __init__(self,ledger:HashChainLedger|None=None,authenticator:HMACReceiptAuthenticator|None=None):
        self.identity=IdentityReceiptGate();self.routes=CertificationRouteEngine();self.completion=LegalCompletionGate();self.ledger=ledger or HashChainLedger();self.authenticator=authenticator;self._closed=False
    @staticmethod
    def sha256_document(document_bytes:bytes)->str:return hashlib.sha256(document_bytes).hexdigest()
    def authenticate_identity_receipt(self,envelope:ReceiptEnvelope,consent_granted:bool):
        if self.authenticator is None:raise RuntimeError("IDENTITY_AUTHENTICATOR_NOT_CONFIGURED")
        return self.assess_identity(self.authenticator.verify(envelope),consent_granted)
    def assess_identity(self,authenticated:AuthenticatedReceipt,consent_granted:bool):
        result=self.identity.assess(authenticated,consent_granted);self.ledger.append("IDENTITY_PROVIDER_RECEIPT",{"decision":result.decision.value,"evidence_digest":result.evidence_digest,"provider_transaction_id":result.provider_transaction_id,"reasons":result.reasons,"provider":authenticated.provider,"payload_sha256":authenticated.payload_sha256,"key_id":authenticated.key_id});return result
    def create_verification_record(self,*,document_bytes:bytes,requested_status:str,identity_assessment,recipient_acceptance:RecipientAcceptanceAssessment|None=None)->VerificationRecord:
        route=self.routes.route(requested_status,recipient_acceptance);status="READY_FOR_NEXT_GATE"
        if route.identity_requirement=="VERIFIED_IDENTITY" and identity_assessment.decision!=IdentityDecision.VERIFIED:status="IDENTITY_GATE_OPEN"
        if route.commissioner_required:status="COMMISSIONER_EVENT_REQUIRED"
        metadata={"commissioner_required":str(route.commissioner_required).lower()}
        if recipient_acceptance is not None:
            metadata={**metadata,"recipient_rule_id":recipient_acceptance.rule_id,"recipient_acceptance_digest":recipient_acceptance.evidence_digest}
        record=VerificationRecord("EOZA-"+secrets.token_hex(6).upper(),self.sha256_document(document_bytes),identity_assessment.evidence_digest,route.lane,route.final_label,status,metadata);self.ledger.append("DOCUMENT_ASSURANCE_RECORD",asdict(record));return record
    def complete_legal_event(self,record:VerificationRecord,authority:CommissionerAuthorityAssessment,event:CommissionerEvent,*,now:int|None=None)->VerificationRecord:
        route=CertificationRoute(record.lane,record.legal_label,record.lane in {AssuranceLane.CERTIFIED_COPY,AssuranceLane.AFFIDAVIT},record.lane==AssuranceLane.AFFIDAVIT,"VERIFIED_IDENTITY",())
        result=self.completion.assess(route,authority,event,expected_document_sha256=record.document_sha256,expected_transaction_id=record.verification_code,now=now)
        self.ledger.append("LEGAL_COMPLETION_EVENT",{"decision":result.decision.value,"event_id":result.event_id,"evidence_digest":result.evidence_digest,"reasons":result.reasons,"verification_code":record.verification_code,"document_sha256":record.document_sha256})
        if result.decision!=LegalCompletionDecision.VERIFIED:return record
        return replace(record,legal_label=result.final_label,status="LEGAL_EVENT_VERIFIED",metadata={**record.metadata,"legal_event_id":result.event_id,"legal_completion_digest":result.evidence_digest})
    def close(self)->None:
        if self._closed:return
        close_replay=getattr(getattr(self.authenticator,"replay_store",None),"close",None)
        if callable(close_replay):close_replay()
        close_ledger=getattr(self.ledger,"close",None)
        if callable(close_ledger):close_ledger()
        self._closed=True
    def __enter__(self):return self
    def __exit__(self,exc_type,exc,tb):self.close();return False
