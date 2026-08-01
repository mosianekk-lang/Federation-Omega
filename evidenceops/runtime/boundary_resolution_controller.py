from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "evidenceops/runtime/boundary_resolution_state.json"
MANIFEST_PATH = ROOT / "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json"
RECEIPT_DIR = ROOT / "evidenceops/runtime/receipts"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_routes() -> dict:
    return {
        "chat_bridge": {
            "configured": bool(os.getenv("EVIDENCEOPS_CHAT_BRIDGE_URL")),
            "loader_present": MANIFEST_PATH.exists(),
            "route": os.getenv("EVIDENCEOPS_CHAT_BRIDGE_URL", ""),
        },
        "dataverse": {
            "environment_configured": bool(os.getenv("KIM_DATAVERSE_URL")),
            "client_configured": bool(os.getenv("KIM_DATAVERSE_CLIENT_ID")),
            "secret_reference_configured": bool(os.getenv("KIM_DATAVERSE_SECRET_REF")),
            "url": os.getenv("KIM_DATAVERSE_URL", ""),
        },
    }


def evaluate_boundary(boundary: dict, routes: dict) -> dict:
    bid = boundary["boundary_id"]
    if bid == "BND-CHAT-ALIGNMENT":
        ready = routes["chat_bridge"]["configured"] and routes["chat_bridge"]["loader_present"]
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": ready,
            "status": "READY_TO_ATTEMPT" if ready else "WAITING_CAPABILITY",
            "next_action": "ATTEMPT_CHAT_ALIGNMENT" if ready else "DISCOVER_OR_BIND_AUTHORISED_CHAT_BRIDGE",
        }
    if bid == "BND-KIM-DATAVERSE":
        dv = routes["dataverse"]
        ready = dv["environment_configured"] and dv["client_configured"] and dv["secret_reference_configured"]
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": ready,
            "status": "READY_TO_ATTEMPT" if ready else "WAITING_CAPABILITY",
            "next_action": "RUN_DATAVERSE_CANARY" if ready else "DISCOVER_OR_BIND_DATAVERSE_CAPABILITY",
        }
    return {"boundary_id": bid, "status": "UNKNOWN", "ready_for_live_attempt": False}


def main() -> int:
    state = _load(STATE_PATH)
    manifest = _load(MANIFEST_PATH)
    routes = discover_routes()
    evaluations = [evaluate_boundary(b, routes) for b in state["boundaries"]]

    receipt = {
        "controller_id": state["controller_id"],
        "active_contract": manifest["active_contract"],
        "generated_at": int(time.time()),
        "state_sha256": _sha(STATE_PATH),
        "manifest_sha256": _sha(MANIFEST_PATH),
        "routes": routes,
        "evaluations": evaluations,
        "overall_status": "READY_TO_ATTEMPT" if any(e["ready_for_live_attempt"] for e in evaluations) else "WAITING_CAPABILITY",
        "truth_boundary": "No boundary is resolved until a live action, readback, and receipt are verified.",
    }

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = RECEIPT_DIR / "boundary_resolution_latest.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
