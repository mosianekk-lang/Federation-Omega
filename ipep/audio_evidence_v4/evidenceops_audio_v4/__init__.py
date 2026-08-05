"""EvidenceOps Audio Evidence Completion System v4."""

from .gates import quotation_release_gate, transcript_certification_gate
from .index import EvidenceIndex
from .ledger import EvidenceLedger, LedgerError
from .legacy import import_legacy_whisper_run
from .models import (
    CustodyEvent,
    EvidenceItem,
    HumanReview,
    QuoteRequest,
    TranscriptSegment,
    TranslationRecord,
    UnitReceipt,
)
from .pipeline import AudioEvidenceCompletionPipeline
from .providers import CommandTranslationAdapter, WhisperCppConfig, WhisperCppUnitAdapter

__all__ = [
    "AudioEvidenceCompletionPipeline",
    "CommandTranslationAdapter",
    "CustodyEvent",
    "EvidenceIndex",
    "EvidenceItem",
    "EvidenceLedger",
    "HumanReview",
    "LedgerError",
    "QuoteRequest",
    "TranscriptSegment",
    "TranslationRecord",
    "UnitReceipt",
    "WhisperCppConfig",
    "WhisperCppUnitAdapter",
    "import_legacy_whisper_run",
    "quotation_release_gate",
    "transcript_certification_gate",
]

__version__ = "4.0.0"
