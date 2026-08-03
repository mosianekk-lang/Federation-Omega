from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .sandbox_fleet import ReceiptLedger


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SystemObservation:
    system: str
    entity_id: str
    intended: Mapping[str, Any]
    declared: Mapping[str, Any]
    observed: Mapping[str, Any]
    proven: Mapping[str, Any]
    outcome: Mapping[str, Any]
    evidence_ref: str
    observed_at: str

    def validate(self) -> None:
        if not self.system or not self.entity_id or not self.evidence_ref:
            raise ValueError("system, entity_id and evidence_ref are required")
        _parse_time(self.observed_at)


class CrossSystemReconciler:
    """Reconciles truth states inside and across provider surfaces."""

    def __init__(self, ledger_path: str | Path):
        self.ledger = ReceiptLedger(ledger_path)

    def reconcile(
        self,
        observations: Iterable[SystemObservation],
        *,
        now: str,
        max_age_seconds: int = 3600,
    ) -> dict[str, Any]:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        now_dt = _parse_time(now)
        records = list(observations)
        if not records:
            raise ValueError("at least one observation is required")

        item_results: list[dict[str, Any]] = []
        grouped: dict[str, list[SystemObservation]] = {}
        for observation in records:
            observation.validate()
            grouped.setdefault(observation.entity_id, []).append(observation)
            age = max(0.0, (now_dt - _parse_time(observation.observed_at)).total_seconds())
            gaps = {
                "intent_gap": _canonical(observation.intended) != _canonical(observation.observed),
                "declaration_gap": _canonical(observation.declared) != _canonical(observation.observed),
                "proof_gap": _canonical(observation.observed) != _canonical(observation.proven),
                "outcome_gap": _canonical(observation.proven) != _canonical(observation.outcome),
                "evidence_missing": not bool(observation.evidence_ref.strip()),
                "stale": age > max_age_seconds,
            }
            item_results.append(
                {
                    "system": observation.system,
                    "entity_id": observation.entity_id,
                    "gaps": gaps,
                    "age_seconds": age,
                    "evidence_ref": observation.evidence_ref,
                    "observation_hash": _digest(asdict(observation)),
                }
            )

        cross_system_gaps: list[dict[str, Any]] = []
        for entity_id, group in sorted(grouped.items()):
            proven_states = {_canonical(item.proven) for item in group}
            outcome_states = {_canonical(item.outcome) for item in group}
            if len(proven_states) > 1 or len(outcome_states) > 1:
                cross_system_gaps.append(
                    {
                        "entity_id": entity_id,
                        "systems": sorted(item.system for item in group),
                        "proven_conflict": len(proven_states) > 1,
                        "outcome_conflict": len(outcome_states) > 1,
                    }
                )

        local_gap_count = sum(
            bool(value)
            for item in item_results
            for value in item["gaps"].values()
        )
        result = {
            "valid": local_gap_count == 0 and not cross_system_gaps,
            "observations": item_results,
            "cross_system_gaps": cross_system_gaps,
            "local_gap_count": local_gap_count,
            "observation_count": len(records),
            "provider_writeback": "REQUIRED_FOR_LIVE_OPERATION",
        }
        result["result_hash"] = _digest(result)
        result["ledger_entry"] = self.ledger.append(result)["entry_hash"]
        result["persistence_verified"] = self.ledger.verify()["valid"]
        return result
