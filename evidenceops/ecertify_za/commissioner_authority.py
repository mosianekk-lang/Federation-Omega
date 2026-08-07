from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from enum import Enum
from .evidence_ref import is_concrete_evidence_ref

class CommissionerAuthorityDecision(str,Enum):
    VERIFIED="VERIFIED"
    HOLD="HOLD"

@dataclass(frozen=True)
class CommissionerAuthorityRecord:
    commissioner_id:str
    designation_type:str
    identity_evidence_ref:str
    authority_source_ref:str
    current_capacity_evidence_ref:str
    valid_from:int
    valid_to:int|None
    authority_checked_at:int

@dataclass(frozen=True)
class CommissionerAuthorityAssessment:
    decision:CommissionerAuthorityDecision
    commissioner_id:str
    reasons:tuple[str,...]
    evidence_digest:str

class CommissionerAuthorityGate:
    """Verify current personal/ex-officio authority before assigning a legal event."""
    def __init__(self,max_authority_age_seconds:int=30*24*3600):self.max_authority_age_seconds=max_authority_age_seconds
    def assess(self,record:CommissionerAuthorityRecord,now:int|None=None)->CommissionerAuthorityAssessment:
        current=int(time.time()) if now is None else int(now);reasons=[];kind=record.designation_type.strip().upper()
        if kind not in {"PERSONAL","EX_OFFICIO"}:reasons.append("UNSUPPORTED_DESIGNATION_TYPE")
        if not is_concrete_evidence_ref(record.identity_evidence_ref):reasons.append("COMMISSIONER_IDENTITY_EVIDENCE_MISSING")
        if not is_concrete_evidence_ref(record.authority_source_ref):reasons.append("COMMISSIONER_AUTHORITY_SOURCE_MISSING")
        if kind=="EX_OFFICIO" and not is_concrete_evidence_ref(record.current_capacity_evidence_ref):reasons.append("CURRENT_EX_OFFICIO_CAPACITY_EVIDENCE_MISSING")
        if current<record.valid_from:reasons.append("COMMISSIONER_AUTHORITY_NOT_YET_EFFECTIVE")
        if record.valid_to is not None and current>record.valid_to:reasons.append("COMMISSIONER_AUTHORITY_EXPIRED")
        if current-record.authority_checked_at>self.max_authority_age_seconds:reasons.append("COMMISSIONER_AUTHORITY_STALE")
        if record.authority_checked_at>current+60:reasons.append("COMMISSIONER_AUTHORITY_CHECK_IN_FUTURE")
        digest=hashlib.sha256(json.dumps({"commissioner_id":record.commissioner_id,"designation_type":kind,"identity_evidence_ref":record.identity_evidence_ref,"authority_source_ref":record.authority_source_ref,"current_capacity_evidence_ref":record.current_capacity_evidence_ref,"valid_from":record.valid_from,"valid_to":record.valid_to,"authority_checked_at":record.authority_checked_at},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return CommissionerAuthorityAssessment(CommissionerAuthorityDecision.HOLD if reasons else CommissionerAuthorityDecision.VERIFIED,record.commissioner_id,tuple(reasons) if reasons else ("COMMISSIONER_AUTHORITY_CURRENT_AND_VERIFIED",),digest)
