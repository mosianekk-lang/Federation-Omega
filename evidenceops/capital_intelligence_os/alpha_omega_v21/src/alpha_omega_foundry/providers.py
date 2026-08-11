from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import datetime
import hashlib
import json
import shutil
import zipfile


class ProviderAdapter(Protocol):
    name: str

    def discover(self) -> dict: ...
    def validate_authority(self) -> dict: ...
    def snapshot(self, source: Path) -> dict: ...
    def deploy(self, source: Path, target: Path) -> dict: ...
    def execute(self, target: Path) -> dict: ...
    def read_back(self, target: Path) -> dict: ...
    def health_check(self, target: Path) -> dict: ...
    def persistence_check(self, target: Path) -> dict: ...
    def rollback(self, target: Path) -> dict: ...


@dataclass
class LocalProviderAdapter:
    workspace: Path
    name: str = "local"

    def discover(self) -> dict:
        return {"provider": self.name, "available": True, "workspace": str(self.workspace)}

    def validate_authority(self) -> dict:
        self.workspace.mkdir(parents=True, exist_ok=True)
        probe = self.workspace / ".authority_probe"
        probe.write_text("ok", encoding="utf-8")
        passed = probe.read_text(encoding="utf-8") == "ok"
        probe.unlink(missing_ok=True)
        return {"provider": self.name, "authorised": passed, "scope": "workspace"}

    def snapshot(self, source: Path) -> dict:
        snapshot_root = self.workspace / "snapshots"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        target = snapshot_root / f"{source.name}-{timestamp}"
        shutil.copytree(source, target)
        return {"provider": self.name, "state": "SNAPSHOT_CREATED", "target": str(target)}

    def deploy(self, source: Path, target: Path) -> dict:
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        return {"provider": self.name, "state": "DEPLOYED", "target": str(target)}

    def execute(self, target: Path) -> dict:
        genome = json.loads((target / "solution_genome.json").read_text(encoding="utf-8"))
        runtime_state = {"state": "RUNNING", "system_id": genome["system_id"]}
        (target / "runtime_state.json").write_text(json.dumps(runtime_state, indent=2), encoding="utf-8")
        return {"provider": self.name, "state": "EXECUTED", "system_id": genome["system_id"]}

    def read_back(self, target: Path) -> dict:
        required = [
            "solution_genome.json",
            "product_spec.json",
            "maintenance_plan.json",
            "health.json",
            "runtime_state.json",
        ]
        present = {name: (target / name).exists() for name in required}
        return {"provider": self.name, "state": "READBACK", "present": present, "pass": all(present.values())}

    def health_check(self, target: Path) -> dict:
        health = json.loads((target / "health.json").read_text(encoding="utf-8"))
        passed = all(float(value) >= 0.99 for value in health.values())
        return {"provider": self.name, "pass": passed, "health": health}

    def persistence_check(self, target: Path) -> dict:
        state = json.loads((target / "runtime_state.json").read_text(encoding="utf-8"))
        return {"provider": self.name, "pass": target.exists() and state.get("state") == "RUNNING"}

    def rollback(self, target: Path) -> dict:
        if target.exists():
            shutil.rmtree(target)
        return {"provider": self.name, "state": "ROLLED_BACK", "target_absent": not target.exists()}


class ReleaseArtifactAdapter:
    name = "release_artifact"

    def build(self, source: Path, output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        archive = output_dir / f"{source.name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    bundle.write(path, arcname=path.relative_to(source))
        sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = {
            "artifact": archive.name,
            "sha256": sha256,
            "bytes": archive.stat().st_size,
            "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        manifest_path = output_dir / f"{source.name}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        verified = hashlib.sha256(archive.read_bytes()).hexdigest() == sha256
        return {
            "state": "ARTIFACT_VERIFIED" if verified else "FAILED",
            "archive": str(archive),
            "manifest": str(manifest_path),
            **manifest,
        }


@dataclass
class GoogleDriveManifestAdapter:
    """Validate provider-native Google Drive manifest deployment receipts.

    Google Drive mutations are executed by an authorised provider connector. This
    adapter imports the resulting immutable receipt, exposes the standard provider
    contract, and refuses promotion when any provider-native gate is absent.
    """

    receipt_path: Path
    name: str = "google_drive_manifest"

    def _receipt(self) -> dict:
        if not self.receipt_path.exists():
            raise FileNotFoundError(self.receipt_path)
        data = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        if data.get("provider") != self.name:
            raise ValueError("receipt provider does not match google_drive_manifest")
        return data

    def discover(self) -> dict:
        receipt = self._receipt()
        return receipt["discover"]

    def validate_authority(self) -> dict:
        return self._receipt()["authority"]

    def snapshot(self, source: Path | None = None) -> dict:
        return self._receipt()["snapshot"]

    def deploy(self, source: Path | None = None, target: Path | None = None) -> dict:
        return self._receipt()["deploy"]

    def execute(self, target: Path | None = None) -> dict:
        return self._receipt()["execute"]

    def read_back(self, target: Path | None = None) -> dict:
        return self._receipt()["readback"]

    def health_check(self, target: Path | None = None) -> dict:
        return self._receipt()["health"]

    def persistence_check(self, target: Path | None = None) -> dict:
        return self._receipt()["persistence"]

    def rollback(self, target: Path | None = None) -> dict:
        return self._receipt()["rollback"]

    def proof_receipt(self) -> dict:
        receipt = self._receipt()
        gates = {
            "discover": bool(receipt["discover"].get("available")),
            "authority": bool(receipt["authority"].get("authorised")),
            "snapshot": receipt["snapshot"].get("state") == "INVENTORY_CAPTURED",
            "deploy": receipt["deploy"].get("state") == "DOCUMENT_CREATED",
            "execute": receipt["execute"].get("state") == "CONTENT_WRITTEN",
            "readback": bool(receipt["readback"].get("pass")),
            "health": bool(receipt["health"].get("pass")),
            "persistence": bool(receipt["persistence"].get("pass")),
            "rollback": bool(receipt["rollback"].get("target_absent")),
        }
        digest = hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()
        return {
            "provider": self.name,
            "state": "OPERATIONAL_VERIFIED_MANIFEST" if all(gates.values()) else "FAILED",
            "gates": gates,
            "receipt_sha256": digest,
            "receipt_id": receipt["proof"]["receipt_id"],
            "binary_package_state": receipt["proof"]["binary_package_state"],
        }
