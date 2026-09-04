from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from evidenceops.fastdoc_fabric.v2 import (
    ContextPackBuilder,
    FastDocV2,
    FastDocV2Config,
    LatencyProfile,
    SQLiteContentStoreV2,
    _pymupdf_version,
)


def make_pdf(path: Path, pages: list[str]) -> None:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(72, 72, 540, 770), text, fontsize=9)
    doc.save(path)
    doc.close()


class FastDocV2Tests(unittest.TestCase):
    def test_profile_defaults(self):
        self.assertEqual(16, FastDocV2Config(profile=LatencyProfile.INTERACTIVE).resolved(100).batch_pages)
        self.assertEqual(32, FastDocV2Config(profile=LatencyProfile.THROUGHPUT).resolved(100).batch_pages)

    def test_cold_warm_and_search_context(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "sample.pdf"
            make_pdf(pdf, ["alpha charge evidence " * 10, "beta working home proof " * 10, "gamma report " * 10])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            cfg = FastDocV2Config(workers=1, batch_pages=1, context_max_chars=2000)
            engine = FastDocV2(store, cfg)
            cold = engine.ingest(pdf)
            self.assertEqual(3, cold.processed_pages)
            self.assertFalse(cold.warm_unchanged)
            warm = engine.ingest(pdf)
            self.assertTrue(warm.warm_unchanged)
            self.assertEqual(0, warm.processed_pages)
            hits = store.search(cold.document_sha256, "working home")
            self.assertTrue(hits)
            self.assertEqual(2, hits[0].page_number)
            pack = ContextPackBuilder(store, cfg).build(
                document_sha256=cold.document_sha256,
                extractor_version=_pymupdf_version(),
                query="working home",
            )
            self.assertTrue(pack.pages)
            self.assertLessEqual(pack.total_chars, 2000)
            self.assertIn(2, [p.page_number for p in pack.pages])
            store.close()

    def test_partial_resume_only_missing_page(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "resume.pdf"
            make_pdf(pdf, ["one " * 40, "two " * 40, "three " * 40])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            cfg = FastDocV2Config(workers=1, batch_pages=1)
            engine = FastDocV2(store, cfg)
            first = engine.ingest(pdf)
            version = _pymupdf_version()
            opt = store.options_sha(None)
            with store.conn:
                store.conn.execute("UPDATE documents SET complete=0 WHERE document_sha=?", (first.document_sha256,))
                store.conn.execute(
                    "DELETE FROM page_map WHERE document_sha=? AND page_number=2 AND extractor=? AND extractor_version=? AND options_sha=?",
                    (first.document_sha256, "pymupdf-fastdoc-v2", version, opt),
                )
                if store.fts_enabled:
                    store.conn.execute("DELETE FROM page_fts WHERE document_sha=? AND page_number=2", (first.document_sha256,))
            resumed = engine.ingest(pdf)
            self.assertEqual(1, resumed.processed_pages)
            self.assertEqual(2, resumed.page_map_hits)
            store.close()

    def test_payload_reuse_across_distinct_documents(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.pdf"
            b = Path(td) / "b.pdf"
            make_pdf(a, ["same payload " * 20])
            doc = pymupdf.open(a)
            doc.set_metadata({"title": "different wrapper"})
            doc.save(b)
            doc.close()
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            engine = FastDocV2(store, FastDocV2Config(workers=1, batch_pages=1))
            ra = engine.ingest(a)
            rb = engine.ingest(b)
            self.assertNotEqual(ra.document_sha256, rb.document_sha256)
            self.assertGreaterEqual(rb.payload_reuse_hits, 1)
            store.close()

    def test_sparse_page_is_escalation_not_global_ocr(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "sparse.pdf"
            make_pdf(pdf, ["native text " * 30, "", "another native page " * 20])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            receipt = FastDocV2(store, FastDocV2Config(workers=1, batch_pages=1)).ingest(pdf)
            self.assertEqual((2,), receipt.escalation_pages)
            self.assertEqual(3, receipt.processed_pages)
            store.close()

    def test_completion_order_iterator_covers_all_pages(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "parallel.pdf"
            make_pdf(pdf, [f"page {i} " * 50 for i in range(1, 25)])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            cfg = FastDocV2Config(workers=2, batch_pages=4, max_inflight_batches=2).resolved(24)
            engine = FastDocV2(store, cfg)
            batches = list(engine.iter_native_batches(pdf, tuple(range(1, 25)), resolved=cfg))
            pages = sorted(p.page_number for batch in batches for p in batch.pages)
            self.assertEqual(list(range(1, 25)), pages)
            self.assertLessEqual(max(len(batch.page_numbers) for batch in batches), 4)
            store.close()

    def test_context_budget_never_exceeded(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "budget.pdf"
            make_pdf(pdf, ["keyword " * 500 for _ in range(5)])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            cfg = FastDocV2Config(workers=1, batch_pages=2, context_max_chars=1200, context_hit_limit=5)
            receipt = FastDocV2(store, cfg).ingest(pdf)
            pack = ContextPackBuilder(store, cfg).build(
                document_sha256=receipt.document_sha256,
                extractor_version=_pymupdf_version(),
                query="keyword",
            )
            self.assertLessEqual(pack.total_chars, 1200)
            self.assertTrue(pack.truncated)
            store.close()

    def test_enrichment_updates_search_and_context_without_mutating_payload(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "enrich.pdf"
            make_pdf(pdf, ["native footer only", "normal page " * 20])
            store = SQLiteContentStoreV2(Path(td) / "db.sqlite")
            cfg = FastDocV2Config(workers=1, batch_pages=1, context_neighbor_pages=0)
            receipt = FastDocV2(store, cfg).ingest(pdf)
            version = _pymupdf_version()
            page_before = store.get_page(receipt.document_sha256, 1, version)
            store.put_enrichment(receipt.document_sha256, 1, version, "LOCAL_OCR", "confidential scanned evidence keyword " * 10)
            page_after = store.get_page(receipt.document_sha256, 1, version)
            self.assertEqual(page_before.payload_sha256, page_after.payload_sha256)
            hits = store.search(receipt.document_sha256, "scanned evidence keyword")
            self.assertTrue(hits)
            pack = ContextPackBuilder(store, cfg).build(
                document_sha256=receipt.document_sha256, extractor_version=version, query="scanned evidence keyword"
            )
            self.assertTrue(pack.pages)
            self.assertIn("LOCAL_OCR", pack.pages[0].reason)
            store.close()


if __name__ == "__main__":
    unittest.main()
