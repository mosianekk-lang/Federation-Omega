import shutil
import tempfile
from pathlib import Path
import unittest

import pymupdf

from federation.adobe_omega_pdf_ops_v1 import (
    annotate_pdf,
    combine_pdfs,
    extract_pages,
    ocr_available,
    ocr_pdf,
    optimize_pdf,
    pdf_properties,
    redact_pdf,
    rotate_pdf,
    split_pdf,
)


def make_pdf(path: Path, pages: list[str]) -> None:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 96), text, fontsize=16)
    doc.set_metadata({"title": "Adobe Omega PDF Fixture", "author": "Federation"})
    doc.save(path)
    doc.close()


def read_texts(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text("text") for page in doc]


class AdobeOmegaPdfOpsTests(unittest.TestCase):
    def test_properties_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.pdf"
            make_pdf(path, ["Page One", "Page Two"])
            props = pdf_properties(path)
            self.assertEqual(props.page_count, 2)
            self.assertFalse(props.encrypted)
            self.assertFalse(props.needs_password)
            self.assertGreater(props.file_size_bytes, 0)
            self.assertGreater(props.text_char_count, 0)
            self.assertEqual(len(props.rotations), 2)
            self.assertEqual(len(props.extracted_text_sha256), 64)
            self.assertIn(("title", "Adobe Omega PDF Fixture"), props.metadata)

    def test_combine_real_pdfs_and_verify_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.pdf"
            b = root / "b.pdf"
            out = root / "combined.pdf"
            make_pdf(a, ["A1", "A2"])
            make_pdf(b, ["B1"])
            receipt = combine_pdfs([a, b], out)
            self.assertTrue(receipt.semantic_readback_verified)
            self.assertEqual(receipt.output_page_count, 3)
            self.assertEqual([t.strip() for t in read_texts(out)], ["A1", "A2", "B1"])

    def test_extract_reorder_and_delete_by_omission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            out = root / "extract.pdf"
            make_pdf(source, ["P1", "P2", "P3"])
            receipt = extract_pages(source, out, [3, 1])
            self.assertTrue(receipt.semantic_readback_verified)
            self.assertEqual(receipt.output_page_count, 2)
            self.assertEqual([t.strip() for t in read_texts(out)], ["P3", "P1"])

    def test_split_pdf_one_page_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            make_pdf(source, ["P1", "P2", "P3"])
            receipts = split_pdf(source, root / "split")
            self.assertEqual(len(receipts), 3)
            self.assertTrue(all(r.semantic_readback_verified for r in receipts))
            for index in range(1, 4):
                self.assertEqual(read_texts(root / "split" / f"split-{index:04d}.pdf")[0].strip(), f"P{index}")

    def test_rotate_preserves_text_and_reads_back_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            out = root / "rotated.pdf"
            make_pdf(source, ["ROTATE ME", "KEEP ME"])
            receipt = rotate_pdf(source, out, {1: 90, 2: 180})
            self.assertTrue(receipt.semantic_readback_verified)
            with pymupdf.open(out) as doc:
                self.assertEqual(doc[0].rotation, 90)
                self.assertEqual(doc[1].rotation, 180)
                self.assertIn("ROTATE ME", doc[0].get_text())

    def test_optimize_compress_preserves_page_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            out = root / "optimized.pdf"
            make_pdf(source, ["Compression integrity " * 40, "Second page " * 40])
            before = read_texts(source)
            receipt = optimize_pdf(source, out)
            self.assertTrue(receipt.semantic_readback_verified)
            self.assertEqual(read_texts(out), before)
            details = dict(receipt.details)
            self.assertIn("source_size_bytes", details)
            self.assertIn("output_size_bytes", details)

    def test_redact_removes_target_but_preserves_other_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            out = root / "redacted.pdf"
            make_pdf(source, ["PUBLIC TEXT SECRET-ALPHA-991", "SECOND PUBLIC PAGE"])
            receipt = redact_pdf(source, out, text_targets=["SECRET-ALPHA-991"])
            self.assertTrue(receipt.semantic_readback_verified)
            text = "\n".join(read_texts(out))
            self.assertNotIn("SECRET-ALPHA-991", text)
            self.assertIn("PUBLIC TEXT", text)
            self.assertIn("SECOND PUBLIC PAGE", text)

    def test_highlight_and_note_annotations_are_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            out = root / "annotated.pdf"
            make_pdf(source, ["Highlight this phrase", "Second page"])
            receipt = annotate_pdf(
                source,
                out,
                highlights=[(1, "Highlight this phrase")],
                notes=[(2, 120, 140, "Review this page")],
            )
            self.assertTrue(receipt.semantic_readback_verified)
            props = pdf_properties(out)
            self.assertEqual(props.annotation_count, 2)

    def test_fail_closed_on_bad_page_and_same_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            make_pdf(source, ["P1"])
            with self.assertRaises(ValueError):
                extract_pages(source, root / "bad.pdf", [2])
            with self.assertRaises(ValueError):
                optimize_pdf(source, source)
            with self.assertRaises(ValueError):
                rotate_pdf(source, root / "badrot.pdf", {1: 45})

    def test_ocr_dependency_is_explicit(self):
        self.assertEqual(ocr_available(), shutil.which("tesseract") is not None)

    @unittest.skipUnless(shutil.which("tesseract"), "local Tesseract is required for OCR qualification")
    def test_ocr_scanned_pdf_becomes_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scan.pdf"
            out = root / "ocr.pdf"

            original = pymupdf.open()
            page = original.new_page()
            page.insert_text((72, 150), "OCR TARGET 456", fontsize=24)
            pix = page.get_pixmap(dpi=180, alpha=False)
            original.close()

            scan = pymupdf.open()
            scan_page = scan.new_page(width=595, height=842)
            scan_page.insert_image(scan_page.rect, pixmap=pix)
            scan.save(source)
            scan.close()

            with pymupdf.open(source) as doc:
                self.assertEqual(doc[0].get_text("text").strip(), "")

            receipt = ocr_pdf(source, out, dpi=180)
            self.assertTrue(receipt.semantic_readback_verified)
            self.assertIn("OCR TARGET 456", read_texts(out)[0])


if __name__ == "__main__":
    unittest.main()
