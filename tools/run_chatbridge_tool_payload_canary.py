from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from federation.chatbridge_tool_payload_ingress import ChatBridgeToolPayloadIngress


def _payload() -> str:
    lines = [f"INFO worker={index:04d} payload={'x' * 80}" for index in range(1800)]
    lines[900] = (
        "ERROR provider request failed returncode=17 "
        "Authorization: Bearer CANARYSECRET0123456789"
    )
    lines[-2] = "INFO cleanup complete"
    lines[-1] = "conclusion=failure exit code 17"
    return "\n".join(lines)


def run() -> dict[str, object]:
    raw = _payload()
    result = ChatBridgeToolPayloadIngress().ingest(
        tool_name="github.workflow_job_log.synthetic",
        payload=raw,
        content_kind="workflow_log",
        contains_sensitive_hint=True,
    )
    receipt = result.receipt.to_dict()
    failure_marker = "ERROR provider request failed returncode=17"
    receipt.update(
        {
            "canary_schema": "BUBBLES-CHATBRIDGE-PAYLOAD-INGRESS-CANARY-1",
            "failure_signal_preserved": failure_marker in result.bounded_payload,
            "secret_absent": "CANARYSECRET0123456789" not in result.bounded_payload,
            "manual_interventions": 0,
            "value_gate": {
                "minimum_reduction_percent": 90.0,
                "maximum_processing_ms": 500.0,
                "failure_signal_required": True,
                "secret_absence_required": True,
            },
        }
    )
    receipt["value_gate_pass"] = bool(
        receipt["reduction_percent"] >= 90.0
        and receipt["processing_ms"] <= 500.0
        and receipt["failure_signal_preserved"] is True
        and receipt["secret_absent"] is True
        and receipt["external_effects"] == 0
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Effect-free Bubbles/ChatBridge payload-ingress canary")
    parser.add_argument("--output", default="bubbles-tool-payload-canary/receipt.json")
    args = parser.parse_args()
    receipt = run()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "state": receipt["state"],
                "raw_chars": receipt["raw_chars"],
                "bounded_chars": receipt["bounded_chars"],
                "reduction_percent": receipt["reduction_percent"],
                "processing_ms": receipt["processing_ms"],
                "failure_signal_preserved": receipt["failure_signal_preserved"],
                "secret_absent": receipt["secret_absent"],
                "value_gate_pass": receipt["value_gate_pass"],
                "receipt_sha256": receipt["receipt_sha256"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if receipt["value_gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
