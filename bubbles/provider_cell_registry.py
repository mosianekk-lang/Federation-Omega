from __future__ import annotations

"""Bubbles Ω real provider-cell registry adapter.

This module reuses SOVARA's provider execution fabric as the provider-cell
operational source and projects only evidence-backed cells into the Bubbles Ω
ProviderCellMesh. It does not create credentials, provider authority, spend,
quota, deployment rights, or live-provider proof.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from ops.sovara_provider_execution_fabric import CellState, ProviderCell, ProofReceipt, Substrate

from .provider_cell_mesh import ProviderCellHealth, ProviderCellSpec


SCHEMA = "BUBBLES-OMEGA-PROVIDER-CELL-REGISTRY-V1"


@dataclass(frozen=True, slots=True)
class ProviderCellBinding:
    cell_id: str
    provider: str
    connector: str
    substrate: Substrate
    capabilities: tuple[str, ...]
    effect_classes: tuple[str, ...] = ("NO_EFFECT", "READ_ONLY")
    priority: float = 50.0

    def validate(self) -> "ProviderCellBinding":
        if not all((self.cell_id.strip(), self.provider.strip(), self.connector.strip())):
            raise ValueError("PROVIDER_BINDING_IDENTITY_REQUIRED")
        if not self.capabilities:
            raise ValueError("PROVIDER_BINDING_CAPABILITY_REQUIRED")
        return self

    def spec(self) -> ProviderCellSpec:
        self.validate()
        return ProviderCellSpec(
            cell_id=self.cell_id,
            provider=self.provider,
            connector=self.connector,
            capabilities=self.capabilities,
            semantic_readback_required=True,
            supports_effect_classes=self.effect_classes,
            priority=self.priority,
        ).validate()


@dataclass(frozen=True, slots=True)
class RegistryProjection:
    schema: str
    specs: tuple[ProviderCellSpec, ...]
    health: tuple[ProviderCellHealth, ...]
    unmatched_bindings: tuple[str, ...]
    unmatched_sovara_cells: tuple[str, ...]


class ProviderCellRegistry:
    """Project SOVARA provider-cell truth into Bubbles execution-cell truth.

    The projection is intentionally fail-closed:
    - SOURCE_READY/METADATA_VERIFIED alone never become provider_live;
    - operational_eligible alone is insufficient without a proven provider call;
    - semantic readback must be proven independently;
    - credentials are represented only as a boolean reference-ready state.
    """

    def __init__(self, bindings: Sequence[ProviderCellBinding]) -> None:
        validated = tuple(binding.validate() for binding in bindings)
        if len({item.cell_id for item in validated}) != len(validated):
            raise ValueError("DUPLICATE_PROVIDER_BINDING_ID")
        self.bindings = validated

    @staticmethod
    def _cell_key(provider: str, substrate: Substrate) -> tuple[str, str]:
        return provider.strip().casefold(), substrate.value

    @staticmethod
    def _proof_ready(cell: ProviderCell, receipt: ProofReceipt | None) -> bool:
        if receipt is None:
            return bool(cell.semantic_readback_proven)
        return bool(cell.semantic_readback_proven and receipt.promotion_ready)

    def project(
        self,
        cells: Sequence[ProviderCell],
        *,
        receipts: Mapping[str, ProofReceipt] | None = None,
        proof_refs: Mapping[str, Iterable[str]] | None = None,
        observed_at: str = "",
        latency_ms: Mapping[str, float] | None = None,
        estimated_cost_microunits: Mapping[str, int] | None = None,
    ) -> RegistryProjection:
        receipts = dict(receipts or {})
        proof_refs = dict(proof_refs or {})
        latency_ms = dict(latency_ms or {})
        estimated_cost_microunits = dict(estimated_cost_microunits or {})
        source = {self._cell_key(cell.provider, cell.substrate): cell for cell in cells}
        used: set[tuple[str, str]] = set()
        specs: list[ProviderCellSpec] = []
        health: list[ProviderCellHealth] = []
        unmatched: list[str] = []

        for binding in self.bindings:
            specs.append(binding.spec())
            key = self._cell_key(binding.provider, binding.substrate)
            cell = source.get(key)
            if cell is None:
                unmatched.append(binding.cell_id)
                health.append(
                    ProviderCellHealth(
                        cell_id=binding.cell_id,
                        provider_native=False,
                        provider_live=False,
                        semantic_readback_ready=False,
                        credential_bound=False,
                        proof_refs=(),
                        observed_at=observed_at,
                    )
                )
                continue

            used.add(key)
            receipt = receipts.get(binding.provider)
            provider_native = bool(cell.provider_call_proven)
            semantic_ready = self._proof_ready(cell, receipt)
            provider_live = bool(
                cell.operational_eligible
                and provider_native
                and semantic_ready
                and cell.state not in {CellState.HELD, CellState.DEGRADED}
            )
            refs = tuple(sorted({str(x).strip() for x in proof_refs.get(binding.cell_id, ()) if str(x).strip()}))
            health.append(
                ProviderCellHealth(
                    cell_id=binding.cell_id,
                    provider_native=provider_native,
                    provider_live=provider_live,
                    semantic_readback_ready=semantic_ready,
                    credential_bound=bool(cell.credential_reference_ready),
                    latency_ms=latency_ms.get(binding.cell_id),
                    estimated_cost_microunits=estimated_cost_microunits.get(binding.cell_id),
                    proof_refs=refs,
                    observed_at=observed_at,
                ).validate()
            )

        unmatched_sovara = tuple(
            sorted(f"{cell.provider}:{cell.substrate.value}" for key, cell in source.items() if key not in used)
        )
        return RegistryProjection(
            schema=SCHEMA,
            specs=tuple(specs),
            health=tuple(health),
            unmatched_bindings=tuple(sorted(unmatched)),
            unmatched_sovara_cells=unmatched_sovara,
        )


def default_federation_bindings() -> tuple[ProviderCellBinding, ...]:
    """Known execution homes; definitions are not live-provider claims."""

    return (
        ProviderCellBinding(
            cell_id="google-cloud-cloud-run",
            provider="Google Cloud",
            connector="sovara.google_cloud.cloud_run",
            substrate=Substrate.CLOUD_RUN,
            capabilities=("GOOGLE_CLOUD_READ", "GOOGLE_CLOUD_EFFECTS"),
            effect_classes=("NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT"),
            priority=80.0,
        ),
        ProviderCellBinding(
            cell_id="google-apps-script",
            provider="Google Apps Script",
            connector="sovara.google_apps_script",
            substrate=Substrate.APPS_SCRIPT,
            capabilities=("APPS_SCRIPT_READBACK", "APPS_SCRIPT_EFFECTS"),
            effect_classes=("NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT"),
            priority=78.0,
        ),
        ProviderCellBinding(
            cell_id="openai-private-runtime",
            provider="OpenAI",
            connector="sovara.openai.private_runtime",
            substrate=Substrate.PRIVATE_RUNTIME,
            capabilities=("OPENAI_INFERENCE",),
            effect_classes=("NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT"),
            priority=75.0,
        ),
        ProviderCellBinding(
            cell_id="openrouter-private-runtime",
            provider="OpenRouter",
            connector="sovara.openrouter.private_runtime",
            substrate=Substrate.PRIVATE_RUNTIME,
            capabilities=("OPENROUTER_INFERENCE",),
            effect_classes=("NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT"),
            priority=70.0,
        ),
        ProviderCellBinding(
            cell_id="gemini-private-runtime",
            provider="Gemini",
            connector="sovara.gemini.private_runtime",
            substrate=Substrate.PRIVATE_RUNTIME,
            capabilities=("GEMINI_INFERENCE",),
            effect_classes=("NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT"),
            priority=72.0,
        ),
    )


__all__ = [
    "ProviderCellBinding",
    "ProviderCellRegistry",
    "RegistryProjection",
    "default_federation_bindings",
]
