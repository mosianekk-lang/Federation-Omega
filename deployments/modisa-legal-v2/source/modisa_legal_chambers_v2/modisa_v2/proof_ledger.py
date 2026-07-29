from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Iterable

from .canonical import canonical_json, hmac_sha256_b64, secure_compare, sha256_json, sha256_text
from .db import Repository
from .ids import new_id
from .schemas import ChainVerificationResult, ProofAppendRequest, ProofRecord, ProofType


GENESIS_HASH = "0" * 64


class ProofLedger:
    """Append-only per-matter hash chain with HMAC authenticity.

    A model can request a proof record, but it cannot choose its chain position, hashes or
    signature. Release decisions verify these records independently.
    """

    def __init__(self, repo: Repository, signing_key: bytes | None):
        self.repo = repo
        self.signing_key = signing_key

    @property
    def ready(self) -> bool:
        return self.signing_key is not None

    def _sign(self, chain_hash: str) -> str:
        if self.signing_key is None:
            raise RuntimeError("Proof ledger is unavailable: signing key is missing")
        return hmac_sha256_b64(self.signing_key, chain_hash)

    @staticmethod
    def _record_from_row(row: Any) -> ProofRecord:
        return ProofRecord(
            proof_id=row["proof_id"],
            matter_id=row["matter_id"],
            mission_id=row["mission_id"],
            proof_type=ProofType(row["proof_type"]),
            subject_id=row["subject_id"],
            actor_id=row["actor_id"],
            source_ids=json.loads(row["source_ids_json"]),
            payload=json.loads(row["payload_json"]),
            payload_hash=row["payload_hash"],
            chain_index=int(row["chain_index"]),
            previous_hash=row["previous_hash"],
            chain_hash=row["chain_hash"],
            signature=row["signature"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def append(self, request: ProofAppendRequest) -> ProofRecord:
        if self.signing_key is None:
            raise RuntimeError("Proof ledger signing key is required")
        self.repo.ensure_matter(request.matter_id)
        created_at = datetime.now(UTC)
        payload_hash = sha256_json(request.payload)
        proof_id = new_id("PRF")

        with self.repo.connect(immediate=True) as conn:
            last = conn.execute(
                "SELECT chain_index, chain_hash FROM proof_records WHERE matter_id=? "
                "ORDER BY chain_index DESC LIMIT 1",
                (request.matter_id,),
            ).fetchone()
            chain_index = int(last["chain_index"]) + 1 if last else 1
            previous_hash = str(last["chain_hash"]) if last else GENESIS_HASH
            chain_body = {
                "proof_id": proof_id,
                "matter_id": request.matter_id,
                "mission_id": request.mission_id,
                "proof_type": request.proof_type.value,
                "subject_id": request.subject_id,
                "actor_id": request.actor_id,
                "source_ids": request.source_ids,
                "payload_hash": payload_hash,
                "chain_index": chain_index,
                "previous_hash": previous_hash,
                "created_at": created_at.isoformat(),
            }
            chain_hash = sha256_text(canonical_json(chain_body))
            signature = self._sign(chain_hash)
            conn.execute(
                """
                INSERT INTO proof_records(
                  proof_id,matter_id,mission_id,proof_type,subject_id,actor_id,
                  source_ids_json,payload_json,payload_hash,chain_index,previous_hash,
                  chain_hash,signature,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    proof_id,
                    request.matter_id,
                    request.mission_id,
                    request.proof_type.value,
                    request.subject_id,
                    request.actor_id,
                    self.repo.dumps(request.source_ids),
                    self.repo.dumps(request.payload),
                    payload_hash,
                    chain_index,
                    previous_hash,
                    chain_hash,
                    signature,
                    created_at.isoformat(),
                ),
            )
        return ProofRecord(
            proof_id=proof_id,
            matter_id=request.matter_id,
            mission_id=request.mission_id,
            proof_type=request.proof_type,
            subject_id=request.subject_id,
            actor_id=request.actor_id,
            source_ids=request.source_ids,
            payload=request.payload,
            payload_hash=payload_hash,
            chain_index=chain_index,
            previous_hash=previous_hash,
            chain_hash=chain_hash,
            signature=signature,
            created_at=created_at,
        )

    def get(self, proof_id: str) -> ProofRecord | None:
        row = self.repo.fetch_one("SELECT * FROM proof_records WHERE proof_id=?", (proof_id,))
        return self._record_from_row(row) if row else None

    def list_for_mission(self, matter_id: str, mission_id: str) -> list[ProofRecord]:
        rows = self.repo.fetch_all(
            "SELECT * FROM proof_records WHERE matter_id=? AND mission_id=? ORDER BY chain_index",
            (matter_id, mission_id),
        )
        return [self._record_from_row(row) for row in rows]

    def list_by_ids(self, proof_ids: Iterable[str]) -> list[ProofRecord]:
        ids = list(dict.fromkeys(proof_ids))
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.repo.fetch_all(
            f"SELECT * FROM proof_records WHERE proof_id IN ({placeholders}) ORDER BY matter_id, chain_index",
            ids,
        )
        by_id = {row["proof_id"]: self._record_from_row(row) for row in rows}
        return [by_id[proof_id] for proof_id in ids if proof_id in by_id]

    def verify_record(self, record: ProofRecord) -> tuple[bool, str | None]:
        if self.signing_key is None:
            return False, "signing key missing"
        if sha256_json(record.payload) != record.payload_hash:
            return False, "payload hash mismatch"
        body = {
            "proof_id": record.proof_id,
            "matter_id": record.matter_id,
            "mission_id": record.mission_id,
            "proof_type": record.proof_type.value,
            "subject_id": record.subject_id,
            "actor_id": record.actor_id,
            "source_ids": record.source_ids,
            "payload_hash": record.payload_hash,
            "chain_index": record.chain_index,
            "previous_hash": record.previous_hash,
            "created_at": record.created_at.isoformat(),
        }
        expected_hash = sha256_text(canonical_json(body))
        if expected_hash != record.chain_hash:
            return False, "chain hash mismatch"
        if not secure_compare(self._sign(record.chain_hash), record.signature):
            return False, "signature mismatch"
        return True, None

    def verify_chain(self, matter_id: str) -> ChainVerificationResult:
        rows = self.repo.fetch_all(
            "SELECT * FROM proof_records WHERE matter_id=? ORDER BY chain_index", (matter_id,)
        )
        previous = GENESIS_HASH
        expected_index = 1
        for row in rows:
            record = self._record_from_row(row)
            if record.chain_index != expected_index:
                return ChainVerificationResult(
                    valid=False,
                    matter_id=matter_id,
                    checked_count=expected_index - 1,
                    failed_proof_id=record.proof_id,
                    reason="non-contiguous chain index",
                )
            if record.previous_hash != previous:
                return ChainVerificationResult(
                    valid=False,
                    matter_id=matter_id,
                    checked_count=expected_index - 1,
                    failed_proof_id=record.proof_id,
                    reason="previous hash mismatch",
                )
            valid, reason = self.verify_record(record)
            if not valid:
                return ChainVerificationResult(
                    valid=False,
                    matter_id=matter_id,
                    checked_count=expected_index - 1,
                    failed_proof_id=record.proof_id,
                    reason=reason,
                )
            previous = record.chain_hash
            expected_index += 1
        return ChainVerificationResult(
            valid=True,
            matter_id=matter_id,
            checked_count=len(rows),
            head_hash=previous if rows else GENESIS_HASH,
        )
