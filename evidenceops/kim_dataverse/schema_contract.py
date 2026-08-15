from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


class SchemaContractError(ValueError):
    """Raised when a KDV write or schema lookup violates the typed contract."""


@dataclass(frozen=True)
class FieldContract:
    column_index_1based: int
    name: str
    logical_type: str


@dataclass(frozen=True)
class TableBlockContract:
    block_id: str
    header_row_1based: int | None
    data_start_row_1based: int
    data_end_row_1based: int
    fields: tuple[FieldContract, ...]
    candidate_primary_key: str | None = None
    record_shape: str = "table"

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


@dataclass(frozen=True)
class SheetContract:
    sheet_name: str
    xlsx_export_name: str
    role: str
    formula_count: int
    table_blocks: tuple[TableBlockContract, ...]

    def block(self, block_id: str | None = None) -> TableBlockContract:
        if block_id is None:
            if len(self.table_blocks) != 1:
                raise SchemaContractError(
                    f"BLOCK_ID_REQUIRED:{self.sheet_name}:blocks={len(self.table_blocks)}"
                )
            return self.table_blocks[0]
        for block in self.table_blocks:
            if block.block_id == block_id:
                return block
        raise SchemaContractError(f"UNKNOWN_BLOCK:{self.sheet_name}:{block_id}")


@dataclass(frozen=True)
class KDVSchemaRegistry:
    schema_version: str
    sheets: Mapping[str, SheetContract]
    truth_boundary: str

    @classmethod
    def load(cls, path: str | Path) -> "KDVSchemaRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        sheets: dict[str, SheetContract] = {}
        for raw_sheet in data.get("sheets", []):
            blocks: list[TableBlockContract] = []
            for raw_block in raw_sheet.get("table_blocks", []):
                fields = tuple(
                    FieldContract(
                        column_index_1based=int(field.get("column_index_1based", index + 1)),
                        name=str(field["name"]),
                        logical_type=str(field["logical_type"]),
                    )
                    for index, field in enumerate(raw_block.get("fields", []))
                )
                blocks.append(
                    TableBlockContract(
                        block_id=str(raw_block["block_id"]),
                        header_row_1based=raw_block.get("header_row_1based"),
                        data_start_row_1based=int(raw_block["data_start_row_1based"]),
                        data_end_row_1based=int(raw_block["data_end_row_1based"]),
                        fields=fields,
                        candidate_primary_key=raw_block.get("candidate_primary_key"),
                        record_shape=str(raw_block.get("record_shape", "table")),
                    )
                )
            sheet = SheetContract(
                sheet_name=str(raw_sheet["sheet_name"]),
                xlsx_export_name=str(raw_sheet.get("xlsx_export_name", raw_sheet["sheet_name"])),
                role=str(raw_sheet.get("role", "control_or_reference")),
                formula_count=int(raw_sheet.get("formula_count", 0)),
                table_blocks=tuple(blocks),
            )
            sheets[sheet.sheet_name] = sheet
        return cls(
            schema_version=str(data["schema_version"]),
            sheets=sheets,
            truth_boundary=str(data.get("truth_boundary", "")),
        )

    def sheet(self, name: str) -> SheetContract:
        try:
            return self.sheets[name]
        except KeyError as exc:
            raise SchemaContractError(f"UNKNOWN_SHEET:{name}") from exc

    def normalise_record(
        self,
        sheet_name: str,
        values: Mapping[str, Any],
        *,
        block_id: str | None = None,
        require_full_schema: bool = False,
    ) -> dict[str, Any]:
        block = self.sheet(sheet_name).block(block_id)
        field_map = {field.name: field for field in block.fields}
        unknown = sorted(set(values).difference(field_map))
        if unknown:
            raise SchemaContractError("UNKNOWN_FIELDS:" + ",".join(unknown))
        if require_full_schema:
            missing = [name for name in block.field_names if name not in values]
            if missing:
                raise SchemaContractError("MISSING_FIELDS:" + ",".join(missing))
        return {
            field.name: _normalise_value(field, values[field.name])
            for field in block.fields
            if field.name in values
        }

    def validate_live_headers(
        self,
        sheet_name: str,
        live_headers: Iterable[str],
        *,
        block_id: str | None = None,
    ) -> tuple[str, ...]:
        block = self.sheet(sheet_name).block(block_id)
        expected = block.field_names
        observed = tuple(str(item) for item in live_headers)
        if observed != expected:
            raise SchemaContractError(
                f"LIVE_HEADER_DRIFT:{sheet_name}:expected={expected!r}:observed={observed!r}"
            )
        return observed


def _normalise_value(field: FieldContract, value: Any) -> Any:
    if value is None:
        return None
    typ = field.logical_type
    if typ == "string":
        if isinstance(value, (dict, list, tuple, set)):
            raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:string")
        return str(value)
    if typ == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            upper = value.strip().upper()
            if upper == "TRUE":
                return True
            if upper == "FALSE":
                return False
        raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:boolean")
    if typ == "number":
        if isinstance(value, bool):
            raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:number")
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if re.fullmatch(r"[-+]?\d+", text):
                return int(text)
            if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", text):
                return float(text)
        raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:number")
    if typ == "timestamp_string":
        text = str(value).strip()
        candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:timestamp") from exc
        if parsed.tzinfo is None:
            raise SchemaContractError(f"TIMESTAMP_TIMEZONE_REQUIRED:{field.name}")
        return text
    if typ == "date_string":
        text = str(value).strip()
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise SchemaContractError(f"TYPE_MISMATCH:{field.name}:date") from exc
        return text
    raise SchemaContractError(f"UNSUPPORTED_LOGICAL_TYPE:{field.name}:{typ}")
