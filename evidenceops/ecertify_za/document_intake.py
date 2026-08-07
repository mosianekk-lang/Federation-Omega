from __future__ import annotations
import hashlib
from dataclasses import dataclass
from enum import Enum

class IntakeDecision(str,Enum):
    ACCEPT_REFERENCE="ACCEPT_REFERENCE"
    HOLD_FOR_SCAN="HOLD_FOR_SCAN"
    REJECT="REJECT"

@dataclass(frozen=True)
class DocumentIntakeResult:
    decision:IntakeDecision
    reasons:tuple[str,...]
    sha256:str
    detected_type:str
    size_bytes:int

class DocumentIntakePolicy:
    """Pre-storage intake gate. Malware/DLP services remain separate required controls."""
    MAX_BYTES=25*1024*1024
    def detect_type(self,data:bytes)->str:
        if data.startswith(b"%PDF-"):return "application/pdf"
        if data.startswith(b"\xff\xd8\xff"):return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):return "image/png"
        if data.startswith((b"RIFF",)) and data[8:12]==b"WEBP":return "image/webp"
        return "application/octet-stream"
    def assess(self,data:bytes,declared_type:str="")->DocumentIntakeResult:
        digest=hashlib.sha256(data).hexdigest();detected=self.detect_type(data);reasons=[]
        if not data:reasons.append("EMPTY_DOCUMENT")
        if len(data)>self.MAX_BYTES:reasons.append("DOCUMENT_TOO_LARGE")
        if detected=="application/octet-stream":reasons.append("UNSUPPORTED_OR_UNKNOWN_FILE_TYPE")
        if declared_type and declared_type.lower()!=detected:reasons.append("DECLARED_TYPE_MISMATCH")
        if reasons:return DocumentIntakeResult(IntakeDecision.REJECT,tuple(reasons),digest,detected,len(data))
        return DocumentIntakeResult(IntakeDecision.HOLD_FOR_SCAN,("MALWARE_AND_DLP_SCAN_REQUIRED",),digest,detected,len(data))
