from __future__ import annotations

"""Mission-correlated telemetry bridge for Bubbles Ω.

Local trace formation reuses SOL 6.2 TraceEnvelope. External OTEL export is a
separate provider effect and is never attempted without an exact resolved
Bubbles provider-authority decision. Transport success without semantic
provider readback becomes HOLD_READBACK.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import time
from typing import Any, Callable, Mapping

from sol_61_runtime.sol_62_frontier_primitives import TraceEnvelope

from .provider_authority_fabric import AuthorityLeaseDecision, AuthorityState


SCHEMA = "BUBBLES-OMEGA-MISSION-TELEMETRY-V1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hex(seed: Mapping[str, Any], length: int) -> str:
    return sha256(_canonical(dict(seed)).encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True, slots=True)
class TelemetryExportContract:
    capability_id: str
    provider: str
    connector: str
    action: str = "export_otel_trace"


@dataclass(frozen=True, slots=True)
class MissionTraceReceipt:
    schema: str
    mission_id: str
    trace_id: str
    span_id: str
    state: str
    otel_attributes: Mapping[str, Any]
    provider: str = ""
    connector: str = ""
    operation_id: str = ""
    readback_ref: str = ""
    proof_refs: tuple[str, ...] = ()
    transport_ok: bool = False
    provider_native: bool = False
    semantic_readback_verified: bool = False
    provider_effect_authorized: bool = False
    secret_value_recorded: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        payload["otel_attributes"] = dict(self.otel_attributes)
        return payload


class MissionTelemetryBridge:
    @staticmethod
    def envelope(
        *,
        mission_id: str,
        step: str,
        kind: str,
        status: str,
        attributes: Mapping[str, Any],
        ordinal: int = 0,
        parent_span_id: str | None = None,
        duration_ms: float = 0.0,
        started_at_epoch_ms: int | None = None,
    ) -> TraceEnvelope:
        mission_id = str(mission_id).strip()
        step = " ".join(str(step).split())
        if not mission_id or not step:
            raise ValueError("MISSION_TELEMETRY_IDENTITY_REQUIRED")
        trace_id = _hex({"mission_id": mission_id}, 32)
        span_id = _hex({"mission_id": mission_id, "step": step, "ordinal": int(ordinal)}, 16)
        return TraceEnvelope(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            kind=str(kind).strip() or "mission",
            name=step,
            started_at_epoch_ms=(int(time.time() * 1000) if started_at_epoch_ms is None else int(started_at_epoch_ms)),
            duration_ms=float(duration_ms),
            status=str(status).strip() or "UNSET",
            attributes={"bubbles.mission.id": mission_id, **dict(attributes)},
        )

    @staticmethod
    def local_receipt(mission_id: str, envelope: TraceEnvelope, *, proof_refs: tuple[str, ...] = ()) -> MissionTraceReceipt:
        return MissionTraceReceipt(
            schema=SCHEMA,
            mission_id=mission_id,
            trace_id=envelope.trace_id,
            span_id=envelope.span_id,
            state="LOCAL_TRACE_VERIFIED",
            otel_attributes=envelope.otel_attributes(),
            proof_refs=tuple(sorted(set(proof_refs))),
            reason="LOCAL_OTEL_SAFE_TRACE_FORMED_NO_EXTERNAL_EXPORT",
        )

    @staticmethod
    def export(
        mission_id: str,
        envelope: TraceEnvelope,
        *,
        contract: TelemetryExportContract,
        authority: AuthorityLeaseDecision,
        exporter: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
    ) -> MissionTraceReceipt:
        attrs = envelope.otel_attributes()
        exact = (
            authority.state == AuthorityState.RESOLVED.value
            and authority.capability_id == contract.capability_id
            and authority.provider == contract.provider
            and authority.connector == contract.connector
            and authority.action == contract.action
            and authority.provider_effect_authorized
        )
        if not exact:
            return MissionTraceReceipt(
                schema=SCHEMA,
                mission_id=mission_id,
                trace_id=envelope.trace_id,
                span_id=envelope.span_id,
                state="EXPORT_AUTHORITY_GATED",
                otel_attributes=attrs,
                provider=contract.provider,
                connector=contract.connector,
                provider_effect_authorized=False,
                reason="EXACT_PROVIDER_NATIVE_TELEMETRY_EXPORT_GRANT_REQUIRED",
            )

        idempotency_key = _hex(
            {
                "mission_id": mission_id,
                "trace_id": envelope.trace_id,
                "span_id": envelope.span_id,
                "provider": contract.provider,
                "connector": contract.connector,
            },
            64,
        )
        response = dict(exporter(attrs, idempotency_key))
        transport_ok = response.get("transport_ok") is True
        provider_native = response.get("provider_native") is True
        semantic_ok = (
            transport_ok
            and provider_native
            and response.get("semantic_readback_verified") is True
            and bool(str(response.get("readback_ref") or ""))
        )
        operation_id = str(response.get("operation_id") or "")
        readback_ref = str(response.get("readback_ref") or "")
        proof_refs = tuple(
            sorted(
                {
                    *[str(x).strip() for x in authority.proof_refs if str(x).strip()],
                    *[str(x).strip() for x in (response.get("proof_refs") or ()) if str(x).strip()],
                }
            )
        )
        if semantic_ok:
            state = "OTEL_EXPORT_READBACK_VERIFIED"
            reason = "PROVIDER_NATIVE_TELEMETRY_EXPORT_AND_SEMANTIC_READBACK_VERIFIED"
        elif transport_ok:
            state = "HOLD_READBACK"
            reason = "TELEMETRY_TRANSPORT_SUCCEEDED_PROVIDER_SEMANTIC_READBACK_UNPROVEN"
        else:
            state = "EXPORT_FAILED"
            reason = str(response.get("reason") or "TELEMETRY_PROVIDER_TRANSPORT_FAILED")
        return MissionTraceReceipt(
            schema=SCHEMA,
            mission_id=mission_id,
            trace_id=envelope.trace_id,
            span_id=envelope.span_id,
            state=state,
            otel_attributes=attrs,
            provider=contract.provider,
            connector=contract.connector,
            operation_id=operation_id,
            readback_ref=readback_ref,
            proof_refs=proof_refs,
            transport_ok=transport_ok,
            provider_native=provider_native,
            semantic_readback_verified=semantic_ok,
            provider_effect_authorized=True,
            secret_value_recorded=False,
            reason=reason,
        )


__all__ = [
    "MissionTelemetryBridge",
    "MissionTraceReceipt",
    "TelemetryExportContract",
]
