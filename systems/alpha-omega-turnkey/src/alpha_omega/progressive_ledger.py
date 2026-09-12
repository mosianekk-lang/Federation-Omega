from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .progressive_models import AccelerationProfile, _canonical_json


class HashLinkedLearningLedger:
    """Local append-only learning ledger used by the progressive runtime.

    The ledger stores compact execution metadata only. It is tamper-evident in
    its local hash domain, not administrator-authenticated and not a provider
    deployment receipt.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[dict[str, Any]] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._events.append(json.loads(line))
            if not self.verify():
                raise ValueError("learning ledger hash chain is invalid")

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)

    def append(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        previous_hash = self._events[-1]["event_hash"] if self._events else "GENESIS"
        body = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            "previous_hash": previous_hash,
            "payload": dict(payload),
        }
        event_hash = sha256(_canonical_json(body).encode("utf-8")).hexdigest()
        event = body | {"event_hash": event_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(event) + "\n")
        self._events.append(event)
        return event

    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for expected_sequence, event in enumerate(self._events, 1):
            body = {
                "sequence": event.get("sequence"),
                "event_type": event.get("event_type"),
                "previous_hash": event.get("previous_hash"),
                "payload": event.get("payload"),
            }
            if body["sequence"] != expected_sequence or body["previous_hash"] != previous_hash:
                return False
            expected_hash = sha256(_canonical_json(body).encode("utf-8")).hexdigest()
            if event.get("event_hash") != expected_hash:
                return False
            previous_hash = expected_hash
        return True

    def verified_reuse(self) -> dict[str, dict[str, Any]]:
        reusable: dict[str, dict[str, Any]] = {}
        for event in self._events:
            payload = event["payload"]
            if (
                event["event_type"] == "SUCCESS"
                and payload.get("stage") in {"CAPABILITY_VERIFY", "REGRESSION"}
                and payload.get("reusable_key")
                and payload.get("proof_refs")
            ):
                reusable[str(payload["reusable_key"])] = payload
        return reusable

    def acceleration_profile(
        self,
        reuse_hits: int = 0,
        work_units_avoided: int = 0,
    ) -> AccelerationProfile:
        baseline_stages = {"BUILD", "TEST", "RED_TEAM", "CAPABILITY_VERIFY"}
        reuse_stages = {"VERIFY_REUSE", "REGRESSION"}
        grouped: dict[tuple[str, str], dict[str, float]] = {}
        for event in self._events:
            if event["event_type"] != "SUCCESS":
                continue
            payload = event["payload"]
            cycle_id = str(payload.get("cycle_id") or "")
            reusable_key = str(payload.get("reusable_key") or "")
            stage = str(payload.get("stage") or "")
            duration = payload.get("duration_ms")
            if not cycle_id or not reusable_key or duration is None:
                continue
            grouped.setdefault((cycle_id, reusable_key), {})[stage] = float(duration)

        baseline_by_capability: dict[str, list[float]] = {}
        reuse_by_capability: dict[str, list[float]] = {}
        for (_cycle_id, reusable_key), stage_durations in grouped.items():
            if baseline_stages.issubset(stage_durations):
                baseline_by_capability.setdefault(reusable_key, []).append(
                    sum(stage_durations[stage] for stage in baseline_stages)
                )
            if reuse_stages.issubset(stage_durations):
                reuse_by_capability.setdefault(reusable_key, []).append(
                    sum(stage_durations[stage] for stage in reuse_stages)
                )

        comparable = sorted(set(baseline_by_capability) & set(reuse_by_capability))
        baseline = [value for key in comparable for value in baseline_by_capability[key]]
        reused = [value for key in comparable for value in reuse_by_capability[key]]
        ratio = None
        confidence = "UNMEASURED"
        if len(baseline) >= 2 and len(reused) >= 2:
            baseline_avg = sum(baseline) / len(baseline)
            reused_avg = sum(reused) / len(reused)
            if reused_avg > 0:
                ratio = round(baseline_avg / reused_avg, 4)
                confidence = (
                    "MEASURED_LOCAL_LOW_SAMPLE"
                    if min(len(baseline), len(reused)) < 5
                    else "MEASURED_LOCAL"
                )
        return AccelerationProfile(
            reusable_output_count=len(self.verified_reuse()),
            verified_reuse_hits=reuse_hits,
            work_units_avoided=work_units_avoided,
            measured_baseline_samples=len(baseline),
            measured_reuse_samples=len(reused),
            measured_speedup_ratio=ratio,
            confidence=confidence,
        )
