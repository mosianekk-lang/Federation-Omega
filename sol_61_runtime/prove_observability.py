from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from observability import ObservabilityFabric, ProofRecord, SLO, TraceSpan, digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    runtime = out / "observability-runtime"
    fabric = ObservabilityFabric(runtime)
    for span in [
        TraceSpan("trace-1", "gateway", None, "gateway", "dispatch", 1000, 10, "OK"),
        TraceSpan("trace-1", "provider", "gateway", "provider", "execute", 1010, 40, "ERROR"),
        TraceSpan("trace-1", "readback", "provider", "readback", "verify", 1050, 15, "ERROR"),
    ]:
        fabric.record_span(span)

    fabric.register_slo(SLO("slo-latency", "gateway", "latency_ms", 100, "LTE", 5))
    for value in [50, 54, 58, 55, 57]:
        fabric.record_metric("latency_ms", value)
    slo = fabric.evaluate_slo("slo-latency")
    anomaly = fabric.detect_anomaly("latency_ms", 180)
    correlation = fabric.correlate_trace_failures("trace-1")

    fabric.register_proof(ProofRecord("deploy-proof", "deployment", 100, 50, "a" * 64))
    freshness = fabric.proof_freshness("deploy-proof", 200)
    false_completion = fabric.detect_false_completion("VERIFIED", ["deploy-proof", "health-proof"], 200)
    incident = fabric.form_incident(
        title="Provider execution failed",
        severity="SEV2",
        signals=[anomaly, false_completion],
        correlation=correlation,
    )
    duplicate = fabric.form_incident(
        title="Provider execution failed",
        severity="SEV2",
        signals=[anomaly, false_completion],
        correlation=correlation,
    )
    restarted = ObservabilityFabric(runtime)

    gates = {
        "distributed_trace_capture": len(restarted.spans) == 3,
        "causal_trace_correlation": correlation["root_candidate"] == "provider" and correlation["downstream_failures"] == ["readback"],
        "slo_evaluation": slo["pass"],
        "anomaly_detection": anomaly["anomaly"],
        "proof_freshness_monitoring": not freshness["fresh"],
        "false_completion_detection": false_completion["false_completion"] and false_completion["missing_proofs"] == ["health-proof"],
        "automatic_incident_formation": incident["status"] == "OPEN",
        "incident_deduplication": duplicate["incident_id"] == incident["incident_id"],
        "restart_replay": restarted.verify_chain() and len(restarted.incidents) == 1,
    }
    receipt = {
        "status": "OBSERVABILITY_SELF_DIAGNOSIS_VERIFIED" if all(gates.values()) else "OBSERVABILITY_SELF_DIAGNOSIS_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "metrics": {"spans": len(restarted.spans), "incidents": len(restarted.incidents), "events": len(restarted._events())},
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_observability": True,
            "live_external_telemetry_stream": False,
            "live_incident_delivery": False,
            "continuous_background_monitoring": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-observability-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
