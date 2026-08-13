from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
import unittest
import warnings
import zipfile

from evidenceops.capital_intelligence_os.ingestion import (
    DOCX_TYPE,
    XLSX_TYPE,
    IngestionError,
    MAX_OOXML_ARCHIVE_ENTRIES,
    MAX_OOXML_ENTRY_UNCOMPRESSED,
    MAX_OOXML_COMPRESSION_RATIO,
    MAX_XLSX_WORKSHEETS,
    _validate_ooxml_archive,
    parse_document,
)


DOC_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def make_zip(entries: list[tuple[str, bytes]], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return stream.getvalue()


def docx_xml(text: str) -> bytes:
    return (
        f'<w:document xmlns:w="{DOC_NS}"><w:body><w:p><w:r><w:t>{text}</w:t>'
        f'</w:r></w:p></w:body></w:document>'
    ).encode()


def sheet_xml(value: str = "100") -> bytes:
    return (
        f'<worksheet xmlns="{SHEET_NS}"><sheetData><row r="1">'
        f'<c r="A1"><v>{value}</v></c></row></sheetData></worksheet>'
    ).encode()


class NormalCompatibilityTests(unittest.TestCase):
    def test_normal_docx_still_parses_with_bounded_identity(self):
        parsed = parse_document(make_zip([("word/document.xml", docx_xml("Material Contract"))]), DOCX_TYPE)
        self.assertEqual(parsed.text, "Material Contract")
        self.assertEqual(parsed.parser_id, "DOCX_STDLIB_V2_BOUNDED")
        self.assertGreaterEqual(parsed.metadata["archive_entries"], 1)
        self.assertLessEqual(parsed.metadata["max_compression_ratio"], MAX_OOXML_COMPRESSION_RATIO)

    def test_normal_xlsx_still_parses_with_bounded_identity(self):
        parsed = parse_document(make_zip([("xl/worksheets/sheet1.xml", sheet_xml("100"))]), XLSX_TYPE)
        self.assertIn("100", parsed.text)
        self.assertEqual(parsed.parser_id, "XLSX_STDLIB_V2_BOUNDED")
        self.assertEqual(parsed.metadata["worksheets"], 1)
        self.assertGreaterEqual(parsed.metadata["archive_entries"], 1)


class ArchiveBoundaryTests(unittest.TestCase):
    def test_too_many_archive_entries_fail_closed(self):
        entries = [(f"custom/item{i}.xml", b"<x/>") for i in range(MAX_OOXML_ARCHIVE_ENTRIES + 1)]
        entries.append(("word/document.xml", docx_xml("x")))
        with self.assertRaisesRegex(IngestionError, "OOXML_ARCHIVE_TOO_MANY_ENTRIES"):
            parse_document(make_zip(entries), DOCX_TYPE)

    def test_unsafe_archive_path_fails_closed(self):
        entries = [("word/document.xml", docx_xml("x")), ("../escape.xml", b"<x/>")]
        with self.assertRaisesRegex(IngestionError, "OOXML_UNSAFE_ENTRY_NAME"):
            parse_document(make_zip(entries), DOCX_TYPE)

    def test_duplicate_entry_name_fails_closed(self):
        stream = BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", docx_xml("one"))
                archive.writestr("word/document.xml", docx_xml("two"))
        with self.assertRaisesRegex(IngestionError, "OOXML_DUPLICATE_ENTRY_NAME"):
            parse_document(stream.getvalue(), DOCX_TYPE)

    def test_high_compression_ratio_fails_closed_deterministically(self):
        info = SimpleNamespace(
            filename="word/document.xml",
            flag_bits=0,
            file_size=2_000_000,
            compress_size=1_000,
        )
        fake = SimpleNamespace(infolist=lambda: [info])
        self.assertGreater(info.file_size / info.compress_size, MAX_OOXML_COMPRESSION_RATIO)
        with self.assertRaisesRegex(IngestionError, "OOXML_SUSPICIOUS_COMPRESSION_RATIO"):
            _validate_ooxml_archive(fake)

    def test_entry_uncompressed_limit_fails_closed(self):
        payload = b"A" * (MAX_OOXML_ENTRY_UNCOMPRESSED + 1)
        with self.assertRaisesRegex(IngestionError, "OOXML_ENTRY_TOO_LARGE"):
            parse_document(make_zip([("word/document.xml", payload)]), DOCX_TYPE)

    def test_total_uncompressed_limit_fails_without_allocating_payload(self):
        infos = [
            SimpleNamespace(filename=f"x/{i}.xml", flag_bits=0, file_size=7_000_000, compress_size=7_000_000)
            for i in range(4)
        ]
        fake = SimpleNamespace(infolist=lambda: infos)
        with self.assertRaisesRegex(IngestionError, "OOXML_ARCHIVE_UNCOMPRESSED_LIMIT"):
            _validate_ooxml_archive(fake)

    def test_encrypted_entry_fails_without_decryption_attempt(self):
        info = SimpleNamespace(filename="word/document.xml", flag_bits=1, file_size=100, compress_size=80)
        fake = SimpleNamespace(infolist=lambda: [info])
        with self.assertRaisesRegex(IngestionError, "OOXML_ENCRYPTED_ENTRY_UNSUPPORTED"):
            _validate_ooxml_archive(fake)


class ParserAbuseTests(unittest.TestCase):
    def test_dtd_or_entity_payload_fails_closed(self):
        xml = (
            f'<!DOCTYPE w:document [<!ENTITY x "boom">]>'
            f'<w:document xmlns:w="{DOC_NS}"><w:body><w:p><w:r><w:t>&x;</w:t>'
            f'</w:r></w:p></w:body></w:document>'
        ).encode()
        with self.assertRaisesRegex(IngestionError, "OOXML_DTD_ENTITY_FORBIDDEN"):
            parse_document(make_zip([("word/document.xml", xml)]), DOCX_TYPE)

    def test_excessive_worksheet_count_fails_closed(self):
        entries = [
            (f"xl/worksheets/sheet{i}.xml", sheet_xml(str(i)))
            for i in range(1, MAX_XLSX_WORKSHEETS + 2)
        ]
        with self.assertRaisesRegex(IngestionError, "XLSX_WORKSHEET_LIMIT"):
            parse_document(make_zip(entries), XLSX_TYPE)

    def test_malformed_archive_fails_closed(self):
        with self.assertRaisesRegex(IngestionError, "INVALID_DOCX_DOCUMENT"):
            parse_document(b"not-a-zip", DOCX_TYPE)


if __name__ == "__main__":
    unittest.main()
