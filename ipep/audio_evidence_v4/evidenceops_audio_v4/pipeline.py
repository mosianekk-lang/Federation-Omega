from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable

from .gates import quotation_release_gate, transcript_certification_gate
from .hashing import atomic_write_json
from .index import EvidenceIndex
from .ledger import EvidenceLedger, LedgerError, utc_now
from .media import extract_audio_window, normalize_audio, probe_audio, split_audio
from .models import HumanReview, QuoteRequest, TranscriptSegment
from .providers import TranslationAdapter, WhisperCppUnitAdapter


class AudioEvidenceCompletionPipeline:
    """Governed end-to-end EvidenceOps audio completion orchestrator."""

    CONTRACT = "EVIDENCEOPS_AUDIO_EVIDENCE_COMPLETION_V4"

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    @classmethod
    def create(
        cls,
        workspace: str | Path,
        *,
        matter: str,
        case_wall: str,
        owner: str,
        confidentiality: str = "PRIVATE_EVIDENCE",
    ) -> "AudioEvidenceCompletionPipeline":
        return cls(
            EvidenceLedger.create(
                workspace,
                matter=matter,
                case_wall=case_wall,
                owner=owner,
                confidentiality=confidentiality,
            )
        )

    def collect_source(
        self,
        source_path: str | Path,
        *,
        source_item_id: str,
        actor: str,
        capture_metadata: dict[str, Any],
        make_preservation_copy: bool = True,
    ) -> dict[str, Any]:
        probe = probe_audio(source_path)
        source = self.ledger.ingest_file(
            source_path,
            item_id=source_item_id,
            evidence_class="PRIMARY_SOURCE",
            actor=actor,
            metadata={**capture_metadata, "audio_probe": probe.to_dict()},
        )
        preservation = None
        if make_preservation_copy:
            preservation_path = self.ledger.root / "working" / f"preservation-{Path(source_path).name}"
            preservation_path.parent.mkdir(parents=True, exist_ok=True)
            preservation_path.write_bytes(Path(source_path).read_bytes())
            preservation = self.ledger.ingest_file(
                preservation_path,
                item_id=f"{source_item_id}-PRESERVATION",
                evidence_class="PRESERVATION_COPY",
                actor=actor,
                parent_item_ids=(source_item_id,),
                transformation={"operation": "BYTE_FOR_BYTE_COPY"},
                metadata={"purpose": "preservation copy"},
            )
            if preservation.sha256 != source.sha256:
                raise LedgerError("preservation copy hash does not match source")
        return {
            "contract": self.CONTRACT,
            "state": "SOURCE_COLLECTED_AND_PRESERVED" if preservation else "SOURCE_COLLECTED",
            "source": source.to_dict(),
            "preservation_copy": preservation.to_dict() if preservation else None,
        }

    def prepare_units(
        self,
        *,
        source_item_id: str,
        actor: str,
        unit_seconds: float = 60.0,
    ) -> list[dict[str, Any]]:
        source = self.ledger.find_item(source_item_id)
        source_path = self.ledger.root / source["path"]
        working = self.ledger.root / "working"
        normalized_path = working / f"{source_item_id}-normalized.flac"
        normalization = normalize_audio(source_path, normalized_path)
        normalized = self.ledger.ingest_file(
            normalized_path,
            item_id=f"{source_item_id}-NORMALIZED",
            evidence_class="DERIVATIVE",
            actor=actor,
            parent_item_ids=(source_item_id,),
            transformation={
                "operation": "FFMPEG_NORMALIZE",
                "parameters": {"sample_rate": 16000, "channels": 1, "codec": "flac"},
                "receipt": normalization,
            },
            metadata={"purpose": "provider-normalized derivative"},
        )
        unit_records = split_audio(
            normalized_path,
            working / f"{source_item_id}-units",
            unit_seconds=unit_seconds,
            prefix=source_item_id.lower(),
        )
        result = []
        for unit in unit_records:
            unit_id = f"{source_item_id}-U{unit['sequence']:04d}"
            item = self.ledger.ingest_file(
                unit["path"],
                item_id=unit_id,
                evidence_class="DERIVATIVE",
                actor=actor,
                parent_item_ids=(normalized.item_id,),
                transformation={
                    "operation": "FFMPEG_FIXED_WINDOW_SPLIT",
                    "start_seconds": unit["start_seconds"],
                    "end_seconds": unit["end_seconds"],
                    "unit_seconds": unit_seconds,
                },
                metadata={"unit_sequence": unit["sequence"]},
            )
            result.append(
                {
                    "unit_id": unit_id,
                    "item": item.to_dict(),
                    "start_seconds": unit["start_seconds"],
                    "end_seconds": unit["end_seconds"],
                }
            )
        atomic_write_json(
            self.ledger.manifests_dir / f"{source_item_id}-unit-plan.json",
            {
                "contract": "EVIDENCEOPS_AUDIO_UNIT_PLAN_V1",
                "source_item_id": source_item_id,
                "normalized_item_id": normalized.item_id,
                "unit_seconds": unit_seconds,
                "unit_count": len(result),
                "units": result,
            },
        )
        return result

    def automated_transcribe(
        self,
        *,
        units: Iterable[dict[str, Any]],
        adapter: WhisperCppUnitAdapter,
        actor: str,
    ) -> dict[str, Any]:
        unit_count = 0
        segment_count = 0
        states: dict[str, int] = {"EMITTED_SEGMENTS": 0, "ZERO_SEGMENT": 0, "FAILED": 0}
        for unit in units:
            item = unit["item"]
            path = self.ledger.root / item["path"]
            receipt, segments = adapter.transcribe_unit(
                unit_path=path,
                source_item_id=item["item_id"],
                source_sha256=item["sha256"],
                unit_id=item["item_id"],
                absolute_start=float(unit["start_seconds"]),
                absolute_end=float(unit["end_seconds"]),
                receipt_dir=self.ledger.receipts_dir / "provider-units",
            )
            self.ledger.register_unit_receipt(receipt, actor=actor)
            if segments:
                self.ledger.register_transcript_segments(segments, actor=actor)
            states[receipt.state] += 1
            unit_count += 1
            segment_count += len(segments)
        audit = self.ledger.audit_unit_accounting()
        return {
            "contract": "EVIDENCEOPS_AUTOMATED_TRANSCRIPTION_RUN_V1",
            "state": "COMPLETE_WITH_REVIEW_REQUIRED" if audit["state"] == "PASS" else "FAILED_ACCOUNTING_AUDIT",
            "provider": adapter.name,
            "unit_count": unit_count,
            "segment_count": segment_count,
            "unit_states": states,
            "accounting_audit": audit,
            "truth_boundary": "Automated transcription remains a working record until human verification gates pass.",
        }

    def import_segments_with_receipts(
        self,
        *,
        source_item_id: str,
        segments: Iterable[TranscriptSegment],
        unit_receipts: Iterable[Any],
        actor: str,
    ) -> dict[str, Any]:
        for receipt in unit_receipts:
            self.ledger.register_unit_receipt(receipt, actor=actor)
        count = self.ledger.register_transcript_segments(segments, actor=actor)
        return {
            "state": "IMPORTED",
            "source_item_id": source_item_id,
            "segment_count": count,
            "unit_accounting": self.ledger.audit_unit_accounting(),
        }

    def automated_translate(
        self,
        *,
        adapter: TranslationAdapter,
        target_language: str,
        actor: str,
        segment_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        existing = {(row["segment_id"], row["target_language"]) for row in self.ledger.translations()}
        translated = 0
        skipped = 0
        for segment in self.ledger.transcript_segments():
            if segment_ids is not None and segment["segment_id"] not in segment_ids:
                continue
            if segment["source_language"] == target_language:
                skipped += 1
                continue
            key = (segment["segment_id"], target_language)
            if key in existing:
                skipped += 1
                continue
            translation = adapter.translate(
                segment_id=segment["segment_id"],
                text=segment["original_text"],
                source_language=segment["source_language"],
                target_language=target_language,
                receipt_dir=self.ledger.receipts_dir / "translations",
            )
            self.ledger.register_translation(translation, actor=actor)
            translated += 1
        return {
            "contract": "EVIDENCEOPS_AUTOMATED_TRANSLATION_RUN_V1",
            "state": "COMPLETE_TRANSLATION_REVIEW_REQUIRED",
            "target_language": target_language,
            "translated_count": translated,
            "skipped_count": skipped,
            "truth_boundary": (
                "Machine translations are derivative aids. Original-language text is preserved and translated quotations "
                "remain blocked until bilingual human verification passes."
            ),
        }

    def create_review_window(
        self,
        *,
        source_item_id: str,
        segment_id: str,
        actor: str,
        padding_seconds: float = 2.0,
    ) -> dict[str, Any]:
        source = self.ledger.find_item(source_item_id)
        segment = next(
            (row for row in self.ledger.transcript_segments() if row["segment_id"] == segment_id),
            None,
        )
        if not segment:
            raise LedgerError(f"unknown segment: {segment_id}")
        start = max(0.0, float(segment["start_seconds"]) - padding_seconds)
        end = float(segment["end_seconds"]) + padding_seconds
        output_path = self.ledger.root / "working" / "review-windows" / f"{segment_id}.flac"
        receipt = extract_audio_window(
            self.ledger.root / source["path"],
            output_path,
            start_seconds=start,
            end_seconds=end,
        )
        item_id = f"WIN-{segment_id}"
        item = self.ledger.ingest_file(
            output_path,
            item_id=item_id,
            evidence_class="DERIVATIVE",
            actor=actor,
            parent_item_ids=(source_item_id,),
            transformation={
                "operation": "FFMPEG_REVIEW_WINDOW",
                "start_seconds": start,
                "end_seconds": end,
                "padding_seconds": padding_seconds,
            },
            metadata={"segment_id": segment_id, "review_purpose": True},
        )
        return {"item": item.to_dict(), "window": receipt}

    def register_review(
        self,
        *,
        segment_id: str,
        reviewer: str,
        state: str,
        actor: str,
        verified_source_text: str | None = None,
        verified_translation_text: str | None = None,
        speaker_role_verified: bool = False,
        legal_entities_verified: bool = False,
        audio_window_item_id: str | None = None,
        notes: str | None = None,
    ) -> HumanReview:
        window_sha = None
        if audio_window_item_id:
            window_sha = self.ledger.find_item(audio_window_item_id)["sha256"]
        review = HumanReview(
            review_id=f"REV-{uuid.uuid4().hex[:16]}",
            segment_id=segment_id,
            reviewer=reviewer,
            reviewed_at=utc_now(),
            state=state,  # type: ignore[arg-type]
            verified_source_text=verified_source_text,
            verified_translation_text=verified_translation_text,
            speaker_role_verified=speaker_role_verified,
            legal_entities_verified=legal_entities_verified,
            audio_window_item_id=audio_window_item_id,
            audio_window_sha256=window_sha,
            notes=notes,
        )
        self.ledger.register_human_review(review, actor=actor)
        return review

    def evaluate_quote(self, request: QuoteRequest) -> dict[str, Any]:
        segment = next(
            (row for row in self.ledger.transcript_segments() if row["segment_id"] == request.segment_id),
            None,
        )
        if not segment:
            raise LedgerError(f"unknown segment: {request.segment_id}")
        result = quotation_release_gate(request, source_language=segment["source_language"])
        output = self.ledger.receipts_dir / "quotation-gates" / f"{request.segment_id}-{request.quote_language}.json"
        atomic_write_json(output, result)
        result["receipt_path"] = str(output)
        return result

    def build_search_index(self) -> dict[str, Any]:
        index = EvidenceIndex(self.ledger.index_dir / "audio-evidence.sqlite")
        return index.build(self.ledger)

    def search(self, query: str, *, limit: int = 20, language: str | None = None, verified_only: bool = False):
        return EvidenceIndex(self.ledger.index_dir / "audio-evidence.sqlite").search(
            query,
            limit=limit,
            language=language,
            verified_only=verified_only,
        )

    def audit(self) -> dict[str, Any]:
        custody = self.ledger.verify_custody_chain()
        accounting = self.ledger.audit_unit_accounting()
        segments = self.ledger.transcript_segments()
        reviews = self.ledger.human_reviews()
        human_verified = {
            row["segment_id"]
            for row in reviews
            if row["state"] in {"HUMAN_VERIFIED_SOURCE_TEXT", "HUMAN_VERIFIED_TRANSLATION"}
        }
        certification = transcript_certification_gate(
            total_segments=len(segments),
            human_verified_segments=len(human_verified),
            custody_chain_passed=custody["state"] == "PASS",
            unit_accounting_passed=accounting["state"] == "PASS",
            signed_attestation_sha256=None,
            attesting_person=None,
            attesting_role=None,
        )
        return {
            "contract": self.CONTRACT,
            "state": "PASS_WITH_HUMAN_REVIEW_OPEN" if custody["state"] == accounting["state"] == "PASS" else "FAIL",
            "custody_chain": custody,
            "unit_accounting": accounting,
            "segment_count": len(segments),
            "translation_count": len(self.ledger.translations()),
            "human_review_count": len(reviews),
            "human_verified_segment_count": len(human_verified),
            "certification_gate": certification,
        }
