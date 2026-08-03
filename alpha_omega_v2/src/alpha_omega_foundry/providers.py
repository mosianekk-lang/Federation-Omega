from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol
import datetime
import hashlib
import json
import os
import shutil
import zipfile


class ProviderAdapter(Protocol):
    """Standard proof-carrying provider contract."""

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_fingerprint(root: Path) -> dict:
    files: list[dict] = []
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        file_hash = _sha256_file(path)
        files.append({"path": relative, "sha256": file_hash, "bytes": path.stat().st_size})
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return {"sha256": digest.hexdigest(), "files": files, "file_count": len(files)}


def _write_deterministic_zip(source: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes())


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
        authorised = probe.read_text(encoding="utf-8") == "ok"
        probe.unlink(missing_ok=True)
        return {"provider": self.name, "authorised": authorised, "scope": "workspace_a1"}

    def snapshot(self, source: Path) -> dict:
        fingerprint = _tree_fingerprint(source)
        snapshot_root = self.workspace / "snapshots"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        target = snapshot_root / f"{source.name}-{fingerprint['sha256'][:12]}"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return {
            "provider": self.name,
            "state": "SNAPSHOT_CREATED",
            "target": str(target),
            "source_sha256": fingerprint["sha256"],
        }

    def deploy(self, source: Path, target: Path) -> dict:
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        return {"provider": self.name, "state": "DEPLOYED", "target": str(target)}

    def execute(self, target: Path) -> dict:
        genome = json.loads((target / "solution_genome.json").read_text(encoding="utf-8"))
        runtime_state = {
            "state": "RUNNING",
            "system_id": genome["system_id"],
            "executed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        (target / "runtime_state.json").write_text(
            json.dumps(runtime_state, indent=2), encoding="utf-8"
        )
        return {"provider": self.name, "state": "EXECUTED", "system_id": genome["system_id"]}

    def read_back(self, target: Path) -> dict:
        required = [
            "solution_genome.json",
            "product_spec.json",
            "maintenance_plan.json",
            "health.json",
            "runtime_state.json",
        ]
        present = {name: (target / name).is_file() for name in required}
        return {
            "provider": self.name,
            "state": "READBACK",
            "present": present,
            "pass": all(present.values()),
        }

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


@dataclass
class GitHubReleaseArtifactAdapter:
    """Build and verify an artifact inside a GitHub Actions provider run.

    GitHub's upload-artifact step performs the provider mutation. This adapter
    creates the exact staged files and a proof receipt that is later bound to the
    provider-native workflow run and artifact metadata.
    """

    workspace: Path
    environment: Mapping[str, str] = field(default_factory=lambda: os.environ)
    name: str = "github_release_artifact"

    @property
    def receipt_path(self) -> Path:
        return self.workspace / "provider_receipts" / "github_release_artifact_receipt.json"

    def discover(self) -> dict:
        available = self.environment.get("GITHUB_ACTIONS", "").lower() == "true"
        return {
            "provider": self.name,
            "available": available,
            "repository": self.environment.get("GITHUB_REPOSITORY"),
            "workflow": self.environment.get("GITHUB_WORKFLOW"),
        }

    def validate_authority(self) -> dict:
        required = ("GITHUB_RUN_ID", "GITHUB_SHA", "GITHUB_REPOSITORY")
        missing = [key for key in required if not self.environment.get(key)]
        return {
            "provider": self.name,
            "authorised": not missing and self.discover()["available"],
            "scope": "workflow_artifact_write",
            "missing": missing,
            "run_id": self.environment.get("GITHUB_RUN_ID"),
            "sha": self.environment.get("GITHUB_SHA"),
        }

    def snapshot(self, source: Path) -> dict:
        fingerprint = _tree_fingerprint(source)
        snapshot_dir = self.workspace / "provider_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_dir / f"{source.name}.snapshot.json"
        snapshot_file.write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
        return {
            "provider": self.name,
            "state": "SNAPSHOT_CREATED",
            "snapshot": str(snapshot_file),
            "source_sha256": fingerprint["sha256"],
            "file_count": fingerprint["file_count"],
        }

    def deploy(self, source: Path, target: Path) -> dict:
        target.mkdir(parents=True, exist_ok=True)
        archive = target / f"{source.name}.zip"
        _write_deterministic_zip(source, archive)
        manifest = {
            "provider": self.name,
            "artifact": archive.name,
            "sha256": _sha256_file(archive),
            "bytes": archive.stat().st_size,
            "source": _tree_fingerprint(source),
            "github": {
                "run_id": self.environment.get("GITHUB_RUN_ID"),
                "run_attempt": self.environment.get("GITHUB_RUN_ATTEMPT"),
                "sha": self.environment.get("GITHUB_SHA"),
                "ref": self.environment.get("GITHUB_REF"),
                "repository": self.environment.get("GITHUB_REPOSITORY"),
            },
        }
        manifest_path = target / f"{source.name}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "provider": self.name,
            "state": "ARTIFACT_STAGED",
            "archive": str(archive),
            "manifest": str(manifest_path),
        }

    def execute(self, target: Path) -> dict:
        manifest_path = next(target.glob("*.manifest.json"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive = target / manifest["artifact"]
        verified = archive.is_file() and _sha256_file(archive) == manifest["sha256"]
        return {"provider": self.name, "state": "ARTIFACT_VERIFIED" if verified else "FAILED"}

    def read_back(self, target: Path) -> dict:
        manifests = list(target.glob("*.manifest.json"))
        archives = list(target.glob("*.zip"))
        valid_zip = False
        members: list[str] = []
        if len(archives) == 1:
            with zipfile.ZipFile(archives[0], "r") as bundle:
                members = sorted(bundle.namelist())
                valid_zip = bundle.testzip() is None
        return {
            "provider": self.name,
            "pass": len(manifests) == 1 and len(archives) == 1 and valid_zip and bool(members),
            "archive_count": len(archives),
            "manifest_count": len(manifests),
            "members": members,
        }

    def health_check(self, target: Path) -> dict:
        readback = self.read_back(target)
        return {
            "provider": self.name,
            "pass": readback["pass"] and len(readback["members"]) >= 5,
            "member_count": len(readback["members"]),
        }

    def persistence_check(self, target: Path) -> dict:
        manifest_path = next(target.glob("*.manifest.json"), None)
        if manifest_path is None:
            return {"provider": self.name, "pass": False}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archive = target / manifest["artifact"]
        return {
            "provider": self.name,
            "pass": archive.is_file() and archive.stat().st_size == manifest["bytes"],
        }

    def rollback(self, target: Path) -> dict:
        if target.exists():
            shutil.rmtree(target)
        return {"provider": self.name, "state": "ROLLED_BACK", "target_absent": not target.exists()}

    def run_contract(self, source: Path, target: Path) -> dict:
        discover = self.discover()
        authority = self.validate_authority()
        snapshot = self.snapshot(source)
        deploy = self.deploy(source, target)
        execute = self.execute(target)
        readback = self.read_back(target)
        health = self.health_check(target)
        persistence = self.persistence_check(target)
        rollback_probe = self.workspace / "rollback_probe" / target.name
        self.deploy(source, rollback_probe)
        rollback = self.rollback(rollback_probe)
        gates = {
            "discover": bool(discover["available"]),
            "authority": bool(authority["authorised"]),
            "snapshot": snapshot["state"] == "SNAPSHOT_CREATED",
            "deploy": deploy["state"] == "ARTIFACT_STAGED",
            "execute": execute["state"] == "ARTIFACT_VERIFIED",
            "readback": bool(readback["pass"]),
            "health": bool(health["pass"]),
            "persistence": bool(persistence["pass"]),
            "rollback": bool(rollback["target_absent"]),
        }
        receipt = {
            "provider": self.name,
            "receipt_id": "RCP-GHA-" + hashlib.sha256(
                json.dumps(
                    {
                        "run_id": authority.get("run_id"),
                        "sha": authority.get("sha"),
                        "source": snapshot.get("source_sha256"),
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:16],
            "state": "PROVIDER_STAGED_VERIFIED" if all(gates.values()) else "PROVIDER_BLOCKED",
            "gates": gates,
            "discover": discover,
            "authority": authority,
            "snapshot": snapshot,
            "deploy": deploy,
            "execute": execute,
            "readback": readback,
            "health": health,
            "persistence": persistence,
            "rollback": rollback,
            "truth_boundary": "Provider upload is promoted only after GitHub reports a successful workflow run and hosted artifact metadata.",
        }
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt


@dataclass
class GoogleDriveBinaryAdapter:
    """Read and validate a provider-native Drive binary-upload receipt."""

    receipt_path: Path
    name: str = "google_drive_binary"

    def _receipt(self) -> dict:
        data = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        if data.get("provider") != self.name:
            raise ValueError("receipt provider mismatch")
        return data

    def discover(self) -> dict:
        return self._receipt()["discover"]

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
            "snapshot": receipt["snapshot"].get("state") == "DESTINATION_INVENTORY_CAPTURED",
            "deploy": receipt["deploy"].get("state") == "BINARY_UPLOADED",
            "execute": receipt["execute"].get("state") == "PROVIDER_ACCEPTED",
            "readback": bool(receipt["readback"].get("pass")),
            "health": bool(receipt["health"].get("pass")),
            "persistence": bool(receipt["persistence"].get("pass")),
            "rollback": bool(receipt["rollback"].get("target_absent")),
        }
        return {
            "provider": self.name,
            "state": "OPERATIONAL_VERIFIED_BINARY" if all(gates.values()) else "FAILED",
            "gates": gates,
            "receipt_id": receipt["proof"]["receipt_id"],
            "receipt_sha256": _sha256_file(self.receipt_path),
            "drive_file_id": receipt["proof"].get("drive_file_id"),
        }
