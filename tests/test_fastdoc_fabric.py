import tempfile
import unittest
from pathlib import Path

from evidenceops.fastdoc_fabric.cache import SQLitePageStore
from evidenceops.fastdoc_fabric.engine import FastDocumentEngine
from evidenceops.fastdoc_fabric.models import PagePacket, ProcessingLane
from evidenceops.fastdoc_fabric.router import RoutingPolicy


class FakeAdapter:
    extractor = "fake"
    extractor_version = "1"

    def page_count(self, path):
        return 3

    def extract_document(self, path, workers=None):
        return [
            PagePacket(
                1,
                "A" * 120 + " January review reintegration",
                3,
                0,
                1.0,
                self.extractor,
                self.extractor_version,
            ),
            PagePacket(2, "", 0, 1, 1.0, self.extractor, self.extractor_version),
            PagePacket(
                3,
                "Useful text " * 20 + " deliberate refusal",
                4,
                0,
                1.0,
                self.extractor,
                self.extractor_version,
            ),
        ]


class RoutingPolicyTests(unittest.TestCase):
    def test_native_text_stays_fast(self):
        decision = RoutingPolicy().route(PagePacket(1, "word " * 50, image_count=0))
        self.assertEqual(decision.lane, ProcessingLane.NATIVE_FAST)

    def test_sparse_image_page_escalates(self):
        decision = RoutingPolicy().route(PagePacket(2, "", image_count=1))
        self.assertEqual(decision.lane, ProcessingLane.LAYOUT_OCR)


class CacheAndEngineTests(unittest.TestCase):
    def test_cold_then_warm_ingest_and_search(self):
        with tempfile.TemporaryDirectory() as td:
            store = SQLitePageStore(Path(td) / "fastdoc.sqlite")
            engine = FastDocumentEngine(FakeAdapter(), store)
            sample = Path(td) / "sample.pdf"
            sample.write_bytes(b"%PDF-1.7\nsynthetic")

            cold = engine.ingest(sample)
            self.assertEqual(cold.processed_pages, 3)
            self.assertEqual(cold.cache_hits, 0)
            self.assertEqual(cold.escalation_pages, (2,))

            hits = store.search(cold.document_sha256, "January reintegration")
            self.assertTrue(hits)
            self.assertEqual(hits[0].page_number, 1)

            warm = engine.ingest(sample)
            self.assertEqual(warm.processed_pages, 0)
            self.assertEqual(warm.cache_hits, 3)
            self.assertEqual(warm.escalation_pages, (2,))
            store.close()


if __name__ == "__main__":
    unittest.main()
