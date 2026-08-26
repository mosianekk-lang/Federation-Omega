#!/usr/bin/env python3
"""Provider-neutral execution-cell orchestration for SOVARA.

This module does not execute providers. It prevents one provider's authority or
failure from becoming another provider's dependency and requires cell-specific
proof before aggregator admission.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CellState(str, Enum):
    SOURCE_READY = "SOURCE_READY"
    TARGET_PRIVATE_READY = "TARGET_PRIVATE_READY"
    SOURCE_INSTALLED = "SOURCE_INSTALLED"
    METADATA_VERIFIED = "METADATA_VERIFIED"
    SEMANTIC_VERIFIED = "SEMANTIC_VERIFIED"
    FALLBACK_VERIFIED = "FALLBACK_VERIFIED"
    PROVEN = "PROVEN"
    HELD = "HELD"


@dataclass(frozen=True)
class ProviderCell:
    provider: str
    state: CellState
    authority_scope: str
    public_endpoint: bool = False
    provider_call_proven: bool = False
    semantic_readback_proven: bool = False

    @property
    def aggregator_eligible(self) -> bool:
        return (
            self.state in {CellState.SEMANTIC_VERIFIED, CellState.FALLBACK_VERIFIED, CellState.PROVEN}
            and self.provider_call_proven
            and self.semantic_readback_proven
        )


def independent_ready_cells(cells: Iterable[ProviderCell]) -> tuple[ProviderCell, ...]:
    """Return independently eligible cells; one held cell never blocks another."""
    return tuple(cell for cell in cells if cell.aggregator_eligible)


def can_promote_to_litellm(cell: ProviderCell) -> bool:
    return cell.aggregator_eligible


def authority_inheritance_allowed(source: ProviderCell, target: ProviderCell) -> bool:
    """Provider authority is never inherited across cells."""
    return False


def next_openrouter_gate(*, source_installed: bool, metadata_verified: bool, semantic_verified: bool) -> str:
    if not source_installed:
        return "SOURCE_INSTALL_AND_EXACT_READBACK"
    if not metadata_verified:
        return "PROVIDER_METADATA_READBACK"
    if not semantic_verified:
        return "EXACT_NONCE_SEMANTIC_READBACK"
    return "LITELLM_ADMISSION_AND_FORCED_FALLBACK_PROOF"
