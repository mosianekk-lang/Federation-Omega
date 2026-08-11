from __future__ import annotations

import json
import mimetypes
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .hashing import atomic_write_json, merkle_root, sha256_bytes, sha256_file, stable_record_hash
from .models import CustodyEvent, EvidenceItem, HumanReview, TranscriptSegment, TranslationRecord, UnitReceipt


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LedgerError(RuntimeError):
    pass


class EvidenceLedger:
    """Append-only, content-addressed evidence ledger with a custody hash chain."""

    CONTRACT = "EVIDENCEOPS_AUDIO_EVIDENCE_LEDGER_V4"

    def __init__(self, workspace: str | Path):
        self.root = Path(workspace)
        self.objects_dir = self.root / "objects"
        self.receipts_dir = self.root / "receipts"
        self.manifests_dir = self.root / "manifests"
        self.index_dir = self.root / "index"
        self.ledger_dir = self.root / "ledger"
        self.workspace_manifest_path = self.manifests_dir / "workspace.json"
        self.items_path = self.ledger_dir / "evidence_items.jsonl"
        self.custody_path = self.ledger_dir / "custody_events.jsonl"
        self.units_path = self.ledger_dir / "unit_receipts.jsonl"
        self.segments_path = self.ledger_dir / "transcript_segments.jsonl"
        self.translations_path = self.ledger_dir / "translations.jsonl"
        self.reviews_path = self.ledger_dir / "human_reviews.jsonl"

    @classmethod
    def create(
        cls,
        workspace: str | Path,
        *,
        matter: str,
        case_wall: str,
        owner: str,
        confidentiality: str = "PRIVATE_EVIDENCE",
    ) -> "EvidenceLedger":
        ledger = cls(workspace)
        for folder in (ledger.objects_dir, ledger.receipts_dir, ledger.manifests_dir, ledger.index_dir, ledger.ledger_dir):
            folder.mkdir(parents=True, exist_ok=True)
        if ledger.workspace_manifest_path.exists():
            existing = ledger.read_workspace_manifest()
            if (existing.get("matter"), existing.get("case_wall"), existing.get("owner")) != (matter, case_wall, owner):
                raise LedgerError("workspace identity mismatch")
            return ledger
        atomic_write_json(
            ledger.workspace_manifest_path,
            {
                "contract": cls.CONTRACT,
                "workspace_id": f"AEW-{uuid.uuid4().hex[:16]}",
                "matter": matter,
                "case_wall": case_wall,
                "owner": owner,
                "confidentiality": confidentiality,
                "created_at": utc_now(),
                "truth_boundary": (
                    "Automated processing creates working evidence records, not a certified verbatim transcript, "
                    "biometric speaker identity or legal admissibility finding."
                ),
            },
        )
        return ledger

    def read_workspace_manifest(self) -> dict[str, Any]:
        return json.loads(self.workspace_manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LedgerError(f"invalid JSONL at {path}:{number}") from exc
        return rows

    @staticmethod
    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    def evidence_items(self): return self._read_jsonl(self.items_path)
    def custody_events(self): return self._read_jsonl(self.custody_path)
    def unit_receipts(self): return self._read_jsonl(self.units_path)
    def transcript_segments(self): return self._read_jsonl(self.segments_path)
    def translations(self): return self._read_jsonl(self.translations_path)
    def human_reviews(self): return self._read_jsonl(self.reviews_path)

    def find_item(self, item_id: str) -> dict[str, Any]:
        for item in self.evidence_items():
            if item["item_id"] == item_id:
                return item
        raise LedgerError(f"unknown evidence item: {item_id}")

    def object_path(self, digest: str) -> Path:
        return self.objects_dir / digest[:2] / digest

    def _record_custody(self, *, actor: str, action: str, item_ids: Iterable[str], details: dict[str, Any]) -> None:
        prior = self.custody_events()
        payload = {
            "event_id": f"CUE-{uuid.uuid4().hex[:16]}",
            "occurred_at": utc_now(),
            "actor": actor,
            "action": action,
            "item_ids": tuple(item_ids),
            "details": details,
            "previous_event_hash": prior[-1]["event_hash"] if prior else None,
        }
        event = CustodyEvent(event_hash=stable_record_hash(payload), **payload)
        self._append_jsonl(self.custody_path, event.to_dict())

    def ingest_file(
        self,
        path: str | Path,
        *,
        item_id: str,
        evidence_class: str,
        actor: str,
        parent_item_ids: Iterable[str] = (),
        transformation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        if any(row["item_id"] == item_id for row in self.evidence_items()):
            raise LedgerError(f"duplicate item_id: {item_id}")
        parents = tuple(parent_item_ids)
        for parent in parents:
            self.find_item(parent)
        digest = sha256_file(source)
        carrier = self.object_path(digest)
        carrier.parent.mkdir(parents=True, exist_ok=True)
        if not carrier.exists():
            shutil.copy2(source, carrier)
        if sha256_file(carrier) != digest:
            raise LedgerError("content-addressed copy hash mismatch")
        item_metadata = dict(metadata or {})
        item_metadata.setdefault("original_name", source.name)
        item_metadata.setdefault("mime_type", mimetypes.guess_type(source.name)[0] or "application/octet-stream")
        item = EvidenceItem(
            item_id=item_id,
            evidence_class=evidence_class,
            path=str(carrier.relative_to(self.root)),
            sha256=digest,
            size_bytes=source.stat().st_size,
            created_at=utc_now(),
            parent_item_ids=parents,
            transformation=dict(transformation or {}),
            metadata=item_metadata,
        )
        self._append_jsonl(self.items_path, item.to_dict())
        self._record_custody(
            actor=actor,
            action="INGEST_FILE",
            item_ids=(item_id,),
            details={"sha256": digest, "size_bytes": item.size_bytes, "evidence_class": evidence_class, "parents": parents},
        )
        return item

    def register_external_item(
        self,
        *,
        item_id: str,
        evidence_class: str,
        declared_sha256: str,
        declared_size_bytes: int,
        external_uri: str,
        actor: str,
        parent_item_ids: Iterable[str] = (),
        transformation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        if any(row["item_id"] == item_id for row in self.evidence_items()):
            raise LedgerError(f"duplicate item_id: {item_id}")
        if len(declared_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in declared_sha256):
            raise LedgerError("declared_sha256 must be hexadecimal SHA-256")
        parents = tuple(parent_item_ids)
        for parent in parents:
            self.find_item(parent)
        item_metadata = dict(metadata or {})
        item_metadata.update({"external_uri": external_uri, "hash_verification_state": "DECLARED_EXTERNAL_NOT_MATERIALIZED"})
        item = EvidenceItem(
            item_id=item_id,
            evidence_class=evidence_class,
            path=f"external:{external_uri}",
            sha256=declared_sha256.lower(),
            size_bytes=int(declared_size_bytes),
            created_at=utc_now(),
            parent_item_ids=parents,
            transformation=dict(transformation or {}),
            metadata=item_metadata,
        )
        self._append_jsonl(self.items_path, item.to_dict())
        self._record_custody(
            actor=actor,
            action="REGISTER_EXTERNAL_REFERENCE",
            item_ids=(item_id,),
            details={"declared_sha256": item.sha256, "external_uri": external_uri, "verification_state": "UNMATERIALIZED"},
        )
        return item

    def register_unit_receipt(self, receipt: UnitReceipt, *, actor: str) -> None:
        source = self.find_item(receipt.source_item_id)
        if source["sha256"] != receipt.source_sha256:
            raise LedgerError("unit source hash mismatch")
        if any(row["unit_id"] == receipt.unit_id for row in self.unit_receipts()):
            raise LedgerError(f"duplicate unit receipt: {receipt.unit_id}")
        if receipt.state == "EMITTED_SEGMENTS" and receipt.segment_count <= 0:
            raise LedgerError("emitting unit requires segment_count > 0")
        if receipt.state == "ZERO_SEGMENT" and receipt.segment_count != 0:
            raise LedgerError("zero-segment unit requires segment_count = 0")
        if receipt.state == "FAILED" and not receipt.error:
            raise LedgerError("failed unit requires error")
        self._append_jsonl(self.units_path, receipt.to_dict())
        self._record_custody(
            actor=actor,
            action="REGISTER_UNIT_RECEIPT",
            item_ids=(receipt.source_item_id,),
            details={"unit_id": receipt.unit_id, "state": receipt.state, "segment_count": receipt.segment_count, "raw_response_sha256": receipt.raw_response_sha256},
        )

    def register_transcript_segments(self, segments: Iterable[TranscriptSegment], *, actor: str) -> int:
        unit_map = {row["unit_id"]: row for row in self.unit_receipts()}
        existing = {row["segment_id"] for row in self.transcript_segments()}
        staged, counts = [], {}
        for segment in segments:
            if segment.segment_id in existing:
                raise LedgerError(f"duplicate segment_id: {segment.segment_id}")
            unit = unit_map.get(segment.unit_id)
            if not unit or unit["state"] != "EMITTED_SEGMENTS":
                raise LedgerError(f"segment references non-emitting unit: {segment.unit_id}")
            if segment.source_item_id != unit["source_item_id"]:
                raise LedgerError("segment source differs from unit source")
            if segment.end_seconds < segment.start_seconds:
                raise LedgerError("segment end precedes start")
            staged.append(segment)
            counts[segment.unit_id] = counts.get(segment.unit_id, 0) + 1
        for unit_id, count in counts.items():
            if int(unit_map[unit_id]["segment_count"]) != count:
                raise LedgerError(f"unit {unit_id} segment count mismatch")
        for segment in staged:
            self._append_jsonl(self.segments_path, segment.to_dict())
        if staged:
            self._record_custody(
                actor=actor,
                action="REGISTER_TRANSCRIPT_SEGMENTS",
                item_ids=tuple(sorted({row.source_item_id for row in staged})),
                details={"segment_count": len(staged), "unit_count": len(counts)},
            )
        return len(staged)

    def register_translation(self, translation: TranslationRecord, *, actor: str) -> None:
        segments = {row["segment_id"]: row for row in self.transcript_segments()}
        segment = segments.get(translation.segment_id)
        if not segment:
            raise LedgerError("translation references missing segment")
        if sha256_bytes(segment["original_text"].encode("utf-8")) != translation.source_text_sha256:
            raise LedgerError("translation source text hash mismatch")
        if translation.source_language != segment["source_language"]:
            raise LedgerError("translation source language mismatch")
        if any(row["translation_id"] == translation.translation_id for row in self.translations()):
            raise LedgerError("duplicate translation_id")
        self._append_jsonl(self.translations_path, translation.to_dict())
        self._record_custody(
            actor=actor,
            action="REGISTER_TRANSLATION",
            item_ids=(segment["source_item_id"],),
            details={"translation_id": translation.translation_id, "segment_id": translation.segment_id, "target_language": translation.target_language},
        )

    def register_human_review(self, review: HumanReview, *, actor: str) -> None:
        segments = {row["segment_id"]: row for row in self.transcript_segments()}
        if review.segment_id not in segments:
            raise LedgerError("review references missing segment")
        if review.audio_window_item_id:
            if self.find_item(review.audio_window_item_id)["sha256"] != review.audio_window_sha256:
                raise LedgerError("review audio window hash mismatch")
        if review.state == "HUMAN_VERIFIED_SOURCE_TEXT" and not review.verified_source_text:
            raise LedgerError("verified source text required")
        if review.state == "HUMAN_VERIFIED_TRANSLATION" and not review.verified_translation_text:
            raise LedgerError("verified translation text required")
        if any(row["review_id"] == review.review_id for row in self.human_reviews()):
            raise LedgerError("duplicate review_id")
        self._append_jsonl(self.reviews_path, review.to_dict())
        self._record_custody(
            actor=actor,
            action="REGISTER_HUMAN_REVIEW",
            item_ids=tuple(filter(None, (segments[review.segment_id]["source_item_id"], review.audio_window_item_id))),
            details={"review_id": review.review_id, "segment_id": review.segment_id, "state": review.state, "reviewer": review.reviewer},
        )

    def audit_unit_accounting(self) -> dict[str, Any]:
        units, segments = self.unit_receipts(), self.transcript_segments()
        by_unit: dict[str, int] = {}
        for segment in segments:
            by_unit[segment["unit_id"]] = by_unit.get(segment["unit_id"], 0) + 1
        emitted = [row for row in units if row["state"] == "EMITTED_SEGMENTS"]
        zero = [row for row in units if row["state"] == "ZERO_SEGMENT"]
        failed = [row for row in units if row["state"] == "FAILED"]
        defects = []
        for row in emitted:
            actual = by_unit.get(row["unit_id"], 0)
            if actual != row["segment_count"]:
                defects.append({"unit_id": row["unit_id"], "defect": "SEGMENT_COUNT_MISMATCH", "declared": row["segment_count"], "actual": actual})
        for row in zero + failed:
            if by_unit.get(row["unit_id"], 0):
                defects.append({"unit_id": row["unit_id"], "defect": "NON_EMITTING_UNIT_HAS_SEGMENTS"})
        return {
            "contract": "ZERO_SEGMENT_UNIT_ACCOUNTING_V1",
            "state": "PASS" if not defects else "FAIL",
            "processed_unit_count": len(units),
            "emitted_segment_unit_count": len(emitted),
            "zero_segment_unit_count": len(zero),
            "failed_unit_count": len(failed),
            "structured_segment_count": len(segments),
            "zero_segment_unit_ids": [row["unit_id"] for row in zero],
            "failed_unit_ids": [row["unit_id"] for row in failed],
            "invariant": "processed_unit_count = emitted_segment_unit_count + zero_segment_unit_count + failed_unit_count",
            "defects": defects,
        }

    def verify_custody_chain(self) -> dict[str, Any]:
        defects, previous = [], None
        events = self.custody_events()
        for index, event in enumerate(events):
            if event.get("previous_event_hash") != previous:
                defects.append({"index": index, "event_id": event.get("event_id"), "defect": "PREVIOUS_HASH_MISMATCH"})
            observed = stable_record_hash(event, exclude=("event_hash",))
            if observed != event.get("event_hash"):
                defects.append({"index": index, "event_id": event.get("event_id"), "defect": "EVENT_HASH_MISMATCH"})
            previous = event.get("event_hash")
        return {"contract": "EVIDENCEOPS_CUSTODY_HASH_CHAIN_V1", "state": "PASS" if not defects else "FAIL", "event_count": len(events), "head_hash": previous, "defects": defects}

    def seal_snapshot(self, *, actor: str, note: str = "") -> dict[str, Any]:
        files = [self.workspace_manifest_path, self.items_path, self.custody_path, self.units_path, self.segments_path, self.translations_path, self.reviews_path]
        entries = [
            {"path": str(path.relative_to(self.root)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in files if path.exists()
        ]
        receipt = {
            "contract": "EVIDENCEOPS_AUDIO_WORKSPACE_SEAL_V1",
            "sealed_at": utc_now(),
            "actor": actor,
            "workspace": self.read_workspace_manifest(),
            "entries": entries,
            "merkle_root_sha256": merkle_root(row["sha256"] for row in entries),
            "custody_chain": self.verify_custody_chain(),
            "unit_accounting": self.audit_unit_accounting(),
            "note": note,
            "truth_boundary": "The seal proves listed files and hashes, not transcript accuracy, speaker identity, translation accuracy or admissibility.",
        }
        path = self.receipts_dir / f"workspace-seal-{receipt['sealed_at'].replace(':', '').replace('+', '_')}.json"
        atomic_write_json(path, receipt)
        self._record_custody(actor=actor, action="SEAL_WORKSPACE_SNAPSHOT", item_ids=(), details={"receipt": str(path.relative_to(self.root)), "merkle_root_sha256": receipt["merkle_root_sha256"]})
        return receipt
