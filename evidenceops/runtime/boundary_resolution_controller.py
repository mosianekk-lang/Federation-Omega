from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "evidenceops/runtime/boundary_resolution_state.json"
MANIFEST_PATH = ROOT / "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json"
KDV_BRIDGE_PATH = ROOT / "evidenceops/runtime/kim_dataverse_inplace_bridge.json"
RECEIPT_DIR = ROOT / "evidenceops/runtime/receipts"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_routes() -> dict:
    bridge = _load(KDV_BRIDGE_PATH) if KDV_BRIDGE_PATH.exists() else {}
    inplace_verified = bool(
        bridge.get("write_verified")
        and bridge.get("readback_verified")
        and bridge.get("receipt_id")
        and bridge.get("spreadsheet_id")
    )
    return {
        "chat_bridge": {
            "configured": bool(os.getenv("EVIDENCEOPS_CHAT_BRIDGE_URL")),
            "loader_present": MANIFEST_PATH.exists(),
            "route": os.getenv("EVIDENCEOPS_CHAT_BRIDGE_URL", ""),
        },
        "dataverse": {
            "in_place": {
                "configured": KDV_BRIDGE_PATH.exists(),
                "verified": inplace_verified,
                "bridge_id": bridge.get("bridge_id", ""),
                "spreadsheet_id": bridge.get("spreadsheet_id", ""),
                "receipt_id": bridge.get("receipt_id", ""),
                "backend": bridge.get("backend", ""),
            },
            "native_microsoft": {
                "environment_configured": bool(os.getenv("KIM_DATAVERSE_URL")),
                "client_configured": bool(os.getenv("KIM_DATAVERSE_CLIENT_ID")),
                "secret_reference_configured": bool(os.getenv("KIM_DATAVERSE_SECRET_REF")),
                "url": os.getenv("KIM_DATAVERSE_URL", ""),
            },
        },
    }


def evaluate_boundary(boundary: dict, routes: dict) -> dict:
    bid = boundary["boundary_id"]

    if bid == "BND-CHAT-ALIGNMENT":
        ready = routes["chat_bridge"]["configured"] and routes["chat_bridge"]["loader_present"]
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": ready,
            "resolved": False,
            "status": "READY_TO_ATTEMPT" if ready else "WAITING_CAPABILITY",
            "next_action": "ATTEMPT_CHAT_ALIGNMENT" if ready else "DISCOVER_OR_BIND_AUTHORISED_CHAT_BRIDGE",
        }

    if bid == "BND-KIM-DATAVERSE":
        inplace = routes["dataverse"]["in_place"]
        native = routes["dataverse"]["native_microsoft"]
        native_ready = (
            native["environment_configured"]
            and native["client_configured"]
            and native["secret_reference_configured"]
        )
        if inplace["verified"]:
            return {
                "boundary_id": bid,
                "ready_for_live_attempt": False,
                "resolved": True,
                "status": "RESOLVED_IN_PLACE",
                "route": inplace["backend"],
                "receipt_id": inplace["receipt_id"],
                "next_action": "MONITOR_BRIDGE_AND_OPTIONALLY_BIND_NATIVE_MICROSOFT_DATAVERSE",
            }
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": native_ready,
            "resolved": False,
            "status": "READY_TO_ATTEMPT" if native_ready else "WAITING_CAPABILITY",
            "next_action": "RUN_NATIVE_DATAVERSE_CANARY" if native_ready else "DISCOVER_OR_BIND_CANONICAL_BACKEND",
        }

    return {
        "boundary_id": bid,
        "status": "UNKNOWN",
        "ready_for_live_attempt": False,
        "resolved": False,
        "next_action": "CLASSIFY_BOUNDARY",
    }


def main() -> int:
    state = _load(STATE_PATH)
    manifest = _load(MANIFEST_PATH)
    routes = discover_routes()
    evaluations = [evaluate_boundary(b, routes) for b in state["boundaries"]]

    resolved_count = sum(1 for e in evaluations if e.get("resolved"))
    ready_count = sum(1 for e in evaluations if e.get("ready_for_live_attempt"))
    if resolved_count == len(evaluations):
        overall_status = "ALL_BOUNDARIES_RESOLVED"
    elif resolved_count:
        overall_status = "PARTIALLY_RESOLVED"
    elif ready_count:
        overall_status = "READY_TO_ATTEMPT"
    else:
        overall_status = "WAITING_CAPABILITY"

    receipt = {
        "controller_id": state["controller_id"],
        "active_contract": manifest["active_contract"],
        "generated_at": int(time.time()),
        "state_sha256": _sha(STATE_PATH),
        "manifest_sha256": _sha(MANIFEST_PATH),
        "kdv_bridge_sha256": _sha(KDV_BRIDGE_PATH) if KDV_BRIDGE_PATH.exists() else None,
        "routes": routes,
        "evaluations": evaluations,
        "resolved_count": resolved_count,
        "boundary_count": len(evaluations),
        "overall_status": overall_status,
        "truth_boundary": "A boundary is resolved only after live action, independent readback, and a verified receipt.",
    }

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = RECEIPT_DIR / "boundary_resolution_latest.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
