from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from enum import Enum
from .document_intake import DocumentIntakeResult,IntakeDecision
from .evidence_ref import is_concrete_evidence_ref

class DocumentSecurityDecision(str,Enum):
    VERIFIED="VERIFIED"
    HOLD="HOLD"
    REJECT="REJECT"

@dataclass(frozen=True)
class DocumentSecurityScanReceipt:
    scanner_id:str
    document_sha256:str
    malware_verdict:str
    dlp_verdict:str
    content_validation_verdict:str
    scanner_policy_version:str
    issued_at:int
    evidence_ref:str

@dataclass(frozen=True)
class DocumentSecurityAssessment:
    decision:DocumentSecurityDecision
    document_sha256:str
    reasons:tuple[str,...]
    evidence_digest:str

class DocumentSecurityGate:
    """Require clean malware/DLP/content receipts before a document can be storage-ready."""
    def __init__(self,max_receipt_age_seconds:int=900):self.max_receipt_age_seconds=max_receipt_age_seconds
    def assess(self,intake:DocumentIntakeResult,receipt:DocumentSecurityScanReceipt,now:int|None=None)->DocumentSecurityAssessment:
        current=int(time.time()) if now is None else int(now);reasons=[];reject=False
        if intake.decision==IntakeDecision.REJECT:reasons.append("DOCUMENT_INTAKE_REJECTED");reject=True
        if intake.sha256.lower()!=receipt.document_sha256.lower():reasons.append("SECURITY_SCAN_DOCUMENT_HASH_MISMATCH");reject=True
        if not is_concrete_evidence_ref(receipt.evidence_ref):reasons.append("SECURITY_SCAN_EVIDENCE_MISSING")
        malware=receipt.malware_verdict.strip().upper();dlp=receipt.dlp_verdict.strip().upper();content=receipt.content_validation_verdict.strip().upper()
        if malware not in {"CLEAN"}:reasons.append("MALWARE_SCAN_NOT_CLEAN");reject=malware in {"MALICIOUS","INFECTED","BLOCK"}
        if dlp not in {"PASS","REDACTED_PASS"}:reasons.append("DLP_NOT_CLEARED")
        if content not in {"PASS"}:reasons.append("CONTENT_VALIDATION_NOT_CLEARED")
        if current-receipt.issued_at>self.max_receipt_age_seconds:reasons.append("SECURITY_SCAN_RECEIPT_STALE")
        if receipt.issued_at>current+60:reasons.append("SECURITY_SCAN_RECEIPT_IN_FUTURE")
        digest=hashlib.sha256(json.dumps({"intake_sha256":intake.sha256,"scanner_id":receipt.scanner_id,"document_sha256":receipt.document_sha256,"malware_verdict":receipt.malware_verdict,"dlp_verdict":receipt.dlp_verdict,"content_validation_verdict":receipt.content_validation_verdict,"scanner_policy_version":receipt.scanner_policy_version,"issued_at":receipt.issued_at,"evidence_ref":receipt.evidence_ref},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        decision=DocumentSecurityDecision.REJECT if reject else (DocumentSecurityDecision.HOLD if reasons else DocumentSecurityDecision.VERIFIED)
        return DocumentSecurityAssessment(decision,intake.sha256,tuple(reasons) if reasons else ("MALWARE_DLP_AND_CONTENT_SECURITY_VERIFIED",),digest)
