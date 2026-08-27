from __future__ import annotations

from dataclasses import asdict, dataclass
from email import policy as email_policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO, StringIO
import csv
import json
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

from .diligence import DiligenceEngine
from .models import InformationClass
from .tenancy import TenantContext
from .vault import DocumentVault


MAX_INGEST_BYTES = 5_000_000
MAX_EXTRACTED_CHARS = 2_000_000
MAX_OOXML_ARCHIVE_ENTRIES = 512
MAX_OOXML_TOTAL_UNCOMPRESSED = 25_000_000
MAX_OOXML_ENTRY_UNCOMPRESSED = 8_000_000
MAX_OOXML_COMPRESSION_RATIO = 1_000.0
MAX_OOXML_XML_ELEMENTS = 500_000
MAX_OOXML_XML_DEPTH = 128
MAX_OOXML_XML_ATTRIBUTES = 500_000
MAX_OOXML_XML_ATTRIBUTES_PER_ELEMENT = 128
MAX_OOXML_XML_ATTRIBUTE_CHARS = 1_000_000
MAX_OOXML_XML_TEXT_CHARS = 4_000_000
MAX_DOCX_PARAGRAPHS = 100_000
MAX_XLSX_WORKSHEETS = 64
MAX_XLSX_SHARED_STRINGS = 250_000
MAX_XLSX_TOTAL_CELLS = 500_000
MAX_XLSX_NONEMPTY_CELLS = 250_000
OOXML_READ_CHUNK_BYTES = 64 * 1024
OOXML_SUPPORTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
OOXML_SECURITY_PROFILE = "OOXML_STDLIB_STREAM_BOUNDED_RC71"
OOXML_ISOLATION_BOUNDARY = (
    "In-process stdlib parsing is resource-bounded but is not an OS sandbox; "
    "production document ingestion still requires a separately resource-isolated worker."
)
TEXT_TYPES = {"text/plain", "text/csv", "application/csv"}
JSON_TYPES = {"application/json", "text/json"}
EMAIL_TYPES = {"message/rfc822", "application/eml"}
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_TYPE = "application/pdf"


class IngestionError(ValueError):
    pass


@dataclass
class _OOXMLReadBudget:
    actual_uncompressed_bytes: int = 0

    def account(self, size: int) -> None:
        self.actual_uncompressed_bytes += size
        if self.actual_uncompressed_bytes > MAX_OOXML_TOTAL_UNCOMPRESSED:
            raise IngestionError("OOXML_ACTUAL_UNCOMPRESSED_LIMIT")


@dataclass
class _OOXMLXMLBudget:
    elements: int = 0
    attributes: int = 0
    attribute_chars: int = 0
    text_chars: int = 0
    max_depth: int = 0

    def metadata(self) -> dict[str, int]:
        return {
            "xml_elements": self.elements,
            "xml_attributes": self.attributes,
            "xml_attribute_chars": self.attribute_chars,
            "xml_text_chars": self.text_chars,
            "xml_max_depth": self.max_depth,
        }


@dataclass(frozen=True)
class ParsedDocument:
    parser_id: str
    text: str
    metadata: dict[str, object]
    warnings: tuple[str, ...] = ()

    @property
    def character_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class DocumentIngestRequest:
    logical_key: str
    filename: str
    document_type: str
    content_type: str
    content: bytes
    information_class: InformationClass
    source_id: str
    extracted_text: str = ""
    tags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.logical_key.strip() or not self.document_type.strip() or not self.source_id.strip():
            raise IngestionError("DOCUMENT_IDENTITY_REQUIRED")
        if not self.filename.strip() or "\x00" in self.filename:
            raise IngestionError("INVALID_FILENAME")
        if "/" in self.filename or "\\" in self.filename or self.filename in {".", ".."}:
            raise IngestionError("FILENAME_MUST_BE_BASENAME")
        if not self.content_type.strip():
            raise IngestionError("CONTENT_TYPE_REQUIRED")
        if not self.content:
            raise IngestionError("DOCUMENT_CONTENT_REQUIRED")
        if len(self.content) > MAX_INGEST_BYTES:
            raise IngestionError("DOCUMENT_TOO_LARGE_FOR_REFERENCE_INGESTION")
        if len(self.extracted_text) > MAX_EXTRACTED_CHARS:
            raise IngestionError("EXTRACTED_TEXT_TOO_LARGE")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def value(self) -> str:
        return "\n".join(self.parts)


def _base_content_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


def _decode_utf8(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("UTF8_DECODE_REQUIRED") from exc


def _limit_text(text: str) -> str:
    if len(text) > MAX_EXTRACTED_CHARS:
        raise IngestionError("PARSED_TEXT_TOO_LARGE")
    return text


def _parse_text(content: bytes, content_type: str) -> ParsedDocument:
    text = _decode_utf8(content)
    if content_type in {"text/csv", "application/csv"}:
        rows = list(csv.reader(StringIO(text)))
        normalized = "\n".join("\t".join(cell.strip() for cell in row) for row in rows)
        return ParsedDocument("CSV_STDLIB_V1", _limit_text(normalized), {"rows": len(rows)})
    return ParsedDocument("TEXT_UTF8_V1", _limit_text(text), {})


def _parse_json(content: bytes) -> ParsedDocument:
    try:
        payload = json.loads(_decode_utf8(content))
    except json.JSONDecodeError as exc:
        raise IngestionError("INVALID_JSON_DOCUMENT") from exc
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    return ParsedDocument("JSON_STDLIB_V1", _limit_text(text), {"root_type": type(payload).__name__})


def _plain_or_html_part(message) -> tuple[str, str]:
    plain: list[str] = []
    html: list[str] = []
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        kind = part.get_content_type()
        try:
            body = part.get_content()
        except Exception:
            continue
        if not isinstance(body, str):
            continue
        if kind == "text/plain":
            plain.append(body)
        elif kind == "text/html":
            html.append(body)
    if plain:
        return "\n".join(plain), "text/plain"
    if html:
        parser = _HTMLTextExtractor()
        parser.feed("\n".join(html))
        return parser.value(), "text/html"
    return "", "none"


def _parse_email(content: bytes) -> ParsedDocument:
    try:
        msg = BytesParser(policy=email_policy.default).parsebytes(content)
    except Exception as exc:
        raise IngestionError("INVALID_EMAIL_DOCUMENT") from exc
    body, body_type = _plain_or_html_part(msg)
    headers: dict[str, str] = {}
    for key in ("Subject", "From", "To", "Cc", "Date", "Message-ID"):
        value = msg.get(key)
        if value:
            headers[key.lower().replace("-", "_")] = str(value)
    attachments = [
        part.get_filename()
        for part in msg.walk()
        if part.get_content_disposition() == "attachment" and part.get_filename()
    ]
    prefix = "\n".join(f"{key}: {value}" for key, value in sorted(headers.items()))
    text = (prefix + "\n\n" + body).strip()
    return ParsedDocument(
        "EMAIL_STDLIB_V1",
        _limit_text(text),
        {"headers": headers, "body_type": body_type, "attachment_names": attachments},
    )


def _normalized_ooxml_name(info: zipfile.ZipInfo) -> str:
    name = unicodedata.normalize("NFC", info.filename)
    if not name or "\x00" in name or "\\" in name:
        raise IngestionError("OOXML_UNSAFE_ENTRY_NAME")
    if name.startswith("/") or re.match(r"^[A-Za-z]:/", name):
        raise IngestionError("OOXML_UNSAFE_ENTRY_NAME")
    logical = name[:-1] if info.is_dir() and name.endswith("/") else name
    parts = logical.split("/")
    if not logical or any(part in {"", ".", ".."} for part in parts):
        raise IngestionError("OOXML_UNSAFE_ENTRY_NAME")
    return name


def _validate_ooxml_archive(archive: zipfile.ZipFile) -> dict[str, object]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_OOXML_ARCHIVE_ENTRIES:
        raise IngestionError("OOXML_ARCHIVE_ENTRY_LIMIT")

    seen: set[str] = set()
    declared_total = 0
    max_ratio = 1.0
    for info in infos:
        normalized = _normalized_ooxml_name(info)
        collision_key = normalized.casefold()
        if collision_key in seen:
            raise IngestionError("OOXML_DUPLICATE_ENTRY_NAME")
        seen.add(collision_key)
        if info.flag_bits & 0x1:
            raise IngestionError("OOXML_ENCRYPTED_ENTRY_UNSUPPORTED")
        if info.compress_type not in OOXML_SUPPORTED_COMPRESSION:
            raise IngestionError("OOXML_COMPRESSION_UNSUPPORTED")
        if info.file_size < 0 or info.compress_size < 0:
            raise IngestionError("OOXML_INVALID_ENTRY_SIZE")
        if info.file_size > MAX_OOXML_ENTRY_UNCOMPRESSED:
            raise IngestionError("OOXML_ENTRY_UNCOMPRESSED_LIMIT")
        declared_total += info.file_size
        if declared_total > MAX_OOXML_TOTAL_UNCOMPRESSED:
            raise IngestionError("OOXML_DECLARED_UNCOMPRESSED_LIMIT")
        if info.file_size:
            ratio = info.file_size / max(info.compress_size, 1)
            max_ratio = max(max_ratio, ratio)
            if info.file_size >= 100_000 and ratio > MAX_OOXML_COMPRESSION_RATIO:
                raise IngestionError("OOXML_SUSPICIOUS_COMPRESSION_RATIO")

    return {
        "archive_entries": len(infos),
        "declared_uncompressed_bytes": declared_total,
        "max_compression_ratio": round(max_ratio, 3),
    }


def _read_ooxml_entry(
    archive: zipfile.ZipFile,
    name: str,
    budget: _OOXMLReadBudget,
) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise IngestionError("OOXML_REQUIRED_ENTRY_MISSING") from exc
    if info.is_dir():
        raise IngestionError("OOXML_REQUIRED_ENTRY_IS_DIRECTORY")
    if info.file_size > MAX_OOXML_ENTRY_UNCOMPRESSED:
        raise IngestionError("OOXML_ENTRY_UNCOMPRESSED_LIMIT")

    payload = bytearray()
    try:
        with archive.open(info, "r") as source:
            while True:
                chunk = source.read(OOXML_READ_CHUNK_BYTES)
                if not chunk:
                    break
                payload.extend(chunk)
                budget.account(len(chunk))
                if len(payload) > MAX_OOXML_ENTRY_UNCOMPRESSED:
                    raise IngestionError("OOXML_ACTUAL_ENTRY_UNCOMPRESSED_LIMIT")
    except IngestionError:
        raise
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, OSError, ValueError) as exc:
        raise IngestionError("OOXML_ENTRY_READ_FAILED") from exc

    if len(payload) != info.file_size:
        raise IngestionError("OOXML_ENTRY_SIZE_MISMATCH")
    return bytes(payload)


def _validate_ooxml_xml_encoding_and_declarations(raw: bytes) -> None:
    if b"\x00" in raw:
        raise IngestionError("OOXML_XML_ENCODING_UNSUPPORTED")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestionError("OOXML_XML_ENCODING_UNSUPPORTED") from exc

    declaration = re.match(r"\s*<\?xml\b(?P<body>.*?)\?>", decoded[:1024], re.IGNORECASE | re.DOTALL)
    if declaration:
        match = re.search(
            r"\bencoding\s*=\s*(['\"])(?P<encoding>[^'\"]+)\1",
            declaration.group("body"),
            re.IGNORECASE,
        )
        if match and match.group("encoding").strip().lower() not in {
            "utf-8",
            "utf8",
            "us-ascii",
            "ascii",
        }:
            raise IngestionError("OOXML_XML_ENCODING_UNSUPPORTED")

    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, re.IGNORECASE):
        raise IngestionError("OOXML_DTD_ENTITY_FORBIDDEN")


def _parse_ooxml_xml(
    raw: bytes,
    invalid_code: str,
    budget: _OOXMLXMLBudget,
) -> ET.Element:
    """Parse bounded OOXML XML in-process.

    The parser rejects non-UTF-8/ASCII input and declarations with DTD/entities,
    then enforces cumulative structure budgets while parsing in small chunks.
    These controls are intentionally not represented as process isolation; the
    production boundary remains a separately resource-isolated parser worker.
    """

    _validate_ooxml_xml_encoding_and_declarations(raw)
    parser = ET.XMLPullParser(events=("start", "end"))
    root: ET.Element | None = None
    depth = 0

    def consume_events() -> None:
        nonlocal root, depth
        for event, element in parser.read_events():
            if event == "start":
                if root is None:
                    root = element
                depth += 1
                budget.max_depth = max(budget.max_depth, depth)
                budget.elements += 1
                attribute_count = len(element.attrib)
                budget.attributes += attribute_count
                budget.attribute_chars += sum(
                    len(str(key)) + len(str(value)) for key, value in element.attrib.items()
                )
                if budget.elements > MAX_OOXML_XML_ELEMENTS:
                    raise IngestionError("OOXML_XML_ELEMENT_LIMIT")
                if depth > MAX_OOXML_XML_DEPTH:
                    raise IngestionError("OOXML_XML_DEPTH_LIMIT")
                if attribute_count > MAX_OOXML_XML_ATTRIBUTES_PER_ELEMENT:
                    raise IngestionError("OOXML_XML_ELEMENT_ATTRIBUTE_LIMIT")
                if budget.attributes > MAX_OOXML_XML_ATTRIBUTES:
                    raise IngestionError("OOXML_XML_ATTRIBUTE_LIMIT")
                if budget.attribute_chars > MAX_OOXML_XML_ATTRIBUTE_CHARS:
                    raise IngestionError("OOXML_XML_ATTRIBUTE_TEXT_LIMIT")
            else:
                budget.text_chars += len(element.text or "") + len(element.tail or "")
                if budget.text_chars > MAX_OOXML_XML_TEXT_CHARS:
                    raise IngestionError("OOXML_XML_TEXT_LIMIT")
                depth -= 1

    try:
        for offset in range(0, len(raw), OOXML_READ_CHUNK_BYTES):
            parser.feed(raw[offset : offset + OOXML_READ_CHUNK_BYTES])
            consume_events()
        parser.close()
        consume_events()
    except IngestionError:
        raise
    except (ET.ParseError, UnicodeError, ValueError) as exc:
        raise IngestionError(invalid_code) from exc

    if root is None or depth != 0:
        raise IngestionError(invalid_code)
    return root


def _parse_docx(content: bytes) -> ParsedDocument:
    read_budget = _OOXMLReadBudget()
    xml_budget = _OOXMLXMLBudget()
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except (zipfile.BadZipFile, EOFError, OSError, ValueError) as exc:
        raise IngestionError("INVALID_DOCX_DOCUMENT") from exc
    with archive:
        archive_meta = _validate_ooxml_archive(archive)
        try:
            raw = _read_ooxml_entry(archive, "word/document.xml", read_budget)
        except IngestionError as exc:
            if str(exc) == "OOXML_REQUIRED_ENTRY_MISSING":
                raise IngestionError("INVALID_DOCX_DOCUMENT") from exc
            raise
    root = _parse_ooxml_xml(raw, "INVALID_DOCX_XML", xml_budget)
    paragraphs: list[str] = []
    paragraph_count = 0
    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue
        paragraph_count += 1
        if paragraph_count > MAX_DOCX_PARAGRAPHS:
            raise IngestionError("DOCX_PARAGRAPH_LIMIT")
        value = "".join(
            node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
        ).strip()
        if value:
            paragraphs.append(value)
    return ParsedDocument(
        "DOCX_STDLIB_V1",
        _limit_text("\n".join(paragraphs)),
        {
            **archive_meta,
            **xml_budget.metadata(),
            "actual_uncompressed_bytes_read": read_budget.actual_uncompressed_bytes,
            "paragraphs": paragraph_count,
            "security_profile": OOXML_SECURITY_PROFILE,
            "isolation_boundary": OOXML_ISOLATION_BOUNDARY,
        },
    )


def _shared_strings(
    archive: zipfile.ZipFile,
    read_budget: _OOXMLReadBudget,
    xml_budget: _OOXMLXMLBudget,
) -> list[str]:
    try:
        archive.getinfo("xl/sharedStrings.xml")
    except KeyError:
        return []
    raw = _read_ooxml_entry(archive, "xl/sharedStrings.xml", read_budget)
    root = _parse_ooxml_xml(raw, "INVALID_XLSX_SHARED_STRINGS", xml_budget)
    values: list[str] = []
    for item in root.iter():
        if not item.tag.endswith("}si"):
            continue
        values.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))
        if len(values) > MAX_XLSX_SHARED_STRINGS:
            raise IngestionError("XLSX_SHARED_STRING_LIMIT")
    return values


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    inline = [node.text or "" for node in cell.iter() if node.tag.endswith("}t")]
    if cell_type == "inlineStr" and inline:
        return "".join(inline)
    value_node = next((node for node in cell if node.tag.endswith("}v")), None)
    value = value_node.text if value_node is not None and value_node.text is not None else ""
    if cell_type == "s" and value:
        try:
            return shared[int(value)]
        except (ValueError, IndexError) as exc:
            raise IngestionError("INVALID_XLSX_SHARED_STRING_INDEX") from exc
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"
    formula = next((node.text or "" for node in cell if node.tag.endswith("}f")), "")
    if formula:
        return f"={formula}" + (f" -> {value}" if value else "")
    return value


def _parse_xlsx(content: bytes) -> ParsedDocument:
    read_budget = _OOXMLReadBudget()
    xml_budget = _OOXMLXMLBudget()
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except (zipfile.BadZipFile, EOFError, OSError, ValueError) as exc:
        raise IngestionError("INVALID_XLSX_DOCUMENT") from exc
    with archive:
        archive_meta = _validate_ooxml_archive(archive)
        shared = _shared_strings(archive, read_budget, xml_budget)
        sheets = sorted(
            name for name in archive.namelist()
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        )
        if not sheets:
            raise IngestionError("XLSX_WORKSHEETS_REQUIRED")
        if len(sheets) > MAX_XLSX_WORKSHEETS:
            raise IngestionError("XLSX_WORKSHEET_LIMIT")
        lines: list[str] = []
        total_cell_count = 0
        nonempty_cell_count = 0
        for sheet_index, name in enumerate(sheets, start=1):
            raw = _read_ooxml_entry(archive, name, read_budget)
            root = _parse_ooxml_xml(raw, "INVALID_XLSX_WORKSHEET_XML", xml_budget)
            for cell in root.iter():
                if not cell.tag.endswith("}c"):
                    continue
                total_cell_count += 1
                if total_cell_count > MAX_XLSX_TOTAL_CELLS:
                    raise IngestionError("XLSX_TOTAL_CELL_LIMIT")
                ref = cell.attrib.get("r", f"CELL-{total_cell_count}")
                value = _cell_value(cell, shared)
                if value != "":
                    lines.append(f"Sheet{sheet_index}!{ref}\t{value}")
                    nonempty_cell_count += 1
                    if nonempty_cell_count > MAX_XLSX_NONEMPTY_CELLS:
                        raise IngestionError("XLSX_NONEMPTY_CELL_LIMIT")
        return ParsedDocument(
            "XLSX_STDLIB_V1",
            _limit_text("\n".join(lines)),
            {
                **archive_meta,
                **xml_budget.metadata(),
                "actual_uncompressed_bytes_read": read_budget.actual_uncompressed_bytes,
                "worksheets": len(sheets),
                "shared_strings": len(shared),
                "total_cells": total_cell_count,
                "nonempty_cells": nonempty_cell_count,
                "security_profile": OOXML_SECURITY_PROFILE,
                "isolation_boundary": OOXML_ISOLATION_BOUNDARY,
            },
        )


def parse_document(content: bytes, content_type: str, *, extracted_text: str = "") -> ParsedDocument:
    kind = _base_content_type(content_type)
    if kind in TEXT_TYPES:
        return _parse_text(content, kind)
    if kind in JSON_TYPES:
        return _parse_json(content)
    if kind in EMAIL_TYPES:
        return _parse_email(content)
    if kind == DOCX_TYPE:
        return _parse_docx(content)
    if kind == XLSX_TYPE:
        return _parse_xlsx(content)
    if kind == PDF_TYPE:
        if not extracted_text.strip():
            raise IngestionError("PDF_TEXT_EXTRACTION_REQUIRED")
        return ParsedDocument(
            "PDF_EXTERNAL_TEXT_V1",
            _limit_text(extracted_text),
            {"text_source": "caller_supplied_extraction"},
            ("PDF bytes were integrity-hashed; text extraction was supplied externally and is not independently verified by the stdlib parser.",),
        )
    if extracted_text.strip():
        return ParsedDocument(
            "EXTERNAL_TEXT_FALLBACK_V1",
            _limit_text(extracted_text),
            {"content_type": kind, "text_source": "caller_supplied_extraction"},
            ("Unknown content type accepted only because explicit extracted text was supplied.",),
        )
    raise IngestionError(f"UNSUPPORTED_CONTENT_TYPE:{kind}")


class DocumentIngestionService:
    def __init__(self, vault: DocumentVault) -> None:
        self.vault = vault
        self.diligence = DiligenceEngine()

    def ingest(self, ctx: TenantContext, request: DocumentIngestRequest) -> dict[str, object]:
        request.validate()
        parsed = parse_document(request.content, request.content_type, extracted_text=request.extracted_text)
        record, duplicate = self.vault.ingest(
            ctx,
            logical_key=request.logical_key,
            filename=request.filename,
            document_type=request.document_type,
            content_type=request.content_type,
            content=request.content,
            information_class=request.information_class,
            source_id=request.source_id,
            extracted_text=parsed.text,
            tags=request.tags,
        )
        return {
            "state": "SUCCESS",
            "duplicate": duplicate,
            "document": {**asdict(record), "information_class": record.information_class.value},
            "parser": {
                "parser_id": parsed.parser_id,
                "character_count": parsed.character_count,
                "metadata": parsed.metadata,
                "warnings": list(parsed.warnings),
            },
            "diligence": self.diligence_status(ctx),
            "external_effects": False,
        }

    def diligence_status(self, ctx: TenantContext) -> dict[str, object]:
        requirements = self.diligence.standard_profile()
        available = self.vault.document_types(ctx)
        gaps = self.diligence.missing(requirements, available)
        return {
            "available_document_types": sorted(available),
            "completeness": self.diligence.completeness(requirements, available),
            "missing": [asdict(gap) for gap in gaps],
            "requirements": len(requirements),
        }
