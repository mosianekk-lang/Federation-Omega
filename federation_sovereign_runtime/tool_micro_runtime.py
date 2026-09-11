from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .core import stable_hash


@dataclass(frozen=True)
class MicroRuntimeReceipt:
    operation: str
    input_count: int
    output_count: int
    result_sha256: str
    deterministic: bool = True
    external_effect: bool = False


class DeterministicDataRuntime:
    """Pure data operations for mechanical work that should not consume agent reasoning.

    The runtime is intentionally narrow and effect-free. It operates on JSON-like
    rows and emits deterministic receipts. Provider- or domain-specific execution
    remains outside this module.
    """

    @staticmethod
    def _rows(rows: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in rows)

    @staticmethod
    def _receipt(operation: str, input_count: int, output: Any) -> MicroRuntimeReceipt:
        output_count = len(output) if isinstance(output, (list, tuple)) else 1
        return MicroRuntimeReceipt(
            operation=operation,
            input_count=input_count,
            output_count=output_count,
            result_sha256=stable_hash(output),
        )

    def filter_equal(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        field: str,
        value: Any,
    ) -> tuple[tuple[dict[str, Any], ...], MicroRuntimeReceipt]:
        material = self._rows(rows)
        result = tuple(row for row in material if row.get(field) == value)
        return result, self._receipt(f"FILTER_EQUAL:{field}", len(material), result)

    def project(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        fields: Sequence[str],
    ) -> tuple[tuple[dict[str, Any], ...], MicroRuntimeReceipt]:
        material = self._rows(rows)
        selected = tuple(dict.fromkeys(str(field) for field in fields if str(field)))
        if not selected:
            raise ValueError("PROJECT_FIELDS_REQUIRED")
        result = tuple({field: row.get(field) for field in selected} for row in material)
        return result, self._receipt("PROJECT:" + ",".join(selected), len(material), result)

    def sort_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        field: str,
        reverse: bool = False,
    ) -> tuple[tuple[dict[str, Any], ...], MicroRuntimeReceipt]:
        material = self._rows(rows)

        def key(row: Mapping[str, Any]) -> tuple[bool, str]:
            value = row.get(field)
            return value is None, stable_hash(value)

        result = tuple(sorted(material, key=key, reverse=bool(reverse)))
        return result, self._receipt(f"SORT:{field}:{'DESC' if reverse else 'ASC'}", len(material), result)

    def deduplicate(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        key_fields: Sequence[str],
    ) -> tuple[tuple[dict[str, Any], ...], MicroRuntimeReceipt]:
        material = self._rows(rows)
        keys = tuple(dict.fromkeys(str(field) for field in key_fields if str(field)))
        if not keys:
            raise ValueError("DEDUP_KEY_FIELDS_REQUIRED")
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for row in material:
            identity = stable_hash(tuple((field, row.get(field)) for field in keys))
            if identity in seen:
                continue
            seen.add(identity)
            result.append(row)
        output = tuple(result)
        return output, self._receipt("DEDUP:" + ",".join(keys), len(material), output)

    def aggregate_count(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        group_by: str,
    ) -> tuple[tuple[dict[str, Any], ...], MicroRuntimeReceipt]:
        material = self._rows(rows)
        counts: dict[str, tuple[Any, int]] = {}
        for row in material:
            raw = row.get(group_by)
            identity = stable_hash(raw)
            prior = counts.get(identity)
            counts[identity] = (raw, 1 if prior is None else prior[1] + 1)
        result = tuple(
            {group_by: raw, "count": count}
            for _, (raw, count) in sorted(counts.items(), key=lambda item: item[0])
        )
        return result, self._receipt(f"AGGREGATE_COUNT:{group_by}", len(material), result)


__all__ = ["DeterministicDataRuntime", "MicroRuntimeReceipt"]
