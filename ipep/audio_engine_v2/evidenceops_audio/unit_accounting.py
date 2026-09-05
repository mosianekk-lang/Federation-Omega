from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UnitAccountingError(ValueError):
    """Raised when per-unit provider receipts cannot prove complete accounting."""


@dataclasses.dataclass(frozen=True)
class UnitReceipt:
    unit_id: str
    source_chunk_sha256: str
    unit_start_seconds: float
    unit_end_seconds: float
    provider: str
    provider_exit_code: int
    raw_response_sha256: str
    segment_count: int
    state: str = "PROCESSED"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "UnitReceipt":
        return cls(
            unit_id=str(raw["unit_id"]),
            source_chunk_sha256=str(raw["source_chunk_sha256"]).lower(),
            unit_start_seconds=float(raw["unit_start_seconds"]),
            unit_end_seconds=float(raw["unit_end_seconds"]),
            provider=str(raw["provider"]),
            provider_exit_code=int(raw["provider_exit_code"]),
            raw_response_sha256=str(raw["raw_response_sha256"]).lower(),
            segment_count=int(raw["segment_count"]),
            state=str(raw.get("state", "PROCESSED")).upper(),
        )

    def validate(self) -> None:
        if not self.unit_id.strip():
            raise UnitAccountingError("unit_id is required")
        if not _SHA256_RE.fullmatch(self.source_chunk_sha256):
            raise UnitAccountingError(f"invalid source_chunk_sha256 for {self.unit_id}")
        if not _SHA256_RE.fullmatch(self.raw_response_sha256):
            raise UnitAccountingError(f"invalid raw_response_sha256 for {self.unit_id}")
        if self.unit_start_seconds < 0 or self.unit_end_seconds <= self.unit_start_seconds:
            raise UnitAccountingError(f"invalid unit time range for {self.unit_id}")
        if not self.provider.strip():
            raise UnitAccountingError(f"provider is required for {self.unit_id}")
        if self.segment_count < 0:
            raise UnitAccountingError(f"negative segment_count for {self.unit_id}")
        if self.state not in {"PROCESSED", "FAILED"}:
            raise UnitAccountingError(f"unsupported state for {self.unit_id}: {self.state}")
        if self.state == "PROCESSED" and self.provider_exit_code != 0:
            raise UnitAccountingError(
                f"processed unit has non-zero provider_exit_code for {self.unit_id}"
            )
        if self.state == "FAILED" and self.segment_count != 0:
            raise UnitAccountingError(f"failed unit emitted segments: {self.unit_id}")


def reconcile_unit_accounting(
    expected_unit_ids: Iterable[str],
    receipts: Iterable[UnitReceipt | dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed unless every expected unit has one valid provider receipt.

    The verified invariant is:
    processed = emitted-segment units + zero-segment units + failed units.
    """

    expected = [str(unit_id) for unit_id in expected_unit_ids]
    if not expected:
        raise UnitAccountingError("expected_unit_ids cannot be empty")
    if len(expected) != len(set(expected)):
        raise UnitAccountingError("expected_unit_ids contains duplicates")

    normalized = [
        receipt if isinstance(receipt, UnitReceipt) else UnitReceipt.from_dict(receipt)
        for receipt in receipts
    ]
    for receipt in normalized:
        receipt.validate()

    by_id: dict[str, UnitReceipt] = {}
    duplicates: list[str] = []
    for receipt in normalized:
        if receipt.unit_id in by_id:
            duplicates.append(receipt.unit_id)
        else:
            by_id[receipt.unit_id] = receipt
    if duplicates:
        raise UnitAccountingError(
            "duplicate provider receipts: " + ", ".join(sorted(set(duplicates)))
        )

    expected_set = set(expected)
    receipt_set = set(by_id)
    missing = sorted(expected_set - receipt_set)
    unexpected = sorted(receipt_set - expected_set)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise UnitAccountingError("unit identity mismatch: " + "; ".join(details))

    emitted: list[str] = []
    zero_segment: list[str] = []
    failed: list[str] = []
    for unit_id in expected:
        receipt = by_id[unit_id]
        if receipt.state == "FAILED":
            failed.append(unit_id)
        elif receipt.segment_count == 0:
            zero_segment.append(unit_id)
        else:
            emitted.append(unit_id)

    processed_count = len(normalized)
    accounted_count = len(emitted) + len(zero_segment) + len(failed)
    if processed_count != accounted_count:
        raise UnitAccountingError(
            f"accounting invariant failed: processed={processed_count}, "
            f"accounted={accounted_count}"
        )

    return {
        "contract": "ZERO_SEGMENT_UNIT_ACCOUNTING_V1",
        "state": "ACCOUNTING_VERIFIED" if not failed else "ACCOUNTING_VERIFIED_WITH_FAILURES",
        "expected_unit_count": len(expected),
        "processed_unit_count": processed_count,
        "emitted_segment_unit_count": len(emitted),
        "zero_segment_unit_count": len(zero_segment),
        "failed_unit_count": len(failed),
        "emitted_segment_unit_ids": emitted,
        "zero_segment_unit_ids": zero_segment,
        "failed_unit_ids": failed,
        "raw_provider_receipt_count": processed_count,
        "invariant": (
            "processed_unit_count = emitted_segment_unit_count + "
            "zero_segment_unit_count + failed_unit_count"
        ),
    }
