from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Iterable


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

KNOWN_GOOGLE_TO_XLSX_NAMES = {
    "FEDERATION_ADVERSARIAL_VALIDATION": "FEDERATION_ADVERSARIAL_VALIDATI",
    "CHATBRIDGE_CHECKPOINT_GENERATIONS": "CHATBRIDGE_CHECKPOINT_GENERATIO",
}


class XlsxSemanticError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticCell:
    reference: str
    value: Any
    ooxml_type: str
    style_id: str | None
    formula: str | None


@dataclass(frozen=True)
class SemanticSheet:
    export_name: str
    cells: dict[str, SemanticCell]


class XlsxSemanticWorkbook:
    """Minimal OOXML decoder for audit-safe spreadsheet interpretation."""

    def __init__(self, sheets: dict[str, SemanticSheet], shared_strings: tuple[str, ...]):
        self.sheets = sheets
        self.shared_strings = shared_strings

    @classmethod
    def load(cls, path: str | Path) -> "XlsxSemanticWorkbook":
        with zipfile.ZipFile(Path(path)) as archive:
            shared = cls._shared_strings(archive)
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
            sheets: dict[str, SemanticSheet] = {}
            sheets_node = workbook.find(f"{{{MAIN}}}sheets")
            if sheets_node is None:
                raise XlsxSemanticError("WORKBOOK_SHEETS_MISSING")
            for item in sheets_node:
                name = item.attrib["name"]
                target = rel_map[item.attrib[RID]]
                if not target.startswith("xl/"):
                    target = "xl/" + target
                root = ET.fromstring(archive.read(target))
                cells: dict[str, SemanticCell] = {}
                for cell in root.findall(f".//{{{MAIN}}}c"):
                    ref = cell.attrib["r"]
                    ooxml_type = cell.attrib.get("t", "n")
                    value = cls._decode_cell(cell, shared)
                    formula_node = cell.find(f"{{{MAIN}}}f")
                    cells[ref] = SemanticCell(
                        reference=ref,
                        value=value,
                        ooxml_type=ooxml_type,
                        style_id=cell.attrib.get("s"),
                        formula=formula_node.text if formula_node is not None else None,
                    )
                sheets[name] = SemanticSheet(export_name=name, cells=cells)
            return cls(sheets=sheets, shared_strings=tuple(shared))

    @staticmethod
    def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        return [
            "".join(node.text or "" for node in item.findall(f".//{{{MAIN}}}t"))
            for item in root.findall(f"{{{MAIN}}}si")
        ]

    @staticmethod
    def _decode_cell(cell: ET.Element, shared: list[str]) -> Any:
        typ = cell.attrib.get("t", "n")
        value_node = cell.find(f"{{{MAIN}}}v")
        if typ == "inlineStr":
            inline = cell.find(f"{{{MAIN}}}is")
            if inline is None:
                return ""
            return "".join(node.text or "" for node in inline.findall(f".//{{{MAIN}}}t"))
        if value_node is None:
            return None
        raw = value_node.text or ""
        if typ == "s":
            try:
                index = int(raw)
            except ValueError as exc:
                raise XlsxSemanticError(f"INVALID_SHARED_STRING_INDEX:{raw}") from exc
            if index < 0 or index >= len(shared):
                raise XlsxSemanticError(f"SHARED_STRING_INDEX_OUT_OF_RANGE:{index}")
            return shared[index]
        if typ == "b":
            if raw not in {"0", "1"}:
                raise XlsxSemanticError(f"INVALID_BOOLEAN:{raw}")
            return raw == "1"
        if typ in {"str", "e"}:
            return raw
        try:
            number = float(raw)
        except ValueError:
            return raw
        return int(number) if number.is_integer() else number

    def cell(self, sheet: str, reference: str) -> SemanticCell:
        try:
            return self.sheets[sheet].cells[reference]
        except KeyError as exc:
            raise XlsxSemanticError(f"CELL_NOT_FOUND:{sheet}!{reference}") from exc

    def formula_count(self) -> int:
        return sum(
            1
            for sheet in self.sheets.values()
            for cell in sheet.cells.values()
            if cell.formula is not None
        )

    def assert_sheet_identity_compatible(self, live_sheet_names: Iterable[str]) -> dict[str, str]:
        live_names = tuple(str(name) for name in live_sheet_names)
        mapping: dict[str, str] = {}
        claimed: dict[str, str] = {}
        for live in live_names:
            export = KNOWN_GOOGLE_TO_XLSX_NAMES.get(live, live[:31])
            if export in claimed and claimed[export] != live:
                raise XlsxSemanticError(
                    f"XLSX_SHEET_NAME_COLLISION:{claimed[export]}:{live}:{export}"
                )
            claimed[export] = live
            mapping[live] = export
        missing = sorted(set(mapping.values()).difference(self.sheets))
        if missing:
            raise XlsxSemanticError("XLSX_SHEETS_MISSING:" + ",".join(missing))
        return mapping
