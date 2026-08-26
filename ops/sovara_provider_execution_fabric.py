#!/usr/bin/env python3
"""SOVARA Sovereign Multi-Provider Execution Fabric v1.

Provider-neutral orchestration only. This module does not resolve credentials,
perform provider calls, or grant provider authority. It selects independent
provider cells and promotes only provider receipts that satisfy the proof contract.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "SOVARA-PROVIDER-EXECUTION-FABRIC-V1"

class CellState(str, Enum):
    HELD = "HELD"
    READY = "READY"
    PROVEN = "PROVEN"
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
        ))

@dataclass(frozen=True, slots=True)
class ProviderCell:
    provider: str
    substrate: Substrate
    credential_reference_ready: bool
    runtime_authorised: bool
    health_ok: bool
    funding_or_quota_ready: bool
    state: CellState = CellState.READY
    circuit_open: bool = False
    failure_fingerprint: str | None = None

    @property
    def eligible(self) -> bool:
        return all((
            self.credential_reference_ready,
            self.runtime_authorised,
            self.health_ok,
            self.funding_or_quota_ready,
            self.state in {CellState.READY, CellState.PROVEN},
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

def select_provider_route(
    cells: Sequence[ProviderCell],
    receipts: Mapping[str, ProofReceipt] | None = None,
    preferred_order: Sequence[str] = (),
) -> RouteDecision:
    receipts = receipts or {}
    preference = {name: i for i, name in enumerate(preferred_order)}
    eligible = [c for c in cells if c.eligible]
    held = [c for c in cells if not c.eligible]
    eligible.sort(key=lambda c: (preference.get(c.provider, 10_000), c.provider, c.substrate.value))
    selected = eligible[0] if eligible else None
    litellm = tuple(sorted(
        provider for provider, receipt in receipts.items()
        if receipt.promotion_ready
    ))
    core = {
        "schema": SCHEMA,
        "selected_provider": selected.provider if selected else None,
        "selected_substrate": selected.substrate.value if selected else None,
        "eligible_providers": tuple(c.provider for c in eligible),
        "held_providers": tuple(c.provider for c in held),
        "litellm_admission": litellm,
        "reason": "independent_provider_cell_selected" if selected else "no_provider_cell_currently_eligible",
    }
    return RouteDecision(**core, fingerprint=_fingerprint(core))

def classify_provider_failure(*, provider: str, fingerprint: str, materially_changed_dependency: bool) -> dict[str, object]:
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
    return [
        {
            **asdict(cell),
            "substrate": cell.substrate.value,
            "state": cell.state.value,
            "eligible": cell.eligible,
        }
        for cell in cells
    ]
