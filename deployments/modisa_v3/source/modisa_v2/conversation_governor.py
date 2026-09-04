"""Directive closure, safe fallback, and material-update controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DirectiveState(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class Directive:
    directive_id: str
    text: str
    sequence: int
    state: DirectiveState = DirectiveState.OPEN
    proof_ids: tuple[str, ...] = ()
    reason: str | None = None


class DirectiveLedger:
    def __init__(self) -> None:
        self._items: dict[str, Directive] = {}

    def add(self, directive_id: str, text: str, sequence: int) -> Directive:
        if directive_id in self._items:
            raise ValueError("Directive already exists")
        item = Directive(directive_id, text, sequence)
        self._items[directive_id] = item
        return item

    def resolve(
        self,
        directive_id: str,
        state: DirectiveState,
        *,
        proof_ids: tuple[str, ...] = (),
        reason: str | None = None,
    ) -> Directive:
        current = self._items[directive_id]
        if state is DirectiveState.OPEN:
            raise ValueError("Resolution cannot reopen a directive")
        if state is DirectiveState.DONE and not proof_ids:
            raise ValueError("Completed directives require proof")
        if state in {DirectiveState.BLOCKED, DirectiveState.SUPERSEDED} and not reason:
            raise ValueError("Blocked or superseded directives require a reason")
        updated = Directive(
            current.directive_id,
            current.text,
            current.sequence,
            state,
            tuple(sorted(set(proof_ids))),
            reason,
        )
        self._items[directive_id] = updated
        return updated

    def ordered(self) -> tuple[Directive, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: item.sequence))

    def open_items(self) -> tuple[Directive, ...]:
        return tuple(item for item in self.ordered() if item.state is DirectiveState.OPEN)

    def can_finalize(self) -> bool:
        return not self.open_items()


class SafeFallback(StrEnum):
    CONTINUE_OFFLINE = "CONTINUE_OFFLINE"
    BLOCK_LIVE_ONLY = "BLOCK_LIVE_ONLY"
    EXECUTE_LIVE = "EXECUTE_LIVE"


def select_credential_fallback(
    *, credentials_present: bool, offline_route_allowed: bool, live_required: bool
) -> SafeFallback:
    if credentials_present:
        return SafeFallback.EXECUTE_LIVE
    if offline_route_allowed and not live_required:
        return SafeFallback.CONTINUE_OFFLINE
    return SafeFallback.BLOCK_LIVE_ONLY


class MaterialUpdateBudget:
    def __init__(self, maximum_pre_result_updates: int = 2) -> None:
        if maximum_pre_result_updates < 0:
            raise ValueError("Update budget cannot be negative")
        self.maximum = maximum_pre_result_updates
        self.used = 0

    def admit(self, *, material_delta: bool, blocker: bool = False) -> bool:
        if blocker:
            return True
        if not material_delta or self.used >= self.maximum:
            return False
        self.used += 1
        return True
