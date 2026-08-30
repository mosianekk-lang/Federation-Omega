from __future__ import annotations

"""Read-only C03 capability registry over Living State and KDV projections."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

from .closure_matrix_v1 import ACTIONABLE_STATES, HELD_STATES, validate_matrix


SCHEMA = "CFBE-OMEGA-CAPABILITY-REGISTRY-V1"
RECEIPT_SCHEMA = "CFBE-OMEGA-CAPABILITY-REGISTRY-QUERY-RECEIPT-V1"
PROOF_RANK = {
    "UNKNOWN": 0,
    "DESIGN_ONLY": 1,
    "SOURCE_PRESENT": 2,
    "DETERMINISTIC_TESTED": 3,
    "SHADOW_OR_LOCAL_RUNTIME": 4,
    "PROVIDER_VERIFIED": 5,
    "PRODUCTION_VERIFIED": 6,
    "OUTCOME_VERIFIED": 7,
    "ECONOMICALLY_VERIFIED": 8,
}


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    capability_id: str
    capability: str
    rail: str
    closure_state: str
    maturity: str
    source_kind: str
    source_ref: str
    proof_ref: str
    observed_at: str
    ttl_seconds: int
    authority_ceiling: str
    cost_units: float
    latency_ms: float
    failure_domains: tuple[str, ...]
    dependencies: tuple[str, ...]
    next_action: str
    fingerprint: str

    @property
    def proof_rank(self) -> int:
        return PROOF_RANK.get(self.maturity, 0)

    def fresh_at(self, now: str) -> bool:
        age = (_time(now) - _time(self.observed_at)).total_seconds()
        return 0 <= age <= self.ttl_seconds

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RegistryQueryReceipt:
    schema: str
    registry_sha256: str
    selected: tuple[CapabilityRecord, ...]
    held: Mapping[str, tuple[str, ...]]
    selected_per_rail: Mapping[str, int]
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "registry_sha256": self.registry_sha256,
            "selected": [record.to_dict() for record in self.selected],
            "held": {key: list(value) for key, value in sorted(self.held.items())},
            "selected_per_rail": dict(self.selected_per_rail),
            "provider_effect_authorized": self.provider_effect_authorized,
            "financial_effect_authorized": self.financial_effect_authorized,
            "receipt_sha256": self.receipt_sha256,
        }


def _record(raw: Mapping[str, Any], *, source_kind: str, source_ref: str, observed_at: str, ttl_seconds: int) -> CapabilityRecord:
    capability_id = str(raw.get("id") or raw.get("capability_id") or raw.get("node_id") or "").strip()
    capability = str(raw.get("capability") or raw.get("system") or raw.get("name") or capability_id).strip()
    if not capability_id or not capability:
        raise ValueError("CFBE_CAPABILITY_REGISTRY_ID_AND_NAME_REQUIRED")
    maturity = str(raw.get("maturity") or raw.get("proof_maturity") or "UNKNOWN")
    if maturity not in PROOF_RANK:
        raise ValueError(f"CFBE_CAPABILITY_REGISTRY_UNKNOWN_MATURITY:{capability_id}")
    ttl = int(raw.get("ttl_seconds") or ttl_seconds)
    if ttl < 1:
        raise ValueError(f"CFBE_CAPABILITY_REGISTRY_TTL_REQUIRED:{capability_id}")
    body = {
        "capability_id": capability_id,
        "capability": capability,
        "rail": str(raw.get("rail") or "UNASSIGNED"),
        "closure_state": str(raw.get("closure_state") or raw.get("state") or "HOLD"),
        "maturity": maturity,
        "source_kind": source_kind,
        "source_ref": str(raw.get("source_ref") or source_ref),
        "proof_ref": str(raw.get("proof_ref") or ""),
        "observed_at": str(raw.get("observed_at") or observed_at),
        "ttl_seconds": ttl,
        "authority_ceiling": str(raw.get("authority_ceiling") or "A1"),
        "cost_units": float(raw.get("cost_units") or 0),
        "latency_ms": float(raw.get("latency_ms") or 0),
        "failure_domains": _clean(raw.get("failure_domains") or ()),
        "dependencies": _clean(raw.get("dependencies") or ()),
        "next_action": str(raw.get("next_action") or ""),
    }
    _time(body["observed_at"])
    return CapabilityRecord(**body, fingerprint=_digest(body))


def normalize_kdv_projection(
    rows: Iterable[Mapping[str, Any]], *, source_ref: str, observed_at: str, ttl_seconds: int = 86400
) -> tuple[CapabilityRecord, ...]:
    return tuple(
        _record(row, source_kind="KDV_PROJECTION", source_ref=source_ref, observed_at=observed_at, ttl_seconds=ttl_seconds)
        for row in rows
    )


def normalize_living_state_events(events: Iterable[Mapping[str, Any]]) -> tuple[CapabilityRecord, ...]:
    records: list[CapabilityRecord] = []
    for event in events:
        if str(event.get("event_type")) != "NODE_OBSERVED":
            continue
        node = dict(((event.get("payload") or {}).get("node") or {}))
        kind = str(node.get("kind") or "")
        if "CAPABILITY" not in kind.upper():
            continue
        provenance = dict(node.get("provenance") or {})
        attributes = dict(node.get("attributes") or node.get("metadata") or {})
        raw = {
            **attributes,
            "id": node.get("node_id"),
            "capability": node.get("name") or attributes.get("capability"),
            "state": node.get("state"),
            "maturity": provenance.get("proof_maturity") or attributes.get("maturity"),
            "proof_ref": provenance.get("proof_ref"),
            "source_ref": provenance.get("source_ref"),
            "observed_at": provenance.get("observed_at"),
            "ttl_seconds": provenance.get("ttl_seconds"),
            "authority_ceiling": provenance.get("authority_ceiling"),
        }
        records.append(
            _record(
                raw,
                source_kind="LIVING_STATE",
                source_ref=str(provenance.get("source_ref") or "living-state"),
                observed_at=str(provenance.get("observed_at") or ""),
                ttl_seconds=int(provenance.get("ttl_seconds") or 1),
            )
        )
    return tuple(records)


class CapabilityRegistry:
    def __init__(self, records: Sequence[CapabilityRecord]):
        grouped: dict[str, list[CapabilityRecord]] = {}
        for record in records:
            grouped.setdefault(record.capability_id, []).append(record)
        self._records = {key: tuple(values) for key, values in grouped.items()}

    @property
    def registry_sha256(self) -> str:
        return _digest({key: [record.to_dict() for record in values] for key, values in sorted(self._records.items())})

    def resolve(self, capability_id: str, *, now: str) -> tuple[CapabilityRecord | None, tuple[str, ...]]:
        candidates = self._records.get(capability_id, ())
        fresh = [record for record in candidates if record.fresh_at(now)]
        if not fresh:
            return None, ("MISSING_CAPABILITY_OBSERVATION",) if not candidates else ("STALE_CAPABILITY_OBSERVATION",)
        states = {(record.closure_state, record.maturity) for record in fresh}
        if len(states) > 1:
            return None, ("SPLIT_BRAIN_CAPABILITY_OBSERVATION",)
        best = max(fresh, key=lambda record: (record.proof_rank, record.observed_at, record.source_kind, record.fingerprint))
        return best, ()

    def query_closure_wave(
        self, matrix: Mapping[str, Any], *, now: str, active_ids: Iterable[str] = ()
    ) -> RegistryQueryReceipt:
        validate_matrix(matrix)
        active = set(str(item) for item in active_ids)
        rows = list(matrix["rows"])
        priority = {item: index for index, item in enumerate(matrix.get("highest_leverage_red_cells") or [])}
        rows.sort(key=lambda row: (priority.get(str(row["id"]), 10_000), str(row["rail"]), str(row["id"])))
        limit = int(matrix["scheduler_policy"]["wip_limit_per_rail"])
        counts = {rail: 0 for rail in matrix["rails"]}
        selected: list[CapabilityRecord] = []
        held: dict[str, tuple[str, ...]] = {}
        for row in rows:
            cid = str(row["id"])
            blockers: list[str] = []
            record, resolution = self.resolve(cid, now=now)
            blockers.extend(resolution)
            if cid in active:
                blockers.append("ALREADY_ACTIVE")
            if str(row["closure_state"]) in HELD_STATES:
                blockers.append(str(row["closure_state"]))
            if str(row["closure_state"]) not in ACTIONABLE_STATES:
                blockers.append("NOT_ACTIONABLE")
            rail = str(row["rail"])
            if counts[rail] >= limit:
                blockers.append("RAIL_WIP_LIMIT")
            for dependency in row.get("dependencies") or ():
                dependency_record, dependency_blockers = self.resolve(str(dependency), now=now)
                if dependency_record is None:
                    blockers.append(f"DEPENDENCY_UNREADY:{dependency}:{dependency_blockers[0]}")
            if blockers or record is None:
                held[cid] = _clean(blockers)
                continue
            selected.append(record)
            counts[rail] += 1
        body = {
            "schema": RECEIPT_SCHEMA,
            "registry_sha256": self.registry_sha256,
            "selected": [record.to_dict() for record in selected],
            "held": {key: list(value) for key, value in sorted(held.items())},
            "selected_per_rail": counts,
            "provider_effect_authorized": False,
            "financial_effect_authorized": False,
        }
        return RegistryQueryReceipt(
            schema=RECEIPT_SCHEMA,
            registry_sha256=self.registry_sha256,
            selected=tuple(selected),
            held=held,
            selected_per_rail=counts,
            provider_effect_authorized=False,
            financial_effect_authorized=False,
            receipt_sha256=_digest(body),
        )


__all__ = [
    "SCHEMA",
    "CapabilityRecord",
    "CapabilityRegistry",
    "RegistryQueryReceipt",
    "normalize_kdv_projection",
    "normalize_living_state_events",
]
