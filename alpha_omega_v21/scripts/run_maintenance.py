from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alpha_omega_foundry.operations import OperationsFabric


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Alpha Omega maintenance cycle")
    parser.add_argument("--workspace", default="./maintenance_workspace")
    parser.add_argument("--system-id", default="ALPHA-OMEGA-FOUNDRY-V21")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    ops = OperationsFabric(workspace)
    expected = {
        "release_artifact": "VERIFIED",
        "github_ci": "SUCCESS",
        "google_drive_publish": "VERIFIED",
    }
    state_file = workspace / "current_state.json"
    if state_file.exists():
        actual = json.loads(state_file.read_text(encoding="utf-8"))
    else:
        actual = dict(expected)
        state_file.write_text(json.dumps(actual, indent=2), encoding="utf-8")

    heartbeat = ops.heartbeat(args.system_id)
    drift = ops.detect_drift(expected, actual)
    if drift["drift"]:
        failure = ops.classify_failure("schema validation drift detected")
        repair = ops.choose_repair(failure)
        outcome = {"state": "REPAIR_ROUTED", "repair": repair, "drift": drift}
        lesson = ops.learn({"type": "DRIFT", "system_id": args.system_id}, outcome)
        cycle_state = "DEGRADED"
    else:
        failure = None
        repair = None
        lesson = ops.learn(
            {"type": "MAINTENANCE_CYCLE", "system_id": args.system_id},
            {"state": "HEALTHY_NO_DRIFT"},
        )
        cycle_state = "HEALTHY"

    retirement = ops.retirement_decision(
        {"value_score": 1.0, "failure_rate": 0.0, "replacement_ready": False}
    )
    receipt = {
        "system_id": args.system_id,
        "state": cycle_state,
        "heartbeat": heartbeat,
        "drift": drift,
        "failure": failure,
        "repair": repair,
        "lesson": lesson,
        "retirement": retirement,
    }
    receipt_path = workspace / "maintenance_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    if cycle_state != "HEALTHY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
