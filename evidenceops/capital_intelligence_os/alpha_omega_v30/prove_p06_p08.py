from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .capability_market import CapabilityRegistry, CapabilitySpec
from .chaos_factory import ChaosCase, ChaosFactory
from .sandbox_fleet import OperationalSandbox, ReceiptLedger, SandboxPolicy, SandboxTask


def build_proof(workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    ledger = ReceiptLedger(workspace / "sandbox_ledger.jsonl")
    policy = SandboxPolicy(
        timeout_seconds=0.5,
        max_output_bytes=1024,
        max_artifact_bytes=100_000,
        allowed_executables=(sys.executable,),
    )
    sandbox = OperationalSandbox(policy, ledger)

    operational = sandbox.run(
        SandboxTask(
            task_id="p06-operational-readback",
            command=(
                sys.executable,
                "-c",
                "from pathlib import Path; Path('result.json').write_text('{\\\"state\\\":\\\"healthy\\\"}', encoding='utf-8')",
            ),
            export_paths=("result.json",),
        )
    )
    if not all(
        operational[key]
        for key in (
            "execution_verified",
            "readback_verified",
            "health_verified",
            "persistence_verified",
            "rollback_verified",
        )
    ):
        raise SystemExit("P06 operational proof failed")

    registry = CapabilityRegistry(workspace / "capability_registry.jsonl")
    base = CapabilitySpec(
        capability_id="operational-sandbox-fleet",
        version="1.0.0",
        purpose="Execute authorised CI workloads in disposable process sandboxes with quotas and receipts",
        interfaces=("execute", "artifact-export", "receipt-ledger"),
        providers=("github-actions",),
        fitness={"correctness": 1.0, "reliability": 0.95, "cost_efficiency": 0.9},
        proof_refs=(operational["ledger_entry_hash"], operational["result_hash"]),
    )
    base_record = registry.register(base)
    evolved = CapabilitySpec(
        capability_id="operational-sandbox-fleet",
        version="1.1.0",
        purpose="Add deterministic chaos containment evidence to the operational sandbox fleet",
        interfaces=("execute", "artifact-export", "receipt-ledger", "chaos-test"),
        providers=("github-actions",),
        fitness={"correctness": 1.0, "reliability": 1.0, "cost_efficiency": 0.9},
        parent_fingerprint=base_record["fingerprint"],
        proof_refs=(operational["ledger_entry_hash"],),
    )
    evolved_record = registry.register(evolved)
    selected = registry.resolve(
        required_interfaces=("execute", "chaos-test"),
        provider="github-actions",
    )
    lineage = registry.lineage(evolved_record["fingerprint"])
    if selected is None or selected["fingerprint"] != evolved_record["fingerprint"] or len(lineage) != 2:
        raise SystemExit("P07 registry selection or lineage proof failed")

    chaos = ChaosFactory(sandbox).run(
        [
            ChaosCase(
                name="nonzero-exit-contained",
                task=SandboxTask(
                    task_id="chaos-nonzero",
                    command=(sys.executable, "-c", "import sys; sys.exit(7)"),
                ),
                expected_status="NONZERO_EXIT",
            ),
            ChaosCase(
                name="timeout-contained",
                task=SandboxTask(
                    task_id="chaos-timeout",
                    command=(sys.executable, "-c", "import time; time.sleep(2)"),
                ),
                expected_status="TIMEOUT",
            ),
            ChaosCase(
                name="output-quota-contained",
                task=SandboxTask(
                    task_id="chaos-output",
                    command=(sys.executable, "-c", "print('x' * 5000)"),
                ),
                expected_status="OUTPUT_LIMIT",
            ),
        ]
    )
    if not chaos["valid"]:
        raise SystemExit("P08 chaos containment proof failed")

    ledger_state = ledger.verify()
    registry_state = registry.verify()
    if not ledger_state["valid"] or not registry_state["valid"]:
        raise SystemExit("persistence verification failed")

    receipt = {
        "programme_id": "AO-V30-SELF-VERIFYING-INSTITUTION",
        "provider": "github-actions",
        "provider_boundary": "process-level disposable CI sandbox; no VM, container, kernel or Cloud Run claim",
        "phases": {
            "P06": {
                "status": "OPERATIONAL_VERIFIED_GITHUB_ACTIONS",
                "execution": operational["execution_verified"],
                "readback": operational["readback_verified"],
                "health": operational["health_verified"],
                "persistence": operational["persistence_verified"],
                "rollback": operational["rollback_verified"],
                "receipt": operational["ledger_entry_hash"],
            },
            "P07": {
                "status": "OPERATIONAL_VERIFIED_GITHUB_ACTIONS",
                "registry": registry_state,
                "selected_capability": selected["fingerprint"],
                "lineage": lineage,
            },
            "P08": {
                "status": "OPERATIONAL_VERIFIED_GITHUB_ACTIONS",
                "chaos": chaos,
            },
        },
        "ledger": ledger_state,
        "registry": registry_state,
    }
    (workspace / "chaos_report.json").write_text(json.dumps(chaos, indent=2, sort_keys=True), encoding="utf-8")
    (workspace / "p06_p08_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("p06_p08_workspace"))
    args = parser.parse_args()
    print(json.dumps(build_proof(args.workspace), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
