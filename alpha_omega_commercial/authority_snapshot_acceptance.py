from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from authority_snapshot import (
    CommercialAuthoritySnapshot,
    CommercialAuthoritySnapshotValidator,
    digest,
    parse_utc,
    valid_sha256,
)


@dataclass(frozen=True)
class AuthoritySnapshotAcceptanceDecision:
    valid: bool
    idempotent: bool
    reasons: tuple[str, ...]
    snapshot_id: str | None
    snapshot_sha256: str | None
    latest_snapshot_id: str | None
    latest_snapshot_sha256: str | None


class AuthoritySnapshotAcceptanceLedger:
    """Durable anti-rollback ledger for live commercial authority snapshots.

    Snapshot validity alone is not enough: an older, still-unexpired snapshot must
    not be replayed after a newer snapshot has already been accepted. This ledger
    maintains a hash-linked, restart-safe acceptance history and rejects temporal
    rollback, snapshot-ID equivocation and source-ledger rollback.
    """

    FILE_NAME = "authority_snapshot_acceptance_ledger.jsonl"

    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / self.FILE_NAME
        self.entries = self._load_entries()

    @staticmethod
    def _entry_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(entry)
        payload.pop("entry_sha256", None)
        return payload

    @classmethod
    def _expected_entry_sha256(cls, entry: Mapping[str, Any]) -> str:
        return digest(cls._entry_payload(entry))

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        entries: list[dict[str, Any]] = []
        previous = "GENESIS"
        seen_snapshot_ids: dict[str, str] = {}
        for line_number, raw_line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not raw_line.strip():
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"authority snapshot acceptance ledger invalid JSON at line {line_number}"
                ) from exc

            expected_sequence = len(entries) + 1
            if entry.get("sequence") != expected_sequence:
                raise RuntimeError("authority snapshot acceptance ledger sequence invalid")
            if entry.get("previous_entry_sha256") != previous:
                raise RuntimeError("authority snapshot acceptance ledger chain invalid")
            if entry.get("entry_sha256") != self._expected_entry_sha256(entry):
                raise RuntimeError("authority snapshot acceptance ledger hash invalid")

            snapshot_id = str(entry.get("snapshot_id", ""))
            snapshot_sha256 = str(entry.get("snapshot_sha256", ""))
            if not snapshot_id:
                raise RuntimeError("authority snapshot acceptance ledger snapshot id missing")
            if not valid_sha256(snapshot_sha256):
                raise RuntimeError("authority snapshot acceptance ledger snapshot hash invalid")
            prior_hash = seen_snapshot_ids.get(snapshot_id)
            if prior_hash is not None and prior_hash != snapshot_sha256:
                raise RuntimeError("authority snapshot acceptance ledger id conflict")
            seen_snapshot_ids[snapshot_id] = snapshot_sha256

            try:
                parse_utc(str(entry["generated_at"]))
                parse_utc(str(entry["accepted_at"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    "authority snapshot acceptance ledger timestamp invalid"
                ) from exc

            previous = str(entry["entry_sha256"])
            entries.append(entry)
        return entries

    def _validate_snapshot(
        self,
        snapshot: CommercialAuthoritySnapshot,
        validator: CommercialAuthoritySnapshotValidator,
        *,
        required_scope: Mapping[str, tuple[str, ...]],
        now: str,
    ) -> list[str]:
        reasons: list[str] = []
        if not snapshot.domains:
            reasons.append("AUTHORITY_SNAPSHOT_DOMAINS_EMPTY")
        if not valid_sha256(snapshot.source_ledger_head):
            reasons.append("SOURCE_LEDGER_HEAD_HASH_INVALID")
        for domain in sorted(snapshot.domains):
            decision = validator.validate_domain(
                domain,
                required_scope=required_scope.get(domain, ()),
                now=now,
            )
            reasons.extend(decision.reasons)
        return sorted(set(reasons))

    def preview(
        self,
        snapshot: CommercialAuthoritySnapshot | None,
        validator: CommercialAuthoritySnapshotValidator,
        *,
        required_scope: Mapping[str, tuple[str, ...]],
        now: str,
    ) -> AuthoritySnapshotAcceptanceDecision:
        latest = self.entries[-1] if self.entries else None
        if snapshot is None:
            return AuthoritySnapshotAcceptanceDecision(
                valid=False,
                idempotent=False,
                reasons=("AUTHORITY_SNAPSHOT_REQUIRED",),
                snapshot_id=None,
                snapshot_sha256=None,
                latest_snapshot_id=latest.get("snapshot_id") if latest else None,
                latest_snapshot_sha256=latest.get("snapshot_sha256") if latest else None,
            )

        reasons = self._validate_snapshot(
            snapshot,
            validator,
            required_scope=required_scope,
            now=now,
        )
        if not reasons:
            same_hash = next(
                (
                    entry
                    for entry in self.entries
                    if entry["snapshot_sha256"] == snapshot.snapshot_sha256
                ),
                None,
            )
            if same_hash is not None:
                return AuthoritySnapshotAcceptanceDecision(
                    valid=True,
                    idempotent=True,
                    reasons=(),
                    snapshot_id=snapshot.snapshot_id,
                    snapshot_sha256=snapshot.snapshot_sha256,
                    latest_snapshot_id=latest.get("snapshot_id") if latest else None,
                    latest_snapshot_sha256=latest.get("snapshot_sha256") if latest else None,
                )

            same_id = next(
                (
                    entry
                    for entry in self.entries
                    if entry["snapshot_id"] == snapshot.snapshot_id
                ),
                None,
            )
            if same_id is not None:
                reasons.append("AUTHORITY_SNAPSHOT_ID_CONFLICT")

            if latest is not None:
                candidate_generated = parse_utc(snapshot.generated_at)
                latest_generated = parse_utc(str(latest["generated_at"]))
                if candidate_generated < latest_generated:
                    reasons.append("AUTHORITY_SNAPSHOT_ROLLBACK_DETECTED")
                elif candidate_generated == latest_generated:
                    reasons.append("AUTHORITY_SNAPSHOT_EQUIVOCATION_DETECTED")

                earlier_head = next(
                    (
                        entry
                        for entry in self.entries[:-1]
                        if entry["source_ledger_head"] == snapshot.source_ledger_head
                    ),
                    None,
                )
                if (
                    earlier_head is not None
                    and snapshot.source_ledger_head != latest["source_ledger_head"]
                ):
                    reasons.append("SOURCE_LEDGER_HEAD_ROLLBACK_DETECTED")

        return AuthoritySnapshotAcceptanceDecision(
            valid=not reasons,
            idempotent=False,
            reasons=tuple(sorted(set(reasons))),
            snapshot_id=snapshot.snapshot_id,
            snapshot_sha256=snapshot.snapshot_sha256,
            latest_snapshot_id=latest.get("snapshot_id") if latest else None,
            latest_snapshot_sha256=latest.get("snapshot_sha256") if latest else None,
        )

    def accept(
        self,
        snapshot: CommercialAuthoritySnapshot | None,
        validator: CommercialAuthoritySnapshotValidator,
        *,
        required_scope: Mapping[str, tuple[str, ...]],
        now: str,
    ) -> dict[str, Any]:
        decision = self.preview(
            snapshot,
            validator,
            required_scope=required_scope,
            now=now,
        )
        if not decision.valid:
            raise PermissionError(
                "authority snapshot acceptance failed: " + ",".join(decision.reasons)
            )
        if decision.idempotent:
            return next(
                dict(entry)
                for entry in self.entries
                if entry["snapshot_sha256"] == decision.snapshot_sha256
            )
        assert snapshot is not None

        previous = self.entries[-1]["entry_sha256"] if self.entries else "GENESIS"
        entry: dict[str, Any] = {
            "sequence": len(self.entries) + 1,
            "event": "AUTHORITY_SNAPSHOT_ACCEPTED",
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_sha256": snapshot.snapshot_sha256,
            "generated_at": snapshot.generated_at,
            "expires_at": snapshot.expires_at,
            "source_projection_sha256": snapshot.source_projection_sha256,
            "source_ledger_head": snapshot.source_ledger_head,
            "domain_evidence_sha256": {
                domain: lease.evidence_sha256
                for domain, lease in sorted(snapshot.domains.items())
            },
            "accepted_at": now,
            "previous_entry_sha256": previous,
        }
        entry["entry_sha256"] = self._expected_entry_sha256(entry)

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.entries.append(entry)
        return dict(entry)

    def readback(
        self,
        snapshot: CommercialAuthoritySnapshot | None,
        validator: CommercialAuthoritySnapshotValidator,
        *,
        required_scope: Mapping[str, tuple[str, ...]],
        now: str,
    ) -> dict[str, Any]:
        decision = self.preview(
            snapshot,
            validator,
            required_scope=required_scope,
            now=now,
        )
        latest = self.entries[-1] if self.entries else None
        return {
            "ledger_file": self.FILE_NAME,
            "integrity": "VERIFIED" if self.entries or not self.path.exists() else "EMPTY",
            "entries": len(self.entries),
            "latest_snapshot_id": latest["snapshot_id"] if latest else None,
            "latest_snapshot_sha256": latest["snapshot_sha256"] if latest else None,
            "latest_entry_sha256": latest["entry_sha256"] if latest else "GENESIS",
            "candidate_valid": decision.valid,
            "candidate_idempotent": decision.idempotent,
            "candidate_reasons": list(decision.reasons),
            "anti_rollback_enforced": True,
            "snapshot_id_conflict_rejected": True,
            "source_ledger_rollback_rejected": True,
        }
