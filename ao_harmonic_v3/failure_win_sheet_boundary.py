from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


EVENT_SHEET = "Failure-Win Events v2"
MANIFEST_SHEET = "Failure-Win Receiver Manifest v2"
ALIAS_SHEET = "Failure-Win Receiver Aliases v2"

# Google Sheets zero-based column indexes. E:M is the formula-owned projection.
MANIFEST_SPILL_START = 4
MANIFEST_SPILL_END_EXCLUSIVE = 13
MANIFEST_REGISTRY_START = 0
MANIFEST_REGISTRY_END_EXCLUSIVE = 4
MANIFEST_SNAPSHOT_START = 14
MANIFEST_SNAPSHOT_END_EXCLUSIVE = 16


class FailureWinSheetRole(str, Enum):
    EVENT_WRITER = "EVENT_WRITER"
    RECEIVER_REGISTRY_MANAGER = "RECEIVER_REGISTRY_MANAGER"
    RECEIVER_ALIAS_MANAGER = "RECEIVER_ALIAS_MANAGER"
    MANIFEST_COMPILER = "MANIFEST_COMPILER"


class ProjectionWriteViolation(ValueError):
    pass


@dataclass(frozen=True)
class FailureWinSheetWrite:
    sheet_name: str
    start_column: int
    end_column_exclusive: int
    role: FailureWinSheetRole

    def __post_init__(self) -> None:
        if self.start_column < 0 or self.end_column_exclusive <= self.start_column:
            raise ValueError("INVALID_COLUMN_RANGE")


def assert_failure_win_sheet_write_allowed(write: FailureWinSheetWrite) -> None:
    """Fail closed before a Failure-Win Sheets write crosses a source/projection boundary.

    Normal behavior/currentness events belong only in the append-only Events sheet.
    Manifest E:M is a derived MAP/XLOOKUP spill and must never be directly written.
    Registry A:D and snapshot metadata O:P have distinct authority roles.
    """

    if write.sheet_name == EVENT_SHEET:
        if write.role is FailureWinSheetRole.EVENT_WRITER:
            return
        raise ProjectionWriteViolation("EVENT_SHEET_ROLE_MISMATCH")

    if write.sheet_name == ALIAS_SHEET:
        if write.role is FailureWinSheetRole.RECEIVER_ALIAS_MANAGER:
            return
        raise ProjectionWriteViolation("ALIAS_SHEET_ROLE_MISMATCH")

    if write.sheet_name != MANIFEST_SHEET:
        raise ProjectionWriteViolation("UNKNOWN_FAILURE_WIN_SHEET")

    overlaps_spill = not (
        write.end_column_exclusive <= MANIFEST_SPILL_START
        or write.start_column >= MANIFEST_SPILL_END_EXCLUSIVE
    )
    if overlaps_spill:
        raise ProjectionWriteViolation("DERIVED_MANIFEST_SPILL_WRITE_PROHIBITED")

    if (
        write.role is FailureWinSheetRole.RECEIVER_REGISTRY_MANAGER
        and write.start_column >= MANIFEST_REGISTRY_START
        and write.end_column_exclusive <= MANIFEST_REGISTRY_END_EXCLUSIVE
    ):
        return

    if (
        write.role is FailureWinSheetRole.MANIFEST_COMPILER
        and write.start_column >= MANIFEST_SNAPSHOT_START
        and write.end_column_exclusive <= MANIFEST_SNAPSHOT_END_EXCLUSIVE
    ):
        return

    raise ProjectionWriteViolation("MANIFEST_WRITE_ROLE_OR_RANGE_PROHIBITED")
