from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    service: str
    operation: str
    started_at_ms: int
    duration_ms: float
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SLO:
    slo_id: str
    service: str
    metric: str
    target: float
    comparator: str  # LTE or GTE
    window_size: int = 20


@dataclass(frozen=True)
class ProofRecord:
    proof_id: str
    subject: str
    observed_at_epoch: int
    max_age_seconds: int
    evidence_hash: str


class ObservabilityFabric:
    """Provider-neutral observability and self-diagnosis reference fabric."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_file = self.root / "observability-events.jsonl"
        self.state_file = self.root / "observability-state.json"
        self.spans: list[dict[str, Any]] = []
        self.metrics: dict[str, list[float]] = {}
        self.slos: dict[str, dict[str, Any]] = {}
        self.proofs: dict[str, dict[str, Any]] = {}
        self.incidents: dict[str, dict[str, Any]] = {}
        self._replay()

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._events()
        event = {
            "event_id": f"obs-{len(rows)+1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": rows[-1]["event_hash"] if rows else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self._apply(event)
        self._persist()
        return event

    def record_span(self, span: TraceSpan) -> dict[str, Any]:
        if span.duration_ms < 0 or span.status not in {"OK", "ERROR"}:
            raise ValueError("invalid span")
        body = asdict(span)
        self._append("SPAN_RECORDED", body)
        return body

    def record_metric(self, name: str, value: float) -> dict[str, Any]:
        if not math.isfinite(value):
            raise ValueError("metric must be finite")
        body = {"name": name, "value": float(value)}
        self._append("METRIC_RECORDED", body)
        return body

    def register_slo(self, slo: SLO) -> dict[str, Any]:
        if slo.comparator not in {"LTE", "GTE"} or slo.window_size < 1:
            raise ValueError("invalid SLO")
        body = asdict(slo)
        self._append("SLO_REGISTERED", body)
        return body

    def evaluate_slo(self, slo_id: str) -> dict[str, Any]:
        slo = self.slos[slo_id]
        values = self.metrics.get(slo["metric"], [])[-int(slo["window_size"]):]
        if not values:
            return {"slo_id": slo_id, "status": "NO_DATA", "pass": False}
        observed = sum(values) / len(values)
        passed = observed <= slo["target"] if slo["comparator"] == "LTE" else observed >= slo["target"]
        return {"slo_id": slo_id, "observed": observed, "target": slo["target"], "status": "PASS" if passed else "BREACH", "pass": passed}

    def detect_anomaly(self, metric: str, current: float, baseline_size: int = 8, threshold_z: float = 2.5) -> dict[str, Any]:
        history = self.metrics.get(metric, [])[-baseline_size:]
        if len(history) < 3:
            return {"metric": metric, "anomaly": False, "reason": "INSUFFICIENT_BASELINE"}
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance)
        z = 0.0 if std == 0 and current == mean else float("inf") if std == 0 else abs(current - mean) / std
        return {"metric": metric, "anomaly": z >= threshold_z, "z_score": z, "baseline_mean": mean, "current": current}

    def correlate_trace_failures(self, trace_id: str) -> dict[str, Any]:
        spans = [s for s in self.spans if s["trace_id"] == trace_id]
        failures = [s for s in spans if s["status"] == "ERROR"]
        if not failures:
            return {"trace_id": trace_id, "root_candidate": None, "failed_spans": []}
        span_map = {s["span_id"]: s for s in spans}
        failure_ids = {s["span_id"] for s in failures}
        roots = [s for s in failures if s.get("parent_span_id") not in failure_ids]
        root = min(roots or failures, key=lambda s: s["started_at_ms"])
        descendants = [s["span_id"] for s in failures if s["span_id"] != root["span_id"]]
        return {"trace_id": trace_id, "root_candidate": root["span_id"], "service": root["service"], "failed_spans": sorted(failure_ids), "downstream_failures": sorted(descendants)}

    def register_proof(self, proof: ProofRecord) -> dict[str, Any]:
        if len(proof.evidence_hash) != 64:
            raise ValueError("invalid evidence hash")
        body = asdict(proof)
        self._append("PROOF_REGISTERED", body)
        return body

    def proof_freshness(self, proof_id: str, now_epoch: int) -> dict[str, Any]:
        proof = self.proofs[proof_id]
        age = now_epoch - int(proof["observed_at_epoch"])
        fresh = 0 <= age <= int(proof["max_age_seconds"])
        return {"proof_id": proof_id, "age_seconds": age, "fresh": fresh, "state": "FRESH" if fresh else "STALE"}

    def detect_false_completion(self, declared_state: str, required_proof_ids: list[str], now_epoch: int) -> dict[str, Any]:
        missing = sorted(pid for pid in required_proof_ids if pid not in self.proofs)
        stale = sorted(pid for pid in required_proof_ids if pid in self.proofs and not self.proof_freshness(pid, now_epoch)["fresh"])
        false_completion = declared_state in {"COMPLETE", "VERIFIED", "LIVE"} and bool(missing or stale)
        return {"declared_state": declared_state, "false_completion": false_completion, "missing_proofs": missing, "stale_proofs": stale}

    def form_incident(self, *, title: str, severity: str, signals: list[dict[str, Any]], correlation: dict[str, Any]) -> dict[str, Any]:
        if severity not in {"SEV1", "SEV2", "SEV3", "SEV4"}:
            raise ValueError("invalid severity")
        fingerprint = digest({"title": title, "severity": severity, "signals": signals, "correlation": correlation})
        existing = next((v for v in self.incidents.values() if v["fingerprint"] == fingerprint and v["status"] == "OPEN"), None)
        if existing:
            return existing
        incident = {
            "incident_id": f"inc-{len(self.incidents)+1:06d}",
            "title": title,
            "severity": severity,
            "status": "OPEN",
            "signals": signals,
            "correlation": correlation,
            "fingerprint": fingerprint,
            "formed_at": utc_now(),
        }
        self._append("INCIDENT_FORMED", incident)
        return incident

    def verify_chain(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event["previous_hash"] != previous:
                return False
            payload = {k: v for k, v in event.items() if k != "event_hash"}
            if digest(payload) != event["event_hash"]:
                return False
            previous = event["event_hash"]
        return True

    def _events(self) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        return [json.loads(line) for line in self.events_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _apply(self, event: dict[str, Any]) -> None:
        kind, payload = event["event_type"], event["payload"]
        if kind == "SPAN_RECORDED":
            self.spans.append(payload)
        elif kind == "METRIC_RECORDED":
            self.metrics.setdefault(payload["name"], []).append(payload["value"])
        elif kind == "SLO_REGISTERED":
            self.slos[payload["slo_id"]] = payload
        elif kind == "PROOF_REGISTERED":
            self.proofs[payload["proof_id"]] = payload
        elif kind == "INCIDENT_FORMED":
            self.incidents[payload["incident_id"]] = payload

    def _replay(self) -> None:
        self.spans, self.metrics, self.slos, self.proofs, self.incidents = [], {}, {}, {}, {}
        for event in self._events():
            self._apply(event)
        self._persist()

    def _persist(self) -> None:
        state = {"spans": self.spans, "metrics": self.metrics, "slos": self.slos, "proofs": self.proofs, "incidents": self.incidents}
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
