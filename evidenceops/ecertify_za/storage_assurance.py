from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from enum import Enum
from .document_security import DocumentSecurityAssessment,DocumentSecurityDecision
from .evidence_ref import is_concrete_evidence_ref

class StorageAssuranceDecision(str,Enum):
    VERIFIED="VERIFIED"
    HOLD="HOLD"

@dataclass(frozen=True)
class StorageCommitReceipt:
    object_id:str
    object_version:str
    document_sha256:str
    encryption_evidence_ref:str
    storage_evidence_ref:str
    retention_policy_ref:str
    deletion_due_at:int|None
    private_access_only:bool

@dataclass(frozen=True)
class SecureDocumentAssessment:
    decision:StorageAssuranceDecision
    document_sha256:str
    object_id:str
    reasons:tuple[str,...]
    evidence_digest:str

class StorageAssuranceGate:
    """Release a document into the assurance workflow only after security and encrypted-storage proof."""
    def assess(self,security:DocumentSecurityAssessment,receipt:StorageCommitReceipt)->SecureDocumentAssessment:
        reasons=[]
        if security.decision!=DocumentSecurityDecision.VERIFIED:reasons.append("DOCUMENT_SECURITY_NOT_VERIFIED")
        if security.document_sha256.lower()!=receipt.document_sha256.lower():reasons.append("STORAGE_DOCUMENT_HASH_MISMATCH")
        if not receipt.object_id.strip() or not receipt.object_version.strip():reasons.append("STORAGE_OBJECT_IDENTITY_MISSING")
        if not is_concrete_evidence_ref(receipt.encryption_evidence_ref):reasons.append("ENCRYPTION_EVIDENCE_MISSING")
        if not is_concrete_evidence_ref(receipt.storage_evidence_ref):reasons.append("STORAGE_READBACK_EVIDENCE_MISSING")
        if not is_concrete_evidence_ref(receipt.retention_policy_ref):reasons.append("RETENTION_POLICY_EVIDENCE_MISSING")
        if not receipt.private_access_only:reasons.append("DOCUMENT_STORAGE_NOT_PRIVATE")
        digest=hashlib.sha256(json.dumps({"security_digest":security.evidence_digest,"object_id":receipt.object_id,"object_version":receipt.object_version,"document_sha256":receipt.document_sha256,"encryption_evidence_ref":receipt.encryption_evidence_ref,"storage_evidence_ref":receipt.storage_evidence_ref,"retention_policy_ref":receipt.retention_policy_ref,"deletion_due_at":receipt.deletion_due_at,"private_access_only":receipt.private_access_only},sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return SecureDocumentAssessment(StorageAssuranceDecision.HOLD if reasons else StorageAssuranceDecision.VERIFIED,security.document_sha256,receipt.object_id,tuple(reasons) if reasons else ("SECURE_PRIVATE_STORAGE_AND_RETENTION_VERIFIED",),digest)
