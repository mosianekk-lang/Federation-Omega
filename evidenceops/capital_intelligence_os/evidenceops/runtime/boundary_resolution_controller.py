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


def _fingerprint(value: str) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "verified"}


def discover_routes() -> dict:
    bridge = _load(KDV_BRIDGE_PATH) if KDV_BRIDGE_PATH.exists() else {}
    identifier_ref = bridge.get("identifier_ref", "")
    receipt_ref = bridge.get("receipt_ref", "")
    status_ref = bridge.get("status_ref", "")
    identifier = os.getenv(identifier_ref, "") if identifier_ref else ""
    receipt = os.getenv(receipt_ref, "") if receipt_ref else ""
    runtime_status = os.getenv(status_ref, "") if status_ref else ""
    expected_status = bridge.get(
        "private_control_plane_status", "WRITE_AND_READBACK_VERIFIED"
    )

    chat_route = os.getenv("EVIDENCEOPS_CHAT_BRIDGE_URL", "")
    cloud_url = os.getenv("EVIDENCEOPS_CLOUD_RUN_URL", "")
    deployment_receipt = os.getenv(
        "EVIDENCEOPS_RUNTIME_DEPLOYMENT_RECEIPT", ""
    )
    writeback_receipt = os.getenv(
        "EVIDENCEOPS_RUNTIME_WRITEBACK_RECEIPT", ""
    )

    return {
        "chat_bridge": {
            "configured": bool(chat_route),
            "loader_present": MANIFEST_PATH.exists(),
            "route_fingerprint": _fingerprint(chat_route),
            "private_value_echoed": False,
        },
        "dataverse": {
            "in_place": {
                "descriptor_present": KDV_BRIDGE_PATH.exists(),
                "control_plane_verified": (
                    bridge.get("private_control_plane_status")
                    == "WRITE_AND_READBACK_VERIFIED"
                ),
                "runtime_bound": bool(
                    identifier
                    and receipt
                    and runtime_status == expected_status
                ),
                "identifier_present": bool(identifier),
                "receipt_present": bool(receipt),
                "identifier_fingerprint": _fingerprint(identifier),
                "receipt_fingerprint": _fingerprint(receipt),
                "receipt_ref": receipt_ref,
                "backend": bridge.get("backend", ""),
                "private_values_echoed": False,
            },
            "native_microsoft": {
                "environment_configured": bool(os.getenv("KIM_DATAVERSE_URL")),
                "client_configured": bool(os.getenv("KIM_DATAVERSE_CLIENT_ID")),
                "secret_reference_configured": bool(
                    os.getenv("KIM_DATAVERSE_SECRET_REF")
                ),
                "private_value_echoed": False,
            },
        },
        "runtime": {
            "cloud_url_present": bool(cloud_url),
            "cloud_url_fingerprint": _fingerprint(cloud_url),
            "deployment_receipt_present": bool(deployment_receipt),
            "deployment_receipt_fingerprint": _fingerprint(deployment_receipt),
            "health_verified": _truthy("EVIDENCEOPS_RUNTIME_HEALTH_VERIFIED"),
            "writeback_receipt_present": bool(writeback_receipt),
            "writeback_receipt_fingerprint": _fingerprint(writeback_receipt),
            "private_values_echoed": False,
        },
    }


def evaluate_boundary(boundary: dict, routes: dict) -> dict:
    bid = boundary["boundary_id"]

    if bid == "BND-CHAT-ALIGNMENT":
        ready = (
            routes["chat_bridge"]["configured"]
            and routes["chat_bridge"]["loader_present"]
        )
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": ready,
            "resolved": False,
            "status": "READY_TO_ATTEMPT" if ready else "WAITING_CAPABILITY",
            "next_action": (
                "ATTEMPT_CHAT_ALIGNMENT"
                if ready
                else "DISCOVER_OR_BIND_AUTHORISED_CHAT_BRIDGE"
            ),
        }

    if bid == "BND-KIM-DATAVERSE":
        inplace = routes["dataverse"]["in_place"]
        native = routes["dataverse"]["native_microsoft"]
        native_ready = (
            native["environment_configured"]
            and native["client_configured"]
            and native["secret_reference_configured"]
        )
        if inplace["control_plane_verified"]:
            return {
                "boundary_id": bid,
                "ready_for_live_attempt": False,
                "resolved": True,
                "status": "RESOLVED_IN_PLACE",
                "route": inplace["backend"],
                "receipt_ref": inplace["receipt_ref"],
                "runtime_bound": inplace["runtime_bound"],
                "next_action": (
                    "VERIFY_RUNTIME_WRITE_THROUGH"
                    if not inplace["runtime_bound"]
                    else "MONITOR_BRIDGE_AND_OPTIONALLY_BIND_NATIVE_MICROSOFT_DATAVERSE"
                ),
            }
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": native_ready,
            "resolved": False,
            "status": "READY_TO_ATTEMPT" if native_ready else "WAITING_CAPABILITY",
            "next_action": (
                "RUN_NATIVE_DATAVERSE_CANARY"
                if native_ready
                else "DISCOVER_OR_BIND_CANONICAL_BACKEND"
            ),
        }

    if bid == "BND-SOVEREIGN-RUNTIME":
        runtime = routes["runtime"]
        canonical_bound = routes["dataverse"]["in_place"]["runtime_bound"]
        resolved = bool(
            runtime["cloud_url_present"]
            and runtime["deployment_receipt_present"]
            and runtime["health_verified"]
            and runtime["writeback_receipt_present"]
            and canonical_bound
        )
        return {
            "boundary_id": bid,
            "ready_for_live_attempt": not resolved,
            "resolved": resolved,
            "status": "RESOLVED" if resolved else "ACTIVE_REPAIR",
            "next_action": (
                "MONITOR_PRODUCTION_RUNTIME"
                if resolved
                else "COMPLETE_GREEN_CI_DEPLOY_HEALTH_AND_WRITEBACK_RECEIPTS"
            ),
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
        "kdv_bridge_sha256": (
            _sha(KDV_BRIDGE_PATH) if KDV_BRIDGE_PATH.exists() else None
        ),
        "routes": routes,
        "evaluations": evaluations,
        "resolved_count": resolved_count,
        "boundary_count": len(evaluations),
        "overall_status": overall_status,
        "private_values_persisted": False,
        "truth_boundary": (
            "A boundary is resolved only after live action, independent "
            "readback, and a verified receipt."
        ),
    }

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = RECEIPT_DIR / "boundary_resolution_latest.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
