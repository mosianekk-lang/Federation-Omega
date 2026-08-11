from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from enum import Enum
from .evidence_ref import is_concrete_evidence_ref
from .models import AssuranceLane

class RecipientAcceptanceDecision(str,Enum):
    VERIFIED="VERIFIED"
    HOLD="HOLD"

@dataclass(frozen=True)
class RecipientAcceptanceRule:
    rule_id:str
    recipient_id:str
    use_case:str
    document_type:str
    accepted_lanes:tuple[AssuranceLane,...]
    authority_evidence_ref:str
    effective_from:int
    expires_at:int|None
    last_verified_at:int

@dataclass(frozen=True)
class RecipientAcceptanceAssessment:
    decision:RecipientAcceptanceDecision
    rule_id:str
    reasons:tuple[str,...]
    evidence_digest:str

class RecipientAcceptanceGate:
    """Verify exact, current recipient acceptance before Lane 5 can be selected."""
    def __init__(self,max_rule_age_seconds:int=90*24*3600):self.max_rule_age_seconds=max_rule_age_seconds
    def assess(self,rule:RecipientAcceptanceRule,*,recipient_id:str,use_case:str,document_type:str,lane:AssuranceLane=AssuranceLane.INSTITUTION_ACCEPTED,now:int|None=None)->RecipientAcceptanceAssessment:
        current=int(time.time()) if now is None else int(now);reasons=[]
        if rule.recipient_id!=recipient_id:reasons.append("RECIPIENT_MISMATCH")
        if rule.use_case!=use_case:reasons.append("USE_CASE_MISMATCH")
        if rule.document_type!=document_type:reasons.append("DOCUMENT_TYPE_MISMATCH")
        if lane not in rule.accepted_lanes:reasons.append("LANE_NOT_ACCEPTED")
        if not is_concrete_evidence_ref(rule.authority_evidence_ref):reasons.append("RECIPIENT_AUTHORITY_EVIDENCE_MISSING")
        if current<rule.effective_from:reasons.append("RECIPIENT_RULE_NOT_YET_EFFECTIVE")
        if rule.expires_at is not None and current>rule.expires_at:reasons.append("RECIPIENT_RULE_EXPIRED")
        if current-rule.last_verified_at>self.max_rule_age_seconds:reasons.append("RECIPIENT_RULE_STALE")
        if rule.last_verified_at>current+60:reasons.append("RECIPIENT_RULE_VERIFIED_IN_FUTURE")
        digest=hashlib.sha256(json.dumps({"rule_id":rule.rule_id,"recipient_id":rule.recipient_id,"use_case":rule.use_case,"document_type":rule.document_type,"lanes":[x.value for x in rule.accepted_lanes],"authority_evidence_ref":rule.authority_evidence_ref,"effective_from":rule.effective_from,"expires_at":rule.expires_at,"last_verified_at":rule.last_verified_at},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return RecipientAcceptanceAssessment(RecipientAcceptanceDecision.HOLD if reasons else RecipientAcceptanceDecision.VERIFIED,rule.rule_id,tuple(reasons) if reasons else ("EXACT_RECIPIENT_ACCEPTANCE_RULE_VERIFIED",),digest)
