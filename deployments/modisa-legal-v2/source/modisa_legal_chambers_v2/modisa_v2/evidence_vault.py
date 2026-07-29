from __future__ import annotations

import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .canonical import sha256_bytes
from .config import Settings
from .db import Repository
from .ids import new_id
from .prompt_security import scan_untrusted_text
from .schemas import EvidenceIngestRequest, EvidenceObject, ProofAppendRequest, ProofType
from .proof_ledger import ProofLedger
from .security import contains_secret


class EvidenceVault:
    """Content-addressed evidence store with optional AES-256-GCM encryption."""

    MAGIC = b"MODISA2\x00"

    def __init__(self, settings: Settings, repo: Repository, ledger: ProofLedger):
        self.settings = settings
        self.repo = repo
        self.ledger = ledger
        self.settings.evidence_root.mkdir(parents=True, exist_ok=True)

    @property
    def encryption_ready(self) -> bool:
        return self.settings.evidence_aes_key is not None

    def _resolve_input(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(candidate)
        if candidate.stat().st_size > self.settings.max_file_bytes:
            raise ValueError("Evidence file exceeds configured maximum")
        if not any(candidate == root or root in candidate.parents for root in self.settings.authorised_read_roots):
            raise ValueError("Evidence path is outside authorised roots")
        return candidate

    def _blob_path(self, sha256: str, encrypted: bool) -> Path:
        suffix = ".aesgcm" if encrypted else ".bin"
        path = self.settings.evidence_root / sha256[:2] / sha256[2:4] / f"{sha256}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _encrypt(self, plaintext: bytes, sha256: str) -> bytes:
        key = self.settings.evidence_aes_key
        if key is None:
            if not self.settings.allow_unencrypted_dev:
                raise RuntimeError("Evidence encryption key is required")
            return plaintext
        nonce = os.urandom(12)
        aad = f"MODISA-EVIDENCE:{sha256}".encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        return self.MAGIC + nonce + ciphertext

    def _decrypt(self, stored: bytes, sha256: str, encrypted: bool) -> bytes:
        if not encrypted:
            return stored
        key = self.settings.evidence_aes_key
        if key is None:
            raise RuntimeError("Evidence encryption key is required for readback")
        if not stored.startswith(self.MAGIC) or len(stored) < len(self.MAGIC) + 12:
            raise ValueError("Invalid encrypted evidence envelope")
        offset = len(self.MAGIC)
        nonce = stored[offset : offset + 12]
        ciphertext = stored[offset + 12 :]
        aad = f"MODISA-EVIDENCE:{sha256}".encode("utf-8")
        return AESGCM(key).decrypt(nonce, ciphertext, aad)

    def ingest(self, request: EvidenceIngestRequest, actor_id: str) -> tuple[EvidenceObject, str, str]:
        path = self._resolve_input(request.path)
        plaintext = path.read_bytes()
        digest = sha256_bytes(plaintext)
        encrypted = self.settings.evidence_aes_key is not None
        if not encrypted and not self.settings.allow_unencrypted_dev:
            raise RuntimeError("Unencrypted evidence storage is prohibited")
        storage_path = self._blob_path(digest, encrypted)
        if not storage_path.exists():
            payload = self._encrypt(plaintext, digest)
            temp = storage_path.with_suffix(storage_path.suffix + ".tmp")
            temp.write_bytes(payload)
            os.replace(temp, storage_path)

        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        text_scan = None
        if media_type.startswith("text/") or path.suffix.lower() in {".eml", ".md", ".txt", ".json", ".csv"}:
            decoded = plaintext[:2_000_000].decode("utf-8", errors="replace")
            text_scan = scan_untrusted_text(decoded)
        tainted = bool(text_scan and text_scan.tainted)
        metadata: dict[str, Any] = dict(request.metadata)
        metadata.update(
            {
                "source_absolute_path": str(path),
                "secret_pattern_detected": contains_secret(
                    plaintext[:1_000_000].decode("utf-8", errors="ignore")
                ),
                "prompt_injection_signals": list(text_scan.signals) if text_scan else [],
            }
        )
        evidence_id = new_id("EVID")
        created_at = datetime.fromisoformat(self.repo.now())
        self.repo.ensure_matter(request.matter_id)
        try:
            self.repo.execute(
                """
                INSERT INTO evidence_objects(
                  evidence_id,matter_id,sha256,byte_size,media_type,original_name,storage_path,
                  encrypted,parent_evidence_id,nested_depth,metadata_json,tainted_untrusted_content,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    evidence_id,
                    request.matter_id,
                    digest,
                    len(plaintext),
                    media_type,
                    path.name,
                    str(storage_path),
                    int(encrypted),
                    request.parent_evidence_id,
                    request.nested_depth,
                    self.repo.dumps(metadata),
                    int(tainted),
                    created_at.isoformat(),
                ),
            )
        except Exception:
            row = self.repo.fetch_one(
                """SELECT * FROM evidence_objects
                   WHERE matter_id=? AND sha256=? AND parent_evidence_id IS ? AND original_name=?""",
                (request.matter_id, digest, request.parent_evidence_id, path.name),
            )
            if row is None:
                raise
            evidence_id = row["evidence_id"]
            created_at = datetime.fromisoformat(row["created_at"])
            metadata = self.repo.loads(row["metadata_json"], {})
            encrypted = bool(row["encrypted"])
            storage_path = Path(row["storage_path"])
            tainted = bool(row["tainted_untrusted_content"])

        hash_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.EVIDENCE_HASH,
                subject_id=evidence_id,
                actor_id=actor_id,
                source_ids=[evidence_id],
                payload={
                    "sha256": digest,
                    "byte_size": len(plaintext),
                    "storage_path": str(storage_path),
                    "encrypted": encrypted,
                },
            )
        )
        injection_proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=request.matter_id,
                mission_id=request.mission_id,
                proof_type=ProofType.PROMPT_INJECTION_SCAN,
                subject_id=evidence_id,
                actor_id=actor_id,
                source_ids=[evidence_id],
                payload={
                    "tainted": tainted,
                    "signals": metadata.get("prompt_injection_signals", []),
                    "evidence_treated_as_untrusted_data": True,
                },
            )
        )
        return (
            EvidenceObject(
                evidence_id=evidence_id,
                matter_id=request.matter_id,
                sha256=digest,
                byte_size=len(plaintext),
                media_type=media_type,
                original_name=path.name,
                storage_path=str(storage_path),
                encrypted=encrypted,
                parent_evidence_id=request.parent_evidence_id,
                nested_depth=request.nested_depth,
                metadata=metadata,
                tainted_untrusted_content=tainted,
                created_at=created_at,
            ),
            hash_proof.proof_id,
            injection_proof.proof_id,
        )

    def get(self, evidence_id: str) -> EvidenceObject | None:
        row = self.repo.fetch_one("SELECT * FROM evidence_objects WHERE evidence_id=?", (evidence_id,))
        if row is None:
            return None
        return EvidenceObject(
            evidence_id=row["evidence_id"],
            matter_id=row["matter_id"],
            sha256=row["sha256"],
            byte_size=int(row["byte_size"]),
            media_type=row["media_type"],
            original_name=row["original_name"],
            storage_path=row["storage_path"],
            encrypted=bool(row["encrypted"]),
            parent_evidence_id=row["parent_evidence_id"],
            nested_depth=int(row["nested_depth"]),
            metadata=self.repo.loads(row["metadata_json"], {}),
            tainted_untrusted_content=bool(row["tainted_untrusted_content"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def read_verified(self, evidence_id: str, mission_id: str, actor_id: str) -> tuple[bytes, str]:
        evidence = self.get(evidence_id)
        if evidence is None:
            raise ValueError("Unknown evidence")
        stored = Path(evidence.storage_path).read_bytes()
        plaintext = self._decrypt(stored, evidence.sha256, evidence.encrypted)
        actual = sha256_bytes(plaintext)
        if actual != evidence.sha256:
            raise ValueError("Evidence readback hash mismatch")
        proof = self.ledger.append(
            ProofAppendRequest(
                matter_id=evidence.matter_id,
                mission_id=mission_id,
                proof_type=ProofType.SOURCE_READ,
                subject_id=evidence_id,
                actor_id=actor_id,
                source_ids=[evidence_id],
                payload={
                    "readback_sha256": actual,
                    "byte_size": len(plaintext),
                    "hash_matches_registered_evidence": True,
                },
            )
        )
        return plaintext, proof.proof_id
