from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import (
    MissionResultIdentity,
    MissionResultLookupReceipt,
    lookup_mission_result,
    record_mission_result,
)
from federation.bubbles_frontier_hyperperformance import DeterministicResultCache

_SCHEMA = "FEDERATION-MISSION-RESULT-INDEX-V1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DurableResultRecord:
    cache_key: str
    identity: dict[str, object]
    result_ref: str
    result_sha256: str
    proof_refs: tuple[str, ...]
    recorded_at: str
    previous_hash: str
    record_hash: str

    def payload_without_hash(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "cache_key": self.cache_key,
            "identity": self.identity,
            "result_ref": self.result_ref,
            "result_sha256": self.result_sha256,
            "proof_refs": list(self.proof_refs),
            "recorded_at": self.recorded_at,
            "previous_hash": self.previous_hash,
        }


class DurableMissionResultIndex:
    """Restart-safe append-only metadata index for deterministic Result Fabric entries.

    This does not persist result payloads and grants no execution/provider authority.
    Exact Result Fabric identity, proof references and freshness remain controlling.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, DurableResultRecord] = {}
        self._tail_hash = ""
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        previous = ""
        for line_number, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"RESULT_INDEX_INVALID_JSON:{line_number}") from exc
            if payload.get("schema") != _SCHEMA:
                raise ValueError(f"RESULT_INDEX_SCHEMA_MISMATCH:{line_number}")
            claimed = str(payload.get("record_hash", ""))
            body = dict(payload)
            body.pop("record_hash", None)
            if str(body.get("previous_hash", "")) != previous:
                raise ValueError(f"RESULT_INDEX_CHAIN_BROKEN:{line_number}")
            actual = _digest(body)
            if claimed != actual:
                raise ValueError(f"RESULT_INDEX_HASH_MISMATCH:{line_number}")
            record = DurableResultRecord(
                cache_key=str(body["cache_key"]),
                identity=dict(body["identity"]),
                result_ref=str(body["result_ref"]),
                result_sha256=str(body["result_sha256"]),
                proof_refs=tuple(str(item) for item in body["proof_refs"]),
                recorded_at=str(body["recorded_at"]),
                previous_hash=str(body["previous_hash"]),
                record_hash=claimed,
            )
            existing = self._records.get(record.cache_key)
            if existing is not None and existing != record:
                raise ValueError(f"RESULT_INDEX_CONFLICTING_CACHE_KEY:{line_number}")
            self._records[record.cache_key] = record
            previous = claimed
        self._tail_hash = previous

    def verify(self) -> dict[str, object]:
        # Re-open through the same fail-closed parser so disk tampering is detected.
        probe = object.__new__(DurableMissionResultIndex)
        probe.path = self.path
        probe._records = {}
        probe._tail_hash = ""
        probe._load()
        return {
            "schema": _SCHEMA,
            "valid": True,
            "record_count": len(probe._records),
            "tail_hash": probe._tail_hash,
            "external_effects": 0,
            "provider_effect_authorized": False,
        }

    def lookup(self, identity: MissionResultIdentity, *, now: str) -> MissionResultLookupReceipt:
        record = self._records.get(identity.cache_key)
        if record is None:
            cache = DeterministicResultCache()
            return lookup_mission_result(cache, identity, now=now)
        if record.identity != identity.canonical_mapping():
            raise ValueError("RESULT_INDEX_IDENTITY_MISMATCH")
        cache = DeterministicResultCache()
        record_mission_result(
            cache,
            identity,
            result_ref=record.result_ref,
            result_sha256=record.result_sha256,
            proof_refs=record.proof_refs,
            recorded_at=record.recorded_at,
            now=now,
        )
        return lookup_mission_result(cache, identity, now=now)

    def record(
        self,
        identity: MissionResultIdentity,
        *,
        result_ref: str,
        result_sha256: str,
        proof_refs: tuple[str, ...],
        recorded_at: str,
        now: str,
    ) -> MissionResultLookupReceipt:
        cache = DeterministicResultCache()
        receipt = record_mission_result(
            cache,
            identity,
            result_ref=result_ref,
            result_sha256=result_sha256,
            proof_refs=proof_refs,
            recorded_at=recorded_at,
            now=now,
        )
        refs = tuple(sorted({item.strip() for item in proof_refs if item.strip()}))
        body = {
            "schema": _SCHEMA,
            "cache_key": identity.cache_key,
            "identity": identity.canonical_mapping(),
            "result_ref": receipt.result_ref,
            "result_sha256": receipt.result_sha256,
            "proof_refs": list(refs),
            "recorded_at": recorded_at,
            "previous_hash": self._tail_hash,
        }
        record_hash = _digest(body)
        candidate = DurableResultRecord(
            cache_key=identity.cache_key,
            identity=identity.canonical_mapping(),
            result_ref=receipt.result_ref,
            result_sha256=receipt.result_sha256,
            proof_refs=refs,
            recorded_at=recorded_at,
            previous_hash=self._tail_hash,
            record_hash=record_hash,
        )
        existing = self._records.get(identity.cache_key)
        if existing is not None:
            equivalent = (
                existing.identity == candidate.identity
                and existing.result_ref == candidate.result_ref
                and existing.result_sha256 == candidate.result_sha256
                and existing.proof_refs == candidate.proof_refs
                and existing.recorded_at == candidate.recorded_at
            )
            if not equivalent:
                raise ValueError("RESULT_INDEX_CONFLICTING_CACHE_KEY")
            return lookup_mission_result(cache, identity, now=now)
        payload = dict(body)
        payload["record_hash"] = record_hash
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(_canonical(payload) + "\n")
            stream.flush()
        self._records[identity.cache_key] = candidate
        self._tail_hash = record_hash
        return receipt
