from __future__ import annotations

"""Mission proof passport for Bubbles Ω.

The passport projects one mission's evidence from the existing durable mission
ledger. It does not create a second proof store or grant provider authority.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1


SCHEMA = "BUBBLES-OMEGA-MISSION-PROOF-PASSPORT-V1"
_EVENT_SCHEMA = "BUBBLES_OMEGA_PROOF_EVENT_V1"


class PassportEventKind(str, Enum):
    SOURCE = "SOURCE"
    AUTHORITY = "AUTHORITY"
    PROVIDER_DISPATCH = "PROVIDER_DISPATCH"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    RECOVERY = "RECOVERY"
    EVALUATION = "EVALUATION"
    VALUE = "VALUE"
    FINAL = "FINAL"


@dataclass(frozen=True, slots=True)
class PassportSnapshot:
    schema: str
    mission_id: str
    event_count: int
    event_refs: tuple[str, ...]
    proof_refs: tuple[str, ...]
    authority_resolved: bool
    semantic_readback_verified: bool
    final_verified: bool
    proof_complete: bool
    hold_readback: bool
    total_cost_microunits: int
    total_latency_ms: float
    external_effect_count: int
    ledger_verified: bool
    ledger_head_hash: str | None
    provider_effect_authorized: bool = False
    owner_value_proven: bool = False
    secret_value_recorded: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_refs"] = list(self.event_refs)
        payload["proof_refs"] = list(self.proof_refs)
        payload["truth_boundary"] = {
            "proof_complete_is_owner_value": False,
            "passport_grants_provider_authority": False,
            "passport_is_second_memory_root": False,
            "provider_effect_authority_is_inherited": False,
        }
        return payload


class MissionProofPassport:
    EVENT_TYPE = "BUBBLES_OMEGA_PROOF_EVENT_V1"

    def __init__(self, runtime: DurableMissionRuntimeV1) -> None:
        self.runtime = runtime

    @staticmethod
    def _safe_refs(values: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))

    def record(
        self,
        mission_id: str,
        kind: PassportEventKind,
        *,
        state: str,
        proof_refs: Iterable[str] = (),
        data: Mapping[str, Any] | None = None,
        idempotency_key: str = "",
    ) -> str:
        if not str(mission_id).strip():
            raise ValueError("PASSPORT_MISSION_ID_REQUIRED")
        if not str(state).strip():
            raise ValueError("PASSPORT_STATE_REQUIRED")
        payload = {
            "schema": _EVENT_SCHEMA,
            "kind": PassportEventKind(kind).value,
            "state": str(state).strip().upper(),
            "proof_refs": list(self._safe_refs(proof_refs)),
            "data": dict(data or {}),
            "secret_value_recorded": False,
        }
        event = self.runtime.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT_TYPE,
            payload=payload,
            idempotency_key=idempotency_key or f"{kind.value}:{state}:{payload['proof_refs']}",
        )
        return event.event_id

    def events(self, mission_id: str) -> tuple[Any, ...]:
        return tuple(
            event
            for event in self.runtime.ledger.events(mission_id)
            if event.event_type == self.EVENT_TYPE
            and event.payload.get("schema") == _EVENT_SCHEMA
        )

    def snapshot(self, mission_id: str) -> PassportSnapshot:
        self.runtime.project(mission_id)
        events = self.events(mission_id)
        proof_refs: set[str] = set()
        semantic_readback_verified = False
        final_verified = False
        hold_readback = False
        total_cost = 0
        total_latency = 0.0
        external_effects = 0
        provider_effect_authorized = False

        bound = self.runtime._bound_event(mission_id)
        mission_ir = dict(bound.payload["mission_ir"])
        effect_class = str(mission_ir.get("effect_class") or "NO_EFFECT")
        authority_resolved = effect_class in {"NO_EFFECT", "READ_ONLY"}

        refs: list[str] = []
        for event in events:
            refs.append(event.event_id)
            payload = dict(event.payload)
            proof_refs.update(str(item) for item in payload.get("proof_refs", ()) if str(item).strip())
            kind = str(payload.get("kind") or "")
            state = str(payload.get("state") or "")
            data = dict(payload.get("data") or {})
            if kind == PassportEventKind.AUTHORITY.value and state in {"RESOLVED", "NOT_REQUIRED"}:
                authority_resolved = True
                provider_effect_authorized = data.get("provider_effect_authorized") is True
            if kind == PassportEventKind.SEMANTIC_READBACK.value and state in {
                "PROVIDER_SEMANTIC_READBACK_VERIFIED",
                "VERIFIED",
            }:
                semantic_readback_verified = True
            if kind == PassportEventKind.PROVIDER_DISPATCH.value and state == "HOLD_READBACK":
                hold_readback = True
            if kind == PassportEventKind.FINAL.value and state == "VERIFIED":
                final_verified = True
            cost = data.get("cost_microunits")
            latency = data.get("latency_ms")
            if isinstance(cost, int) and cost >= 0:
                total_cost += cost
            if isinstance(latency, (int, float)) and latency >= 0:
                total_latency += float(latency)
            if data.get("effect_attempted") is True:
                external_effects += 1

        ledger_state = self.runtime.ledger.verify()
        proof_complete = (
            authority_resolved
            and semantic_readback_verified
            and final_verified
            and not hold_readback
        )
        return PassportSnapshot(
            schema=SCHEMA,
            mission_id=mission_id,
            event_count=len(events),
            event_refs=tuple(refs),
            proof_refs=tuple(sorted(proof_refs)),
            authority_resolved=authority_resolved,
            semantic_readback_verified=semantic_readback_verified,
            final_verified=final_verified,
            proof_complete=proof_complete,
            hold_readback=hold_readback,
            total_cost_microunits=total_cost,
            total_latency_ms=round(total_latency, 6),
            external_effect_count=external_effects,
            ledger_verified=ledger_state.get("state") == "VERIFIED",
            ledger_head_hash=ledger_state.get("head_hash"),
            provider_effect_authorized=provider_effect_authorized,
            owner_value_proven=False,
            secret_value_recorded=False,
        )


__all__ = [
    "MissionProofPassport",
    "PassportEventKind",
    "PassportSnapshot",
]
