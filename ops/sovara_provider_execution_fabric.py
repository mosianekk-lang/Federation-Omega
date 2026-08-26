#!/usr/bin/env python3
"""SOVARA Sovereign Multi-Provider Execution Fabric v1.1.

Provider-neutral orchestration only. This module does not resolve credentials,
perform provider calls, or grant provider authority. It preserves the original
provider-cell lifecycle contract while adding independent substrate selection,
provider-local circuit breaking, proof receipts, and progressive aggregator
admission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "SOVARA-PROVIDER-EXECUTION-FABRIC-V1"


class CellState(str, Enum):
    SOURCE_READY = "SOURCE_READY"
    TARGET_PRIVATE_READY = "TARGET_PRIVATE_READY"
    SOURCE_INSTALLED = "SOURCE_INSTALLED"
    METADATA_VERIFIED = "METADATA_VERIFIED"
    SEMANTIC_VERIFIED = "SEMANTIC_VERIFIED"
    FALLBACK_VERIFIED = "FALLBACK_VERIFIED"
    PROVEN = "PROVEN"
    HELD = "HELD"
    READY = "READY"
    DEGRADED = "DEGRADED"


class Substrate(str, Enum):
    APPS_SCRIPT = "apps_script"
    CLOUD_RUN = "cloud_run"
    PRIVATE_RUNTIME = "private_runtime"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class ProofReceipt:
    provider: str
    identity_verified: bool
    metadata_verified: bool
    semantic_nonce_verified: bool
    resolved_model_readback: bool
    usage_readback: bool
    cost_readback: bool
    generation_readback: bool
    failure_fingerprint: str | None = None

    @property
    def promotion_ready(self) -> bool:
        return all((
            self.identity_verified,
            self.metadata_verified,
            self.semantic_nonce_verified,
            self.resolved_model_readback,
            self.usage_readback,
            self.cost_readback,
            self.generation_readback,
        ))


@dataclass(frozen=True, slots=True)
class ProviderCell:
    # Original v1 fields remain first and positional-compatible.
    provider: str
    state: CellState
    authority_scope: str
    public_endpoint: bool = False
    provider_call_proven: bool = False
    semantic_readback_proven: bool = False

    # v1.1 additive execution-fabric fields.
    substrate: Substrate = Substrate.PRIVATE_RUNTIME
    credential_reference_ready: bool = False
    runtime_authorised: bool = False
    health_ok: bool = True
    funding_or_quota_ready: bool = False
    circuit_open: bool = False
    failure_fingerprint: str | None = None

    @property
    def aggregator_eligible(self) -> bool:
        """Backward-compatible v1 semantic admission contract."""
        return (
            self.state in {CellState.SEMANTIC_VERIFIED, CellState.FALLBACK_VERIFIED, CellState.PROVEN}
            and self.provider_call_proven
            and self.semantic_readback_proven
        )

    @property
    def operational_eligible(self) -> bool:
        """Whether this exact provider/substrate cell may be selected to execute."""
        return all((
            self.credential_reference_ready,
            self.runtime_authorised,
            self.health_ok,
            self.funding_or_quota_ready,
            self.state not in {CellState.HELD, CellState.DEGRADED},
            not self.circuit_open,
        ))


@dataclass(frozen=True, slots=True)
class RouteDecision:
    schema: str
    selected_provider: str | None
    selected_substrate: str | None
    eligible_providers: tuple[str, ...]
    held_providers: tuple[str, ...]
    litellm_admission: tuple[str, ...]
    reason: str
    fingerprint: str


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def independent_ready_cells(cells: Iterable[ProviderCell]) -> tuple[ProviderCell, ...]:
    """Return independently aggregator-eligible cells; one held cell never blocks another."""
    return tuple(cell for cell in cells if cell.aggregator_eligible)


def can_promote_to_litellm(cell: ProviderCell) -> bool:
    """Backward-compatible v1 cell-level semantic promotion gate."""
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


def select_provider_route(
    cells: Sequence[ProviderCell],
    receipts: Mapping[str, ProofReceipt] | None = None,
    preferred_order: Sequence[str] = (),
) -> RouteDecision:
    """Select one eligible provider/substrate without globalising other-cell failures."""
    receipts = receipts or {}
    preference = {name: i for i, name in enumerate(preferred_order)}
    eligible_cells = [cell for cell in cells if cell.operational_eligible]
    eligible_cells.sort(
        key=lambda cell: (
            preference.get(cell.provider, 10_000),
            cell.provider,
            cell.substrate.value,
        )
    )
    selected = eligible_cells[0] if eligible_cells else None

    eligible_provider_names = {cell.provider for cell in eligible_cells}
    all_provider_names = {cell.provider for cell in cells}
    held_provider_names = all_provider_names - eligible_provider_names

    litellm = tuple(sorted(
        provider for provider, receipt in receipts.items()
        if receipt.promotion_ready
    ))
    core = {
        "schema": SCHEMA,
        "selected_provider": selected.provider if selected else None,
        "selected_substrate": selected.substrate.value if selected else None,
        "eligible_providers": tuple(sorted(eligible_provider_names)),
        "held_providers": tuple(sorted(held_provider_names)),
        "litellm_admission": litellm,
        "reason": "independent_provider_cell_selected" if selected else "no_provider_cell_currently_eligible",
    }
    return RouteDecision(**core, fingerprint=_fingerprint(core))


def classify_provider_failure(
    *,
    provider: str,
    fingerprint: str,
    materially_changed_dependency: bool,
) -> dict[str, object]:
    """Open or close only the affected provider circuit; never create global stall."""
    if materially_changed_dependency:
        return {
            "provider": provider,
            "failure_fingerprint": fingerprint,
            "circuit_open": False,
            "retry_policy": "REOPEN_ON_MATERIAL_CHANGE",
            "global_stall": False,
        }
    return {
        "provider": provider,
        "failure_fingerprint": fingerprint,
        "circuit_open": True,
        "retry_policy": "SUPPRESS_UNCHANGED_RETRY",
        "global_stall": False,
    }


def provider_cell_matrix(cells: Iterable[ProviderCell]) -> list[dict[str, object]]:
    """Expose value-free provider-cell state for routing/assurance projections."""
    return [
        {
            **asdict(cell),
            "state": cell.state.value,
            "substrate": cell.substrate.value,
            "aggregator_eligible": cell.aggregator_eligible,
            "operational_eligible": cell.operational_eligible,
        }
        for cell in cells
    ]
