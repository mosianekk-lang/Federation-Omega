from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReferenceAdapter(Protocol):
    name: str
    def deploy(self, deployment_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def readback(self, deployment_id: str) -> dict[str, Any]: ...
    def health(self, deployment_id: str) -> dict[str, Any]: ...
    def persistence(self, deployment_id: str) -> dict[str, Any]: ...
    def rollback(self, deployment_id: str) -> dict[str, Any]: ...


@dataclass
class FilesystemAdapter:
    root: Path
    name: str = "filesystem-reference"

    def deploy(self, deployment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        target = self.root / deployment_id
        target.mkdir(parents=True, exist_ok=True)
        body = {"deployment_id": deployment_id, "payload": payload, "deployed_at": now()}
        (target / "deployment.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
        return {"provider": self.name, "state": "DEPLOYED", "sha256": digest_json(body)}

    def readback(self, deployment_id: str) -> dict[str, Any]:
        path = self.root / deployment_id / "deployment.json"
        body = json.loads(path.read_text())
        return {"provider": self.name, "pass": body["deployment_id"] == deployment_id, "body": body}

    def health(self, deployment_id: str) -> dict[str, Any]:
        return {"provider": self.name, "pass": (self.root / deployment_id / "deployment.json").is_file()}

    def persistence(self, deployment_id: str) -> dict[str, Any]:
        return self.health(deployment_id)

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        target = self.root / deployment_id
        if target.exists():
            shutil.rmtree(target)
        return {"provider": self.name, "state": "ROLLED_BACK", "target_absent": not target.exists()}


@dataclass
class SQLiteAdapter:
    database: Path
    name: str = "sqlite-reference"

    def _connect(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database)
        db.execute("CREATE TABLE IF NOT EXISTS deployments(id TEXT PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL)")
        return db

    def deploy(self, deployment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"deployment_id": deployment_id, "payload": payload, "deployed_at": now()}
        encoded = json.dumps(body, sort_keys=True)
        sha = hashlib.sha256(encoded.encode()).hexdigest()
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO deployments VALUES(?,?,?)", (deployment_id, encoded, sha))
        return {"provider": self.name, "state": "DEPLOYED", "sha256": sha}

    def readback(self, deployment_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT body,sha256 FROM deployments WHERE id=?", (deployment_id,)).fetchone()
        if row is None:
            return {"provider": self.name, "pass": False}
        return {"provider": self.name, "pass": hashlib.sha256(row[0].encode()).hexdigest() == row[1], "body": json.loads(row[0])}

    def health(self, deployment_id: str) -> dict[str, Any]:
        return {"provider": self.name, "pass": self.readback(deployment_id)["pass"]}

    def persistence(self, deployment_id: str) -> dict[str, Any]:
        reopened = SQLiteAdapter(self.database)
        return {"provider": self.name, "pass": reopened.readback(deployment_id)["pass"]}

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("DELETE FROM deployments WHERE id=?", (deployment_id,))
        return {"provider": self.name, "state": "ROLLED_BACK", "target_absent": not self.readback(deployment_id)["pass"]}


@dataclass
class ArchiveAdapter:
    root: Path
    name: str = "archive-reference"

    def deploy(self, deployment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{deployment_id}.zip"
        body = json.dumps({"deployment_id": deployment_id, "payload": payload, "deployed_at": now()}, sort_keys=True).encode()
        info = zipfile.ZipInfo("deployment.json", date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(info, body)
        return {"provider": self.name, "state": "DEPLOYED", "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    def readback(self, deployment_id: str) -> dict[str, Any]:
        target = self.root / f"{deployment_id}.zip"
        if not target.exists():
            return {"provider": self.name, "pass": False}
        with zipfile.ZipFile(target) as zf:
            clean = zf.testzip() is None
            body = json.loads(zf.read("deployment.json"))
        return {"provider": self.name, "pass": clean and body["deployment_id"] == deployment_id, "body": body}

    def health(self, deployment_id: str) -> dict[str, Any]:
        return {"provider": self.name, "pass": self.readback(deployment_id)["pass"]}

    def persistence(self, deployment_id: str) -> dict[str, Any]:
        return self.health(deployment_id)

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        target = self.root / f"{deployment_id}.zip"
        target.unlink(missing_ok=True)
        return {"provider": self.name, "state": "ROLLED_BACK", "target_absent": not target.exists()}


def prove_adapter(adapter: ReferenceAdapter, deployment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    deploy = adapter.deploy(deployment_id, payload)
    readback = adapter.readback(deployment_id)
    health = adapter.health(deployment_id)
    persistence = adapter.persistence(deployment_id)
    rollback = adapter.rollback(deployment_id)
    gates = {
        "deploy": deploy["state"] == "DEPLOYED",
        "readback": bool(readback["pass"]),
        "health": bool(health["pass"]),
        "persistence": bool(persistence["pass"]),
        "rollback": bool(rollback["target_absent"]),
    }
    return {"provider": adapter.name, "status": "REFERENCE_PROVIDER_VERIFIED" if all(gates.values()) else "FAILED", "gates": gates, "deploy": deploy, "rollback": rollback}


class ManagedOps:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.state = self.root / "managed_ops.json"
        if not self.state.exists():
            self._write({"services": {}, "incidents": {}, "backups": {}})

    def register_service(self, service_id: str, availability_target: float, response_minutes: int) -> dict[str, Any]:
        data = self._read()
        data["services"][service_id] = {"availability_target": availability_target, "response_minutes": response_minutes, "heartbeats": [], "status": "ACTIVE"}
        self._write(data)
        return data["services"][service_id]

    def heartbeat(self, service_id: str, healthy: bool, latency_ms: int) -> dict[str, Any]:
        data = self._read()
        event = {"at": now(), "healthy": healthy, "latency_ms": latency_ms}
        data["services"][service_id]["heartbeats"].append(event)
        self._write(data)
        return event

    def open_incident(self, incident_id: str, service_id: str, severity: str) -> dict[str, Any]:
        data = self._read()
        incident = {"incident_id": incident_id, "service_id": service_id, "severity": severity, "opened_at": now(), "status": "OPEN"}
        data["incidents"][incident_id] = incident
        self._write(data)
        return incident

    def resolve_incident(self, incident_id: str, resolution: str) -> dict[str, Any]:
        data = self._read()
        incident = data["incidents"][incident_id]
        incident.update({"status": "RESOLVED", "resolved_at": now(), "resolution": resolution})
        self._write(data)
        return incident

    def backup(self, service_id: str) -> dict[str, Any]:
        data = self._read()
        payload = data["services"][service_id]
        backup_id = f"bkp-{service_id}-{len(data['backups'])+1}"
        body = {"backup_id": backup_id, "service_id": service_id, "payload": payload, "created_at": now()}
        body["sha256"] = digest_json(body)
        data["backups"][backup_id] = body
        self._write(data)
        return body

    def restore(self, backup_id: str) -> dict[str, Any]:
        data = self._read()
        backup = data["backups"][backup_id]
        data["services"][backup["service_id"]] = backup["payload"]
        self._write(data)
        return {"backup_id": backup_id, "status": "RESTORED", "service_id": backup["service_id"]}

    def sla_report(self, service_id: str) -> dict[str, Any]:
        data = self._read()
        service = data["services"][service_id]
        beats = service["heartbeats"]
        availability = sum(1 for beat in beats if beat["healthy"]) / len(beats) if beats else 0.0
        incidents = [item for item in data["incidents"].values() if item["service_id"] == service_id]
        return {"service_id": service_id, "availability": availability, "target": service["availability_target"], "pass": availability >= service["availability_target"], "incidents": len(incidents), "open_incidents": sum(1 for item in incidents if item["status"] == "OPEN")}

    def _read(self) -> dict[str, Any]:
        return json.loads(self.state.read_text())

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.state.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, self.state)


@dataclass(frozen=True)
class CapabilityRelease:
    capability_id: str
    version: str
    solution_id: str
    interface: str
    licence: str
    lineage: tuple[str, ...]
    payload_sha256: str


class CapabilityMarketplace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = self.root / "capabilities.json"
        self.entitlements = self.root / "entitlements.json"
        if not self.registry.exists():
            self.registry.write_text("{}\n")
        if not self.entitlements.exists():
            self.entitlements.write_text("{}\n")

    def publish(self, capability_id: str, version: str, solution_id: str, interface: str, licence: str, lineage: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any]:
        key = f"{capability_id}@{version}"
        data = json.loads(self.registry.read_text())
        release = CapabilityRelease(capability_id, version, solution_id, interface, licence, lineage, digest_json(payload))
        encoded = asdict(release)
        if key in data and data[key] != encoded:
            raise ValueError("immutable release collision")
        data[key] = encoded
        self.registry.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return encoded

    def grant(self, tenant_id: str, capability_id: str, version: str, licence_id: str) -> dict[str, Any]:
        key = f"{capability_id}@{version}"
        registry = json.loads(self.registry.read_text())
        if key not in registry:
            raise KeyError(key)
        grants = json.loads(self.entitlements.read_text())
        grants.setdefault(tenant_id, {})[key] = {"licence_id": licence_id, "granted_at": now(), "status": "ACTIVE"}
        self.entitlements.write_text(json.dumps(grants, indent=2, sort_keys=True) + "\n")
        return grants[tenant_id][key]

    def check(self, tenant_id: str, capability_id: str, version: str) -> dict[str, Any]:
        key = f"{capability_id}@{version}"
        grants = json.loads(self.entitlements.read_text())
        grant = grants.get(tenant_id, {}).get(key)
        return {"tenant_id": tenant_id, "capability": key, "entitled": bool(grant and grant["status"] == "ACTIVE"), "grant": grant}


class PartnerProgramme:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / "partners.json"
        if not self.file.exists():
            self.file.write_text("{}\n")

    def register(self, partner_id: str, legal_name: str, brand_name: str, revenue_share_bps: int) -> dict[str, Any]:
        if not 0 <= revenue_share_bps <= 10_000:
            raise ValueError("invalid revenue share")
        data = json.loads(self.file.read_text())
        partner = {"partner_id": partner_id, "legal_name": legal_name, "brand": {"name": brand_name, "mode": "WHITE_LABEL"}, "licence": {"status": "DRAFT_REQUIRES_OWNER_APPROVAL"}, "revenue_share_bps": revenue_share_bps, "status": "REFERENCE_TENANT_READY", "registered_at": now()}
        data[partner_id] = partner
        self.file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return partner

    def revenue_share_calculation(self, partner_id: str, gross_contract_value_zar: int) -> dict[str, Any]:
        data = json.loads(self.file.read_text())
        partner = data[partner_id]
        amount = round(gross_contract_value_zar * partner["revenue_share_bps"] / 10_000, 2)
        return {"partner_id": partner_id, "gross_contract_value_zar": gross_contract_value_zar, "calculated_share_zar": amount, "status": "CALCULATION_ONLY_NO_REVENUE_RECEIVED"}
