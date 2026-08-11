from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from runtime import CompletionContract, Mission, ProviderCapability, SolRuntime, Workstream, digest, utc_now


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "runtime"
        rt = SolRuntime(root)
        rt.register_mission(Mission("omega-evidenceops", "Run durable autonomous work", ("state", "proof", "recovery")))
        rt.register_workstream(Workstream("design", "omega-evidenceops", "Compile mission and context", (), 100))
        rt.register_workstream(Workstream("execute", "omega-evidenceops", "Execute transaction", ("design",), 90))
        rt.register_provider(ProviderCapability("reference-worker", "transaction", True, True, True, True, True, "VERIFIED", utc_now()))

        admission = rt.admit_action("reference-worker", "transaction", consequential=True)
        assert admission["admitted"]
        rt.record_receipt("design", "build", "github-actions", {"pass": True})
        rt.record_receipt("design", "test", "github-actions", {"pass": True})
        rt.record_receipt("design", "readback", "reference-worker", {"pass": True})
        rt.record_receipt("design", "rollback", "reference-worker", {"pass": True})
        design = rt.evaluate_completion("design", CompletionContract(("build", "test", "readback", "rollback")))
        assert design["state"] == "VERIFIED"
        assert [w["workstream_id"] for w in rt.ready_workstreams()] == ["execute"]

        context = rt.compile_context("execute", [
            {"id": "fact-1", "missions": ["omega-evidenceops"], "verified": True, "priority": 100, "observed_at": utc_now()},
            {"id": "claim-1", "missions": ["omega-evidenceops"], "verified": False, "priority": 90, "observed_at": utc_now()},
        ])
        reasoning = rt.reasoning_budget(complexity=3, consequence=3, uncertainty=2, dependency_depth=2, contradiction_risk=2)
        lesson = rt.record_lesson("provider-registry-without-readback", "Require fresh provider-native readback", "receipt://reference")
        policy = rt.compile_lesson_to_policy(0, "PREFLIGHT_CHECK")
        reliability = rt.update_reliability("reference-transaction", True)
        control = rt.cybernetic_decision(error_rate=0.0, queue_age_seconds=0, proof_age_seconds=0, retries=0)
        checkpoint = rt.checkpoint("omega-evidenceops")
        assert rt.verify_event_chain()

        resumed = SolRuntime(root)
        recovery = {
            "event_chain_valid": resumed.verify_event_chain(),
            "checkpoint_present": checkpoint["checkpoint_id"] in resumed.state.checkpoints,
            "mission_present": "omega-evidenceops" in resumed.state.missions,
            "state_hash": digest(json.loads((root / "state.json").read_text())),
        }
        assert all(value for key, value in recovery.items() if key != "state_hash")

        receipt = {
            "programme": "SOL-6.1-OMEGA-EVIDENCEOPS-MODERNISATION",
            "provider": "github-actions-reference-runtime",
            "generated_at": utc_now(),
            "gates": {
                "durable_state": True,
                "event_chain": resumed.verify_event_chain(),
                "checkpoint_resume": recovery["checkpoint_present"],
                "context_compilation": len(context["verified_facts"]) == 1 and len(context["unknowns"]) == 1,
                "proof_completion": design["state"] == "VERIFIED",
                "provider_admission": admission["admitted"],
                "dependency_scheduler": [w["workstream_id"] for w in resumed.ready_workstreams()] == ["execute"],
                "reasoning_budget": reasoning["lane"] == "ESCALATED",
                "lesson_policy": policy["status"] == "ACTIVE",
                "confidence_calibration": reliability["attempts"] == 1,
                "cybernetic_control": control["action"] == "CONTINUE",
                "recovery": recovery["event_chain_valid"],
            },
            "truth_boundary": {
                "provider_neutral_kernel": True,
                "github_actions_execution": True,
                "cloud_run_live": False,
                "apps_script_live": False,
                "continuous_background_execution": False,
                "reason": "External providers require separate fresh authority and provider-native receipts."
            },
        }
        receipt["status"] = "REFERENCE_RUNTIME_VERIFIED" if all(receipt["gates"].values()) else "FAILED"
        receipt["sha256"] = digest(receipt)
        (output / "sol-61-runtime-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        shutil.copy2(root / "events.jsonl", output / "events.jsonl")
        shutil.copy2(root / "state.json", output / "state.json")
        return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
