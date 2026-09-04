import hashlib
import tempfile
import unittest
from pathlib import Path

from evidenceops.ecertify_za.document_intake import DocumentIntakeResult, IntakeDecision
from evidenceops.ecertify_za.document_security import (
    DocumentSecurityAssessment,
    DocumentSecurityDecision,
)
from evidenceops.fastdoc_fabric.cache import SQLitePageStore
from evidenceops.fastdoc_fabric.engine import FastDocumentEngine
from evidenceops.fastdoc_fabric.evidenceops_bridge import EvidenceOpsFastDocBridge
from evidenceops.fastdoc_fabric.models import PagePacket, SearchHit
from evidenceops.fastdoc_fabric.tesseract_adapter import SelectiveLocalOCR
from evidenceops.fastdoc_fabric.visual_resolver import QueryDrivenPageResolver


class FakeAdapter:
    extractor = "fake-native"
    extractor_version = "1"

    def page_count(self, path):
        return 1

    def extract_document(self, path, workers=None):
        return [PagePacket(1, "trusted page text " * 10, extractor=self.extractor, extractor_version=self.extractor_version)]


class FakeOCR:
    extractor = "fake-ocr"
    extractor_version = "1"

    def extract_pages(self, path, page_numbers, *, dpi=120, language="eng"):
        return [
            PagePacket(
                int(n),
                f"ocr page {n} decisive scanned evidence",
                extractor=self.extractor,
                extractor_version=self.extractor_version,
            )
            for n in page_numbers
        ]


class FastDocIntegrationTests(unittest.TestCase):
    def test_security_bridge_requires_hash_bound_verified_document(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.pdf"
            path.write_bytes(b"%PDF-1.7\nfastdoc")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            intake = DocumentIntakeResult(
                IntakeDecision.HOLD_FOR_SCAN,
                ("MALWARE_AND_DLP_SCAN_REQUIRED",),
                sha,
                "application/pdf",
                path.stat().st_size,
            )
            security = DocumentSecurityAssessment(
                DocumentSecurityDecision.VERIFIED,
                sha,
                ("MALWARE_DLP_AND_CONTENT_SECURITY_VERIFIED",),
                "security-digest",
            )
            store = SQLitePageStore(Path(td) / "db.sqlite")
            bridge = EvidenceOpsFastDocBridge(FastDocumentEngine(FakeAdapter(), store))
            receipt = bridge.process_verified_pdf(path, intake=intake, security=security)
            self.assertEqual(receipt.document_sha256, sha)
            self.assertEqual(receipt.page_count, 1)
            store.close()

    def test_selective_ocr_is_cache_first(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.pdf"
            path.write_bytes(b"%PDF-1.7\nfastdoc")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            store = SQLitePageStore(Path(td) / "db.sqlite")
            runner = SelectiveLocalOCR(store, adapter=FakeOCR())
            first = runner.enrich(path, sha, [2, 5])
            second = runner.enrich(path, sha, [2, 5])
            self.assertEqual(first.processed_pages, (2, 5))
            self.assertEqual(second.processed_pages, ())
            self.assertEqual(second.cache_hits, 2)
            self.assertEqual(store.search(sha, "decisive scanned evidence")[0].page_number, 2)
            store.close()

    def test_query_driven_renderer_caps_and_dedupes_pages(self):
        resolver = QueryDrivenPageResolver(max_pages=3)
        hits = [SearchHit(7, -1.0, ""), SearchHit(7, -0.5, ""), SearchHit(2, -0.2, "")]
        self.assertEqual(resolver.select(hits, [9, 10]), (7, 2, 9))


if __name__ == "__main__":
    unittest.main()
