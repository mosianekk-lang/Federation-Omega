from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from provider_bridge import ExecutionRequest, InMemoryAdapter, ProviderCapability, ProviderExecutionBridge, digest
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    bridge = ProviderExecutionBridge()
    bridge.register_adapter("github", InMemoryAdapter())
    bridge.register_capability(ProviderCapability("github", "write", True, True, True, "VERIFIED"))
    bridge.register_capability(ProviderCapability("apps_script", "source_write", True, True, True, "OWNER_CONSENT_REQUIRED"))
    bridge.register_capability(ProviderCapability("gmail", "send", True, True, False, "VERIFIED", owner_reserved=True))

    request = ExecutionRequest("req-proof", "github", "write", {"path": "proof"}, "idem-proof", {"active": True})
    first = bridge.execute(request)
    second = bridge.execute(request)
    rollback = bridge.rollback(first)
    apps_script = bridge.admit(ExecutionRequest("req-apps", "apps_script", "source_write", {}, "idem-apps"))
    gmail = bridge.admit(ExecutionRequest("req-mail", "gmail", "send", {}, "idem-mail"))

    gates = {
        "capability_admission": first.status == "VERIFIED_EXECUTED",
        "provider_native_reference": first.execution_ref.startswith("exec-"),
        "readback_verified": first.readback["active"] is True,
        "idempotent_execution": first.execution_ref == second.execution_ref,
        "rollback_verified": rollback["status"] == "ROLLED_BACK" and rollback["readback"]["active"] is False,
        "apps_script_authority_boundary": apps_script["state"] == "OWNER_CONSENT_REQUIRED",
        "owner_reserved_send_boundary": gmail["state"] == "OWNER_AUTHORITY_REQUIRED",
        "receipt_integrity": len(first.sha256) == 64,
    }
    result = {
        "status": "PROVIDER_EXECUTION_BRIDGE_VERIFIED" if all(gates.values()) else "PROVIDER_EXECUTION_BRIDGE_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "receipt": first.__dict__,
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_reference_adapter": True,
            "live_github_provider_write": False,
            "live_google_drive_provider_write": False,
            "live_gmail_send": False,
            "live_apps_script_source_write": False,
            "live_cloud_run_invocation": False,
        },
    }
    result["sha256"] = digest(result)
    (out / "sol-61-provider-bridge-receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
