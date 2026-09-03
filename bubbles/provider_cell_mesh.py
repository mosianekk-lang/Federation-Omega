from __future__ import annotations

"""Provider cell selection and bounded dispatch for Bubbles Ω.

Provider cells are execution adapters, not sovereign agents. The mesh chooses
among explicitly registered cells using current health, semantic readback,
latency and cost evidence. Effectful dispatch requires an exact resolved
authority decision. Uncertain effects transition to HOLD_READBACK rather than
being retried blindly.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Iterable, Mapping, Sequence

from federation.mission_ir import MissionIR

from .provider_authority_fabric import AuthorityLeaseDecision, AuthorityState


SCHEMA = "BUBBLES-OMEGA-PROVIDER-CELL-MESH-V1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


@dataclass(frozen=True, slots=True)
class ProviderCellSpec:
    cell_id: str
    provider: str
    connector: str
    capabilities: tuple[str, ...]
    semantic_readback_required: bool = True
    supports_effect_classes: tuple[str, ...] = ("NO_EFFECT", "READ_ONLY")
    priority: float = 50.0

    def validate(self) -> "ProviderCellSpec":
        if not all((self.cell_id.strip(), self.provider.strip(), self.connector.strip())):
            raise ValueError("PROVIDER_CELL_IDENTITY_REQUIRED")
        if not self.capabilities:
            raise ValueError("PROVIDER_CELL_CAPABILITIES_REQUIRED")
        allowed = {"NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}
        if set(item.upper() for item in self.supports_effect_classes) - allowed:
            raise ValueError("PROVIDER_CELL_EFFECT_CLASS_INVALID")
        if not 0 <= float(self.priority) <= 100:
            raise ValueError("PROVIDER_CELL_PRIORITY_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ProviderCellHealth:
    cell_id: str
    provider_native: bool
    provider_live: bool
    semantic_readback_ready: bool
    credential_bound: bool
    latency_ms: float | None = None
    estimated_cost_microunits: int | None = None
    proof_refs: tuple[str, ...] = ()
    observed_at: str = ""

    def validate(self) -> "ProviderCellHealth":
        if not self.cell_id.strip():
            raise ValueError("PROVIDER_CELL_HEALTH_ID_REQUIRED")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("PROVIDER_CELL_LATENCY_INVALID")
        if self.estimated_cost_microunits is not None and self.estimated_cost_microunits < 0:
            raise ValueError("PROVIDER_CELL_COST_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    schema: str
    mission_id: str
    capability_id: str
    state: str
    cell_id: str = ""
    provider: str = ""
    connector: str = ""
    score: float = 0.0
    proof_refs: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        return payload


@dataclass(frozen=True, slots=True)
class ProviderExecutionReceipt:
    schema: str
    mission_id: str
    capability_id: str
    cell_id: str
    provider: str
    state: str
    operation_id: str
    idempotency_key: str
    transport_ok: bool
    provider_native: bool
    semantic_readback_verified: bool
    effect_attempted: bool
    effect_class: str
    result_ref: str = ""
    result_sha256: str = ""
    readback_ref: str = ""
    proof_refs: tuple[str, ...] = ()
    cost_microunits: int | None = None
    latency_ms: float | None = None
    provider_effect_authorized: bool = False
    secret_value_recorded: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        return payload


class ProviderCellMesh:
    def __init__(self, cells: Sequence[ProviderCellSpec]) -> None:
        validated = [cell.validate() for cell in cells]
        if len({cell.cell_id for cell in validated}) != len(validated):
            raise ValueError("DUPLICATE_PROVIDER_CELL_ID")
        self.cells = {cell.cell_id: cell for cell in validated}

    @staticmethod
    def _provider_allowed(mission: MissionIR, provider: str) -> bool:
        mission = mission.normalized()
        if provider in mission.provider_denylist:
            return False
        if mission.provider_allowlist and provider not in mission.provider_allowlist:
            return False
        return True

    def select(
        self,
        mission: MissionIR,
        capability_id: str,
        *,
        health: Sequence[ProviderCellHealth],
    ) -> ProviderSelection:
        mission = mission.normalized()
        mission.validate()
        by_id = {item.validate().cell_id: item for item in health}
        candidates: list[tuple[float, ProviderCellSpec, ProviderCellHealth]] = []
        for cell in self.cells.values():
            if capability_id not in cell.capabilities:
                continue
            if mission.effect_class not in tuple(item.upper() for item in cell.supports_effect_classes):
                continue
            if not self._provider_allowed(mission, cell.provider):
                continue
            status = by_id.get(cell.cell_id)
            if status is None or not status.provider_native:
                continue
            if mission.effect_class in {"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"} and not status.credential_bound:
                continue
            if cell.semantic_readback_required and not status.semantic_readback_ready:
                continue
            if not status.provider_live:
                continue
            cost = status.estimated_cost_microunits or 0
            if mission.max_cost_microunits is not None and cost > mission.max_cost_microunits:
                continue
            latency = status.latency_ms or 0.0
            if mission.latency_target_ms is not None and latency > mission.latency_target_ms:
                continue
            score = (
                float(cell.priority)
                + 20.0
                + (10.0 if status.semantic_readback_ready else 0.0)
                + (5.0 if status.credential_bound else 0.0)
                - min(20.0, latency / 1000.0)
                - min(20.0, cost / 1_000_000.0)
            )
            candidates.append((score, cell, status))

        if not candidates:
            return ProviderSelection(
                schema=SCHEMA,
                mission_id=mission.mission_id,
                capability_id=capability_id,
                state="PROVIDER_GATED",
                reason="NO_PROVIDER_CELL_MEETS_CURRENT_LIVE_READBACK_COST_LATENCY_POLICY",
            )

        score, cell, status = max(candidates, key=lambda item: (item[0], item[1].cell_id))
        return ProviderSelection(
            schema=SCHEMA,
            mission_id=mission.mission_id,
            capability_id=capability_id,
            state="SELECTED",
            cell_id=cell.cell_id,
            provider=cell.provider,
            connector=cell.connector,
            score=round(score, 6),
            proof_refs=_clean(status.proof_refs),
            reason="BEST_CURRENT_PROOF_ADJUSTED_PROVIDER_CELL",
        )

    def dispatch(
        self,
        mission: MissionIR,
        selection: ProviderSelection,
        *,
        authority: AuthorityLeaseDecision,
        payload: Mapping[str, Any],
        execute: Callable[[ProviderCellSpec, Mapping[str, Any], str], Mapping[str, Any]],
        readback: Callable[[ProviderCellSpec, Mapping[str, Any], str], Mapping[str, Any]],
    ) -> ProviderExecutionReceipt:
        mission = mission.normalized()
        mission.validate()
        if selection.state != "SELECTED" or selection.cell_id not in self.cells:
            raise ValueError("PROVIDER_CELL_SELECTION_REQUIRED")
        cell = self.cells[selection.cell_id]
        effectful = mission.effect_class in {"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}
        if mission.effect_class == "CONSEQUENTIAL_EFFECT":
            return ProviderExecutionReceipt(
                schema=SCHEMA,
                mission_id=mission.mission_id,
                capability_id=selection.capability_id,
                cell_id=cell.cell_id,
                provider=cell.provider,
                state="APPROVAL_REQUIRED",
                operation_id="",
                idempotency_key="",
                transport_ok=False,
                provider_native=False,
                semantic_readback_verified=False,
                effect_attempted=False,
                effect_class=mission.effect_class,
                provider_effect_authorized=False,
                reason="CONSEQUENTIAL_EFFECT_NOT_AUTOMATICALLY_DISPATCHED",
            )
        if effectful and authority.state != AuthorityState.RESOLVED.value:
            return ProviderExecutionReceipt(
                schema=SCHEMA,
                mission_id=mission.mission_id,
                capability_id=selection.capability_id,
                cell_id=cell.cell_id,
                provider=cell.provider,
                state="AUTHORITY_GATED",
                operation_id="",
                idempotency_key="",
                transport_ok=False,
                provider_native=False,
                semantic_readback_verified=False,
                effect_attempted=False,
                effect_class=mission.effect_class,
                provider_effect_authorized=False,
                reason="EXACT_PROVIDER_AUTHORITY_LEASE_REQUIRED",
            )
        if effectful and (
            authority.provider != cell.provider
            or authority.connector != cell.connector
            or authority.capability_id != selection.capability_id
        ):
            raise ValueError("PROVIDER_AUTHORITY_CELL_MISMATCH")

        operation_id = "BUB-OP-" + _digest(
            {
                "mission_id": mission.mission_id,
                "capability_id": selection.capability_id,
                "cell_id": cell.cell_id,
                "payload": dict(payload),
            }
        )[:24].upper()
        idempotency_key = _digest(
            {
                "operation_id": operation_id,
                "mission_digest": mission.digest(),
                "cell_id": cell.cell_id,
            }
        )
        execution = dict(execute(cell, dict(payload), idempotency_key))
        transport_ok = execution.get("transport_ok") is True
        provider_native = execution.get("provider_native") is True
        effect_attempted = execution.get("effect_attempted") is True
        result_ref = str(execution.get("result_ref") or "")
        result_sha = str(execution.get("result_sha256") or "")
        if effect_attempted != effectful:
            return ProviderExecutionReceipt(
                schema=SCHEMA,
                mission_id=mission.mission_id,
                capability_id=selection.capability_id,
                cell_id=cell.cell_id,
                provider=cell.provider,
                state="FAILED_EFFECT_CLASS_MISMATCH",
                operation_id=operation_id,
                idempotency_key=idempotency_key,
                transport_ok=transport_ok,
                provider_native=provider_native,
                semantic_readback_verified=False,
                effect_attempted=effect_attempted,
                effect_class=mission.effect_class,
                result_ref=result_ref,
                result_sha256=result_sha,
                provider_effect_authorized=effectful and authority.provider_effect_authorized,
                reason="EXECUTOR_EFFECT_DECLARATION_MISMATCH",
            )
        if not transport_ok or not provider_native:
            return ProviderExecutionReceipt(
                schema=SCHEMA,
                mission_id=mission.mission_id,
                capability_id=selection.capability_id,
                cell_id=cell.cell_id,
                provider=cell.provider,
                state="PROVIDER_DISPATCH_FAILED",
                operation_id=operation_id,
                idempotency_key=idempotency_key,
                transport_ok=transport_ok,
                provider_native=provider_native,
                semantic_readback_verified=False,
                effect_attempted=effect_attempted,
                effect_class=mission.effect_class,
                result_ref=result_ref,
                result_sha256=result_sha,
                provider_effect_authorized=effectful and authority.provider_effect_authorized,
                reason=str(execution.get("reason") or "PROVIDER_TRANSPORT_OR_NATIVE_BINDING_FAILED"),
            )

        verification = dict(readback(cell, execution, idempotency_key))
        semantic_ok = (
            verification.get("provider_native") is True
            and verification.get("semantic_readback_verified") is True
            and bool(str(verification.get("readback_ref") or ""))
        )
        proof_refs = _clean(
            tuple(selection.proof_refs)
            + tuple(authority.proof_refs)
            + tuple(execution.get("proof_refs") or ())
            + tuple(verification.get("proof_refs") or ())
        )
        state = "PROVIDER_SEMANTIC_READBACK_VERIFIED" if semantic_ok else (
            "HOLD_READBACK" if effect_attempted else "READBACK_REQUIRED"
        )
        return ProviderExecutionReceipt(
            schema=SCHEMA,
            mission_id=mission.mission_id,
            capability_id=selection.capability_id,
            cell_id=cell.cell_id,
            provider=cell.provider,
            state=state,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            transport_ok=True,
            provider_native=True,
            semantic_readback_verified=semantic_ok,
            effect_attempted=effect_attempted,
            effect_class=mission.effect_class,
            result_ref=result_ref,
            result_sha256=result_sha,
            readback_ref=str(verification.get("readback_ref") or ""),
            proof_refs=proof_refs,
            cost_microunits=execution.get("cost_microunits"),
            latency_ms=execution.get("latency_ms"),
            provider_effect_authorized=effectful and authority.provider_effect_authorized,
            secret_value_recorded=False,
            reason="SEMANTIC_READBACK_VERIFIED" if semantic_ok else "PROVIDER_EFFECT_OR_RESULT_REQUIRES_READBACK",
        )


__all__ = [
    "ProviderCellHealth",
    "ProviderCellMesh",
    "ProviderCellSpec",
    "ProviderExecutionReceipt",
    "ProviderSelection",
]
