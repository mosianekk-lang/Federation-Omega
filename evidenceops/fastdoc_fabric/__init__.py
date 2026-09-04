"""EvidenceOps FastDoc Fabric: fast-path-first, cache-first document intelligence."""

# v1 compatibility surface
from .cache import SQLitePageStore
from .engine import FastDocumentEngine, sha256_file
from .evidenceops_bridge import EvidenceOpsFastDocBridge, EvidenceOpsFastDocReceipt
from .models import IngestReceipt, PagePacket, ProcessingLane, RoutingDecision, SearchHit
from .pymupdf_adapter import PyMuPDFAdapter
from .router import RoutingPolicy
from .tesseract_adapter import OCRReceipt, SelectiveLocalOCR, TesseractOCRAdapter
from .visual_resolver import QueryDrivenPageResolver, RenderedPage

# v2 staged successor surface
from .v2 import (
    ContextPack,
    ContextPackBuilder,
    FastDocV2,
    FastDocV2Config,
    FastDocV2Receipt,
    LatencyProfile,
    OCRV2Receipt,
    PageV2,
    SearchHitV2,
    SQLiteContentStoreV2,
)

__all__ = [
    "ContextPack",
    "ContextPackBuilder",
    "EvidenceOpsFastDocBridge",
    "EvidenceOpsFastDocReceipt",
    "FastDocV2",
    "FastDocV2Config",
    "FastDocV2Receipt",
    "FastDocumentEngine",
    "IngestReceipt",
    "LatencyProfile",
    "OCRReceipt",
    "OCRV2Receipt",
    "PagePacket",
    "PageV2",
    "ProcessingLane",
    "PyMuPDFAdapter",
    "QueryDrivenPageResolver",
    "RenderedPage",
    "RoutingDecision",
    "RoutingPolicy",
    "SQLiteContentStoreV2",
    "SQLitePageStore",
    "SearchHit",
    "SearchHitV2",
    "SelectiveLocalOCR",
    "TesseractOCRAdapter",
    "sha256_file",
]
