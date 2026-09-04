from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from evidenceops.ecertify_za.document_intake import DocumentIntakeResult
from evidenceops.ecertify_za.document_security import (
    DocumentSecurityAssessment,
    DocumentSecurityDecision,
)

from .engine import FastDocumentEngine
from .models import IngestReceipt


@dataclass(frozen=True)
class EvidenceOpsFastDocReceipt:
    document_sha256: str
    security_evidence_digest: str
    page_count: int
    ingest: IngestReceipt


class EvidenceOpsFastDocBridge:
    """Bind FastDoc behind existing EvidenceOps intake/security proof gates.

    Fast parsing never bypasses malware/DLP/content validation. The exact file hash
    must agree across intake, security and FastDoc receipts before a result is
    accepted.
    """

    def __init__(self, engine: FastDocumentEngine) -> None:
        self.engine = engine

    def process_verified_pdf(
        self,
        path: str | Path,
        *,
        intake: DocumentIntakeResult,
        security: DocumentSecurityAssessment,
        workers: int | None = None,
    ) -> EvidenceOpsFastDocReceipt:
        if intake.detected_type != "application/pdf":
            raise ValueError("FASTDOC_REQUIRES_PDF")
        if security.decision != DocumentSecurityDecision.VERIFIED:
            raise PermissionError("DOCUMENT_SECURITY_NOT_VERIFIED")
        if security.document_sha256.lower() != intake.sha256.lower():
            raise ValueError("SECURITY_INTAKE_HASH_MISMATCH")

        ingest = self.engine.ingest(path, workers=workers)
        if ingest.document_sha256.lower() != intake.sha256.lower():
            raise ValueError("FASTDOC_INTAKE_HASH_MISMATCH")
        return EvidenceOpsFastDocReceipt(
            document_sha256=ingest.document_sha256,
            security_evidence_digest=security.evidence_digest,
            page_count=ingest.page_count,
            ingest=ingest,
        )
