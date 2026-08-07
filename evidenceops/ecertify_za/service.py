from __future__ import annotations
import hashlib, secrets
from dataclasses import asdict
from .identity_receipt import IdentityDecision, IdentityReceiptGate, ProviderVerificationReceipt
from .legal import CertificationRouteEngine
from .ledger import HashChainLedger
from .models import VerificationRecord

class ECertifyService:
    def __init__(self, ledger:HashChainLedger|None=None):
        self.identity=IdentityReceiptGate(); self.routes=CertificationRouteEngine(); self.ledger=ledger or HashChainLedger()

    @staticmethod
    def sha256_document(document_bytes:bytes)->str:
        return hashlib.sha256(document_bytes).hexdigest()

    def assess_identity(self,receipt:ProviderVerificationReceipt,consent_granted:bool):
        result=self.identity.assess(receipt,consent_granted)
        self.ledger.append("IDENTITY_PROVIDER_RECEIPT",{"decision":result.decision.value,"evidence_digest":result.evidence_digest,"provider_transaction_id":result.provider_transaction_id,"reasons":result.reasons})
        return result

    def create_verification_record(self,*,document_bytes:bytes,requested_status:str,identity_assessment,recipient_accepts_digital_assurance:bool=False)->VerificationRecord:
        route=self.routes.route(requested_status,recipient_accepts_digital_assurance)
        status="READY_FOR_NEXT_GATE"
        if route.identity_requirement=="VERIFIED_IDENTITY" and identity_assessment.decision!=IdentityDecision.VERIFIED: status="IDENTITY_GATE_OPEN"
        if route.commissioner_required: status="COMMISSIONER_EVENT_REQUIRED"
        record=VerificationRecord("EOZA-"+secrets.token_hex(6).upper(),self.sha256_document(document_bytes),identity_assessment.evidence_digest,route.lane,route.final_label,status,{"commissioner_required":str(route.commissioner_required).lower()})
        self.ledger.append("DOCUMENT_ASSURANCE_RECORD",asdict(record))
        return record
