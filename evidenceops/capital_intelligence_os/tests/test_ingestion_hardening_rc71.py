from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import zipfile

from evidenceops.capital_intelligence_os import ingestion


DOC_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def make_zip(
    entries: list[tuple[str, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return stream.getvalue()


def docx_xml(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{value}</w:t></w:r></w:p>" for value in paragraphs)
    return f'<w:document xmlns:w="{DOC_NS}"><w:body>{body}</w:body></w:document>'.encode()


def sheet_xml(values: list[str | None]) -> bytes:
    cells = "".join(
        f'<c r="A{index}"><v>{value}</v></c>' if value is not None else f'<c r="A{index}"/>'
        for index, value in enumerate(values, start=1)
    )
    return (
        f'<worksheet xmlns="{SHEET_NS}"><sheetData><row r="1">{cells}</row></sheetData></worksheet>'
    ).encode()


class _FakeArchive:
    def __init__(self, entries: dict[str, tuple[zipfile.ZipInfo, bytes]]) -> None:
        self.entries = entries

    def getinfo(self, name: str) -> zipfile.ZipInfo:
        return self.entries[name][0]

    def open(self, info: zipfile.ZipInfo, _mode: str) -> BytesIO:
        return BytesIO(self.entries[info.filename][1])


def fake_entry(name: str, declared_size: int, payload: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name)
    info.file_size = declared_size
    info.compress_size = declared_size
    info.compress_type = zipfile.ZIP_STORED
    return info, payload


class NormalCompatibilityTests(unittest.TestCase):
    def test_normal_docx_remains_compatible_and_reports_security_boundary(self):
        raw = docx_xml(["Material Contract"])
        parsed = ingestion.parse_document(
            make_zip([("word/document.xml", raw)]),
            ingestion.DOCX_TYPE,
        )
        self.assertEqual(parsed.parser_id, "DOCX_STDLIB_V1")
        self.assertEqual(parsed.text, "Material Contract")
        self.assertEqual(parsed.metadata["paragraphs"], 1)
        self.assertEqual(parsed.metadata["security_profile"], ingestion.OOXML_SECURITY_PROFILE)
        self.assertIn("not an OS sandbox", parsed.metadata["isolation_boundary"])
        self.assertEqual(parsed.metadata["actual_uncompressed_bytes_read"], len(raw))

    def test_normal_xlsx_remains_compatible_and_counts_all_cells(self):
        shared = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<si><t>Revenue</t></si></sst>"
        ).encode()
        sheet = (
            f'<worksheet xmlns="{SHEET_NS}"><sheetData><row r="1">'
            '<c r="A1" t="s"><v>0</v></c><c r="A2"><v>100</v></c><c r="A3"/>'
            "</row></sheetData></worksheet>"
        ).encode()
        parsed = ingestion.parse_document(
            make_zip(
                [
                    ("xl/sharedStrings.xml", shared),
                    ("xl/worksheets/sheet1.xml", sheet),
                ]
            ),
            ingestion.XLSX_TYPE,
        )
        self.assertEqual(parsed.parser_id, "XLSX_STDLIB_V1")
        self.assertIn("Revenue", parsed.text)
        self.assertIn("100", parsed.text)
        self.assertEqual(parsed.metadata["shared_strings"], 1)
        self.assertEqual(parsed.metadata["total_cells"], 3)
        self.assertEqual(parsed.metadata["nonempty_cells"], 2)


class ArchiveAndStreamingBoundaryTests(unittest.TestCase):
    def test_unsafe_entry_name_is_rejected(self):
        archive = make_zip(
            [
                ("word/document.xml", docx_xml(["x"])),
                ("../escape.xml", b"<x/>"),
            ]
        )
        with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_UNSAFE_ENTRY_NAME"):
            ingestion.parse_document(archive, ingestion.DOCX_TYPE)

    def test_encrypted_entry_metadata_is_rejected(self):
        info = zipfile.ZipInfo("word/document.xml")
        info.flag_bits = 1
        info.file_size = 10
        info.compress_size = 10
        fake = SimpleNamespace(infolist=lambda: [info])
        with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_ENCRYPTED_ENTRY_UNSUPPORTED"):
            ingestion._validate_ooxml_archive(fake)

    def test_unsupported_compression_is_rejected(self):
        archive = make_zip(
            [("word/document.xml", docx_xml(["x"]))],
            compression=zipfile.ZIP_BZIP2,
        )
        with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_COMPRESSION_UNSUPPORTED"):
            ingestion.parse_document(archive, ingestion.DOCX_TYPE)

    def test_truncated_archive_is_rejected(self):
        archive = make_zip([("word/document.xml", docx_xml(["x"]))])
        with self.assertRaisesRegex(ingestion.IngestionError, "INVALID_DOCX_DOCUMENT"):
            ingestion.parse_document(archive[:-22], ingestion.DOCX_TYPE)

    def test_corrupt_required_entry_is_rejected(self):
        raw = docx_xml(["unique-payload"])
        archive = bytearray(make_zip([("word/document.xml", raw)], compression=zipfile.ZIP_STORED))
        offset = archive.find(raw)
        self.assertGreaterEqual(offset, 0)
        archive[offset + len(raw) - 2] ^= 0x01
        with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_ENTRY_READ_FAILED"):
            ingestion.parse_document(bytes(archive), ingestion.DOCX_TYPE)

    def test_actual_per_entry_budget_is_enforced_while_streaming(self):
        fake = _FakeArchive({"word/document.xml": fake_entry("word/document.xml", 1, b"abcdef")})
        with patch.object(ingestion, "MAX_OOXML_ENTRY_UNCOMPRESSED", 4):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_ACTUAL_ENTRY_UNCOMPRESSED_LIMIT"):
                ingestion._read_ooxml_entry(fake, "word/document.xml", ingestion._OOXMLReadBudget())

    def test_actual_total_budget_is_cumulative_across_entries(self):
        fake = _FakeArchive(
            {
                "xl/sharedStrings.xml": fake_entry("xl/sharedStrings.xml", 5, b"12345"),
                "xl/worksheets/sheet1.xml": fake_entry("xl/worksheets/sheet1.xml", 5, b"67890"),
            }
        )
        budget = ingestion._OOXMLReadBudget()
        with patch.object(ingestion, "MAX_OOXML_ENTRY_UNCOMPRESSED", 10), patch.object(
            ingestion, "MAX_OOXML_TOTAL_UNCOMPRESSED", 8
        ):
            ingestion._read_ooxml_entry(fake, "xl/sharedStrings.xml", budget)
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_ACTUAL_UNCOMPRESSED_LIMIT"):
                ingestion._read_ooxml_entry(fake, "xl/worksheets/sheet1.xml", budget)


class XMLDeclarationAndStructureBoundaryTests(unittest.TestCase):
    def test_late_doctype_and_entity_are_rejected_over_full_payload(self):
        raw = b" " * 1_000_001 + b'<!DOCTYPE r [<!ENTITY x "boom">]><r>&x;</r>'
        archive = make_zip([("word/document.xml", raw)], compression=zipfile.ZIP_STORED)
        with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_DTD_ENTITY_FORBIDDEN"):
            ingestion.parse_document(archive, ingestion.DOCX_TYPE)

    def test_utf16_utf32_and_nul_xml_are_rejected(self):
        payloads = (
            '<?xml version="1.0"?><r/>'.encode("utf-16"),
            '<?xml version="1.0"?><r/>'.encode("utf-32"),
            b"<r>nul\x00byte</r>",
        )
        for raw in payloads:
            with self.subTest(prefix=raw[:8]):
                archive = make_zip([("word/document.xml", raw)], compression=zipfile.ZIP_STORED)
                with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_ENCODING_UNSUPPORTED"):
                    ingestion.parse_document(archive, ingestion.DOCX_TYPE)

    def test_xml_element_budget_is_enforced(self):
        with patch.object(ingestion, "MAX_OOXML_XML_ELEMENTS", 2):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_ELEMENT_LIMIT"):
                ingestion._parse_ooxml_xml(
                    b"<r><a/><b/></r>", "INVALID", ingestion._OOXMLXMLBudget()
                )

    def test_xml_depth_budget_is_enforced(self):
        with patch.object(ingestion, "MAX_OOXML_XML_DEPTH", 2):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_DEPTH_LIMIT"):
                ingestion._parse_ooxml_xml(
                    b"<r><a><b/></a></r>", "INVALID", ingestion._OOXMLXMLBudget()
                )

    def test_xml_attribute_budgets_are_enforced(self):
        with patch.object(ingestion, "MAX_OOXML_XML_ATTRIBUTES_PER_ELEMENT", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_ELEMENT_ATTRIBUTE_LIMIT"):
                ingestion._parse_ooxml_xml(
                    b'<r a="1" b="2"/>', "INVALID", ingestion._OOXMLXMLBudget()
                )
        with patch.object(ingestion, "MAX_OOXML_XML_ATTRIBUTES_PER_ELEMENT", 10), patch.object(
            ingestion, "MAX_OOXML_XML_ATTRIBUTES", 1
        ):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_ATTRIBUTE_LIMIT"):
                ingestion._parse_ooxml_xml(
                    b'<r><a x="1"/><b y="2"/></r>', "INVALID", ingestion._OOXMLXMLBudget()
                )
        with patch.object(ingestion, "MAX_OOXML_XML_ATTRIBUTES_PER_ELEMENT", 10), patch.object(
            ingestion, "MAX_OOXML_XML_ATTRIBUTES", 10
        ), patch.object(ingestion, "MAX_OOXML_XML_ATTRIBUTE_CHARS", 3):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_ATTRIBUTE_TEXT_LIMIT"):
                ingestion._parse_ooxml_xml(
                    b'<r name="long"/>', "INVALID", ingestion._OOXMLXMLBudget()
                )

    def test_xml_text_budget_is_enforced(self):
        with patch.object(ingestion, "MAX_OOXML_XML_TEXT_CHARS", 3):
            with self.assertRaisesRegex(ingestion.IngestionError, "OOXML_XML_TEXT_LIMIT"):
                ingestion._parse_ooxml_xml(b"<r>four</r>", "INVALID", ingestion._OOXMLXMLBudget())


class DocumentSemanticBoundaryTests(unittest.TestCase):
    def test_docx_paragraph_limit_is_enforced(self):
        with patch.object(ingestion, "MAX_DOCX_PARAGRAPHS", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "DOCX_PARAGRAPH_LIMIT"):
                ingestion.parse_document(
                    make_zip([("word/document.xml", docx_xml(["one", "two"]))]),
                    ingestion.DOCX_TYPE,
                )

    def test_xlsx_worksheet_limit_is_enforced(self):
        archive = make_zip(
            [
                ("xl/worksheets/sheet1.xml", sheet_xml(["1"])),
                ("xl/worksheets/sheet2.xml", sheet_xml(["2"])),
            ]
        )
        with patch.object(ingestion, "MAX_XLSX_WORKSHEETS", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "XLSX_WORKSHEET_LIMIT"):
                ingestion.parse_document(archive, ingestion.XLSX_TYPE)

    def test_xlsx_shared_string_limit_is_enforced(self):
        shared = (
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<si><t>one</t></si><si><t>two</t></si></sst>"
        ).encode()
        archive = make_zip(
            [
                ("xl/sharedStrings.xml", shared),
                ("xl/worksheets/sheet1.xml", sheet_xml(["1"])),
            ]
        )
        with patch.object(ingestion, "MAX_XLSX_SHARED_STRINGS", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "XLSX_SHARED_STRING_LIMIT"):
                ingestion.parse_document(archive, ingestion.XLSX_TYPE)

    def test_xlsx_total_cell_limit_counts_empty_cells(self):
        archive = make_zip([("xl/worksheets/sheet1.xml", sheet_xml([None, "1"]))])
        with patch.object(ingestion, "MAX_XLSX_TOTAL_CELLS", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "XLSX_TOTAL_CELL_LIMIT"):
                ingestion.parse_document(archive, ingestion.XLSX_TYPE)

    def test_xlsx_nonempty_cell_limit_is_enforced(self):
        archive = make_zip([("xl/worksheets/sheet1.xml", sheet_xml(["1", "2"]))])
        with patch.object(ingestion, "MAX_XLSX_NONEMPTY_CELLS", 1):
            with self.assertRaisesRegex(ingestion.IngestionError, "XLSX_NONEMPTY_CELL_LIMIT"):
                ingestion.parse_document(archive, ingestion.XLSX_TYPE)


if __name__ == "__main__":
    unittest.main()
