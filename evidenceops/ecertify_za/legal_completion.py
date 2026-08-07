from __future__ import annotations
import hashlib,re,time
from dataclasses import dataclass
from enum import Enum
from .commissioner_authority import CommissionerAuthorityAssessment,CommissionerAuthorityDecision
from .evidence_ref import is_concrete_evidence_ref
from .models import AssuranceLane,CertificationRoute

class CommissionerEventType(str,Enum):
    CERTIFY_COPY="CERTIFY_COPY"
    COMMISSION_AFFIDAVIT="COMMISSION_AFFIDAVIT"

class LegalCompletionDecision(str,Enum):
    VERIFIED="VERIFIED"
    HOLD="HOLD"

@dataclass(frozen=True)
class CommissionerEvent:
    event_id:str
    transaction_id:str
    commissioner_id:str
    event_type:CommissionerEventType
    document_sha256:str
    event_timestamp:int
    event_evidence_ref:str
    conflict_clearance_ref:str
    original_inspected:bool=False
    physical_presence:bool=False
    deponent_signed_in_presence:bool=False

@dataclass(frozen=True)
class LegalCompletionAssessment:
    decision:LegalCompletionDecision
    final_label:str
    reasons:tuple[str,...]
    evidence_digest:str
    event_id:str

class LegalCompletionGate:
    """Release final legal labels only after verified authority and transaction-bound event evidence."""
    def __init__(self,max_future_skew_seconds:int=60):self.max_future_skew_seconds=max_future_skew_seconds
    def assess(self,route:CertificationRoute,authority:CommissionerAuthorityAssessment,event:CommissionerEvent,*,expected_document_sha256:str,expected_transaction_id:str,now:int|None=None)->LegalCompletionAssessment:
        current=int(time.time()) if now is None else int(now);reasons=[];final_label=route.final_label
        if authority.decision!=CommissionerAuthorityDecision.VERIFIED:reasons.append("COMMISSIONER_AUTHORITY_NOT_VERIFIED")
        if authority.commissioner_id!=event.commissioner_id:reasons.append("COMMISSIONER_ID_MISMATCH")
        if event.transaction_id!=expected_transaction_id:reasons.append("LEGAL_EVENT_TRANSACTION_MISMATCH")
        if not re.fullmatch(r"[0-9a-fA-F]{64}",event.document_sha256):reasons.append("DOCUMENT_HASH_INVALID")
        elif event.document_sha256.lower()!=expected_document_sha256.lower():reasons.append("LEGAL_EVENT_DOCUMENT_HASH_MISMATCH")
        if not is_concrete_evidence_ref(event.event_evidence_ref):reasons.append("LEGAL_EVENT_EVIDENCE_MISSING")
        if not is_concrete_evidence_ref(event.conflict_clearance_ref):reasons.append("COMMISSIONER_CONFLICT_CLEARANCE_MISSING")
        if event.event_timestamp>current+self.max_future_skew_seconds:reasons.append("LEGAL_EVENT_IN_FUTURE")
        if route.lane==AssuranceLane.CERTIFIED_COPY:
            if event.event_type!=CommissionerEventType.CERTIFY_COPY:reasons.append("LEGAL_EVENT_TYPE_MISMATCH")
            if not event.original_inspected:reasons.append("ORIGINAL_DOCUMENT_INSPECTION_NOT_PROVED")
            if not reasons:final_label="CERTIFIED_COPY"
        elif route.lane==AssuranceLane.AFFIDAVIT:
            if event.event_type!=CommissionerEventType.COMMISSION_AFFIDAVIT:reasons.append("LEGAL_EVENT_TYPE_MISMATCH")
            if not event.physical_presence:reasons.append("PHYSICAL_PRESENCE_NOT_PROVED")
            if not event.deponent_signed_in_presence:reasons.append("DEPONENT_SIGNATURE_IN_PRESENCE_NOT_PROVED")
            if not reasons:final_label="COMMISSIONED_AFFIDAVIT"
        else:reasons.append("ROUTE_DOES_NOT_REQUIRE_COMMISSIONER_COMPLETION")
        digest=hashlib.sha256(f"{authority.evidence_digest}|{event.event_id}|{event.transaction_id}|{event.commissioner_id}|{event.event_type.value}|{event.document_sha256}|{event.event_timestamp}|{event.event_evidence_ref}|{event.conflict_clearance_ref}|{expected_transaction_id}|{expected_document_sha256}".encode()).hexdigest()
        return LegalCompletionAssessment(LegalCompletionDecision.HOLD if reasons else LegalCompletionDecision.VERIFIED,final_label,tuple(reasons) if reasons else ("AUTHORITY_TRANSACTION_AND_LEGAL_EVENT_VERIFIED",),digest,event.event_id)
