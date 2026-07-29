from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .db import Repository
from .proof_ledger import ProofLedger
from .schemas import ProofAppendRequest, ProofType


def file_hash(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class BackupService:
    """Consistent SQLite/evidence snapshot and restore-canary verifier."""

    def __init__(self, repo: Repository, ledger: ProofLedger, audit: AuditLog):
        self.repo = repo
        self.ledger = ledger
        self.audit = audit

    def create_snapshot(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        destination: Path,
    ) -> dict[str, Any]:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=False)
        db_target = destination / "modisa.sqlite3"
        source = sqlite3.connect(self.repo.path)
        target = sqlite3.connect(db_target)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        evidence_dir = destination / "evidence"
        evidence_dir.mkdir()
        evidence_manifest: list[dict[str, Any]] = []
        rows = self.repo.fetch_all(
            "SELECT evidence_id,storage_path,sha256,encrypted FROM evidence_objects WHERE matter_id=?",
            (matter_id,),
        )
        for row in rows:
            source_path = Path(row["storage_path"])
            if not source_path.exists():
                raise FileNotFoundError(f"Evidence blob missing: {row['evidence_id']}")
            target_path = evidence_dir / source_path.name
            if not target_path.exists():
                shutil.copy2(source_path, target_path)
            evidence_manifest.append(
                {
                    "evidence_id": row["evidence_id"],
                    "registered_plaintext_sha256": row["sha256"],
                    "snapshot_blob": str(target_path.relative_to(destination)),
                    "snapshot_blob_sha256": file_hash(target_path),
                    "encrypted": bool(row["encrypted"]),
                }
            )
        manifest = {
            "version": "2.0.0",
            "matter_id": matter_id,
            "mission_id": mission_id,
            "created_at": datetime.now(UTC).isoformat(),
            "database": {"path": "modisa.sqlite3", "sha256": file_hash(db_target)},
            "evidence": evidence_manifest,
        }
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        manifest["manifest_sha256"] = file_hash(manifest_path)
        self.audit.append(
            actor_id=actor_id,
            event_type="BACKUP_SNAPSHOT_CREATED",
            matter_id=matter_id,
            object_id=str(destination),
            payload={"manifest_sha256": manifest["manifest_sha256"], "evidence_count": len(evidence_manifest)},
        )
        return manifest

    def restore_canary(
        self,
        *,
        matter_id: str,
        mission_id: str,
        actor_id: str,
        snapshot_dir: Path,
    ) -> str:
        snapshot_dir = snapshot_dir.resolve()
        manifest_path = snapshot_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        db_path = snapshot_dir / manifest["database"]["path"]
        if file_hash(db_path) != manifest["database"]["sha256"]:
            raise ValueError("Snapshot database hash mismatch")
        for entry in manifest["evidence"]:
            blob = snapshot_dir / entry["snapshot_blob"]
            if not blob.exists() or file_hash(blob) != entry["snapshot_blob_sha256"]:
                raise ValueError(f"Snapshot evidence hash mismatch: {entry['evidence_id']}")

        with tempfile.TemporaryDirectory(prefix="modisa-restore-") as temp_dir:
            restored_db = Path(temp_dir) / "restored.sqlite3"
            shutil.copy2(db_path, restored_db)
            restored_repo = Repository(restored_db)
            restored_ledger = ProofLedger(restored_repo, self.ledger.signing_key)
            chain = restored_ledger.verify_chain(matter_id)
            restored_audit = AuditLog(restored_repo)
            audit_valid, audit_failure = restored_audit.verify()
            if not chain.valid:
                raise ValueError(f"Restored proof chain invalid: {chain.reason}")
            if not audit_valid:
                raise ValueError(f"Restored audit chain invalid at {audit_failure}")
            expected_evidence = len(manifest["evidence"])
            restored_evidence = int(
                restored_repo.fetch_one(
                    "SELECT COUNT(*) AS n FROM evidence_objects WHERE matter_id=?", (matter_id,)
                )["n"]
            )
            if restored_evidence != expected_evidence:
                raise ValueError("Restored evidence register count differs from snapshot manifest")

        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=matter_id,
                mission_id=mission_id,
                proof_type=ProofType.RESTORE_CANARY,
                subject_id=str(snapshot_dir),
                actor_id=actor_id,
                source_ids=[],
                payload={
                    "snapshot_dir": str(snapshot_dir),
                    "database_hash_verified": True,
                    "evidence_blob_hashes_verified": True,
                    "restored_proof_chain_valid": True,
                    "restored_audit_chain_valid": True,
                    "restored_evidence_count": len(manifest["evidence"]),
                },
            )
        )
        self.audit.append(
            actor_id=actor_id,
            event_type="RESTORE_CANARY_PASSED",
            matter_id=matter_id,
            object_id=str(snapshot_dir),
            payload={"proof_id": proof.proof_id},
        )
        return proof.proof_id
