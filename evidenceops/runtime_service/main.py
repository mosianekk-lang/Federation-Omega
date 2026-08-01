from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ACTIVE_CONTRACT = "EMSIT-KDV-FEVX-IPFL-EVI-FPFE-v3.2"
MANIFEST_PATH = os.getenv(
    "EVIDENCEOPS_ACTIVE_MANIFEST",
    "evidenceops/runtime/ACTIVE_SOVEREIGN_TRANSLATOR.json",
)
STATE_DB = os.getenv("EVIDENCEOPS_STATE_DB", "/tmp/evidenceops/state.db")


class MissionRequest(BaseModel):
    mission_id: str = Field(min_length=1)
    directive_id: str = Field(min_length=1)
    source_input: str = Field(min_length=1)
    authority: str = "S0"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StateStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS missions(mission_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS deltas(delta_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS receipts(receipt_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        self.conn.commit()

    def save_mission(self, mission_id: str, payload: Dict[str, Any]):
        self.conn.execute(
            "INSERT OR REPLACE INTO missions VALUES(?,?,?)",
            (mission_id, json.dumps(payload), int(time.time())),
        )
        self.conn.commit()

    def save_delta(self, delta: Dict[str, Any]):
        self.conn.execute(
            "INSERT OR REPLACE INTO deltas VALUES(?,?,?,?,?)",
            (
                delta["delta_id"],
                delta["mission_id"],
                delta["status"],
                json.dumps(delta),
                int(time.time()),
            ),
        )
        self.conn.commit()

    def save_receipt(self, receipt: Dict[str, Any]):
        self.conn.execute(
            "INSERT OR REPLACE INTO receipts VALUES(?,?,?,?)",
            (
                receipt["receipt_id"],
                receipt["mission_id"],
                json.dumps(receipt),
                int(time.time()),
            ),
        )
        self.conn.commit()

    def open_deltas(self):
        rows = self.conn.execute(
            "SELECT payload FROM deltas WHERE status != 'CLOSED'"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]


class NativeDataverseAdapter:
    """Optional Microsoft Dataverse parity adapter.

    The canonical current backend is declared by the active manifest. This
    adapter is used only when a native Microsoft Dataverse URL and short-lived
    access token are explicitly supplied to the runtime.
    """

    def __init__(self):
        self.base_url = os.getenv("KIM_DATAVERSE_URL", "").rstrip("/")
        self.token = os.getenv("KIM_DATAVERSE_ACCESS_TOKEN", "")
        self.table = os.getenv(
            "KIM_DATAVERSE_MISSION_TABLE", "evidenceops_missions"
        )
        self.timeout = int(os.getenv("KIM_DATAVERSE_TIMEOUT", "20"))

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token and self.table)

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }

    def health(self):
        if not self.configured:
            return {
                "configured": False,
                "status": "OPTIONAL_PARITY_ROUTE_UNBOUND",
            }
        response = requests.get(
            f"{self.base_url}/api/data/v9.2/{self.table}?$top=1",
            headers=self.headers(),
            timeout=self.timeout,
        )
        return {
            "configured": True,
            "status": "READ_VERIFIED" if response.ok else "READ_FAILED",
            "http_status": response.status_code,
        }

    def upsert(self, mission_id: str, payload: Dict[str, Any]):
        if not self.configured:
            return {
                "status": "OPTIONAL_PARITY_SYNC_PACKAGE_CREATED",
                "configured": False,
                "payload": payload,
            }
        escaped = mission_id.replace("'", "''")
        url = (
            f"{self.base_url}/api/data/v9.2/"
            f"{self.table}(evidenceops_missionid='{escaped}')"
        )
        write = requests.patch(
            url, headers=self.headers(), json=payload, timeout=self.timeout
        )
        if write.status_code not in (200, 204):
            raise RuntimeError(
                f"Dataverse write failed: {write.status_code} {write.text[:500]}"
            )
        read = requests.get(url, headers=self.headers(), timeout=self.timeout)
        if not read.ok:
            raise RuntimeError(f"Dataverse readback failed: {read.status_code}")
        return {
            "status": "WRITE_READBACK_VERIFIED",
            "configured": True,
            "write_status": write.status_code,
            "readback": read.json(),
            "verified_at": int(time.time()),
        }


def load_manifest():
    path = Path(MANIFEST_PATH)
    if not path.exists():
        raise RuntimeError(f"Active manifest missing: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("active_contract") != ACTIVE_CONTRACT:
        raise RuntimeError("Active contract mismatch")
    if manifest.get("mission_delta_owner") != "WORKFORCE":
        raise RuntimeError("Mission Delta ownership invariant failed")
    if manifest.get("report_only_terminal_allowed") is not False:
        raise RuntimeError("Report-only closure is prohibited")
    return manifest


def canonical_backend_state(manifest: Dict[str, Any]) -> Dict[str, Any]:
    backend = manifest.get("canonical_backend") or {}
    required = {
        "type",
        "spreadsheet_id",
        "bridge_record",
        "status",
        "receipt_id",
    }
    missing = sorted(required - set(backend))
    verified = (
        not missing
        and backend.get("status") == "WRITE_AND_READBACK_VERIFIED"
    )
    return {
        **backend,
        "configured": bool(backend),
        "verified": verified,
        "missing_fields": missing,
    }


store = StateStore(STATE_DB)
native_dataverse = NativeDataverseAdapter()
app = FastAPI(title="EvidenceOps Sovereign Runtime", version="1.1.0")


@app.get("/health")
def health():
    try:
        manifest = load_manifest()
        backend = canonical_backend_state(manifest)
        return {
            "status": "ok",
            "active_contract": manifest["active_contract"],
            "mission_delta_owner": manifest["mission_delta_owner"],
            "canonical_backend": backend,
            "native_microsoft_dataverse": native_dataverse.health(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/ready")
def ready():
    result = health()
    return {
        "ready": (
            result["status"] == "ok"
            and result["canonical_backend"]["verified"]
        ),
        "mission_intake_ready": True,
        "canonical_context_ready": result["canonical_backend"]["verified"],
        "runtime_write_through_ready": (
            result["native_microsoft_dataverse"]["status"]
            == "READ_VERIFIED"
        ),
        **result,
    }


@app.post("/missions")
def missions(req: MissionRequest):
    try:
        manifest = load_manifest()
        backend = canonical_backend_state(manifest)
        source_hash = hashlib.sha256(
            req.source_input.encode("utf-8")
        ).hexdigest()
        translated = {
            "source_directive": req.source_input,
            "founder_controlled_outcome": req.source_input,
            "success_rule": (
                "REQUESTED_OUTCOME_EQUALS_VERIFIED_OPERATING_OUTCOME"
            ),
            "execution_policy": [
                "PRESERVE_SOURCE",
                "DISCOVER_CAPABILITIES",
                "USE_KIM_DATAVERSE_WHERE_BOUND",
                "CREATE_TASK_DEPENDENCY_IMPACT_GRAPHS",
                "EXECUTE_AUTHORISED_WORK",
                "READBACK_VERIFY",
                "KEEP_MISSION_DELTA_WORKFORCE_OWNED",
            ],
        }
        dv_payload = {
            "evidenceops_missionid": req.mission_id,
            "evidenceops_directiveid": req.directive_id,
            "evidenceops_sourcehash": source_hash,
            "evidenceops_sourceinput": req.source_input,
            "evidenceops_status": "ACTIVE",
        }
        parity_result = native_dataverse.upsert(req.mission_id, dv_payload)

        delta = None
        maturity = (
            "MISSION_STATE_BOUND"
            if backend["verified"]
            else "DOCTRINE_ACTIVE"
        )
        if parity_result["status"] == "WRITE_READBACK_VERIFIED":
            maturity = "KIM_DATAVERSE_WRITE_VERIFIED"
        else:
            delta = {
                "delta_id": f"DELTA-{uuid.uuid4().hex[:12]}",
                "mission_id": req.mission_id,
                "description": (
                    "The canonical in-place Kim Dataverse bridge is verified, "
                    "but this runtime instance has not yet proved direct "
                    "mission write-through and readback."
                    if backend["verified"]
                    else "Canonical Kim Dataverse availability is not verified."
                ),
                "owner": "WORKFORCE",
                "status": "ACTIVE_REPAIR",
                "next_actions": [
                    "DISCOVER_AUTHORISED_RUNTIME_WRITE_ROUTE",
                    "BIND_RUNTIME_IDENTITY",
                    "WRITE_MISSION_TO_CANONICAL_BACKEND",
                    "READBACK_VERIFY",
                    "PERSIST_RECEIPT",
                ],
                "verified_closed": False,
            }
            store.save_delta(delta)

        receipt = {
            "receipt_id": f"RECEIPT-{uuid.uuid4().hex[:12]}",
            "mission_id": req.mission_id,
            "directive_id": req.directive_id,
            "source_hash": source_hash,
            "maturity": maturity,
            "translated_prompt": translated,
            "mission_delta": delta,
            "canonical_backend": backend,
            "native_microsoft_dataverse": parity_result,
            "runtime": {
                "active_contract": manifest["active_contract"],
                "report_only_terminal_allowed": manifest[
                    "report_only_terminal_allowed"
                ],
            },
        }
        store.save_mission(req.mission_id, receipt)
        store.save_receipt(receipt)
        return receipt
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/triggers/resolve")
def resolve():
    return {
        "results": [
            {
                "delta_id": delta["delta_id"],
                "status": "ACTIVE_REPAIR",
                "owner": "WORKFORCE",
                "next_actions": delta["next_actions"],
            }
            for delta in store.open_deltas()
        ]
    }
