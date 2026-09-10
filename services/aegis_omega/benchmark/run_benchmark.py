from __future__ import annotations
import json, random, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aegis_omega.schemas import SecurityEvent, EventClass
from aegis_omega.fusion import assess_events

random.seed(7)

def make_event(i, risky=False):
    classes = list(EventClass)
    return SecurityEvent(
        event_id=f"evt-{i}", device_id=f"device-{i%100}", event_class=classes[i % len(classes)],
        severity=(random.uniform(.70, .99) if risky else random.uniform(.01, .25)),
        confidence=random.uniform(.75, .99), source=f"sensor-{i%4}", attributes={"feature": random.random()}, consent=True
    )

def main():
    benign = [make_event(i, False) for i in range(1200)]
    risky = [make_event(2000+i, True) for i in range(300)]
    t0=time.perf_counter()
    # Benchmark isolated event throughput; multi-signal cases are measured separately below.
    results=[assess_events([e]) for e in benign+risky]
    elapsed=time.perf_counter()-t0
    throughput=len(results)/max(elapsed, 1e-9)
    # A synthetic correlated-case sanity check.
    correlated = assess_events([
        SecurityEvent(event_id="cor1", device_id="device-cor", event_class=EventClass.DEVICE_INTEGRITY, severity=.95, confidence=.95, source="integrity", consent=True),
        SecurityEvent(event_id="cor2", device_id="device-cor", event_class=EventClass.FORENSIC_ARTIFACT, severity=.92, confidence=.94, source="forensics", consent=True),
        SecurityEvent(event_id="cor3", device_id="device-cor", event_class=EventClass.NETWORK_RISK, severity=.88, confidence=.90, source="network", consent=True),
        SecurityEvent(event_id="cor4", device_id="device-cor", event_class=EventClass.IDENTITY_RISK, severity=.83, confidence=.88, source="identity", consent=True),
    ])
    out={
        "dataset": "synthetic-defensive-metadata-v1",
        "events": len(results),
        "elapsed_seconds": round(elapsed, 6),
        "events_per_second": round(throughput, 2),
        "median_single_event_risk": round(statistics.median(r.risk_score for r in results), 6),
        "correlated_case_risk": correlated.risk_score,
        "correlated_case_disposition": correlated.disposition,
        "claim_scope": "Local synthetic reference benchmark only; not evidence of 10x market superiority."
    }
    (Path(__file__).parent / "results.json").write_text(json.dumps(out, indent=2)+"\n")
    print(json.dumps(out, indent=2))

if __name__ == "__main__": main()
