from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .ledger import EvidenceLedger, utc_now
from .models import TranscriptSegment, UnitReceipt


def import_legacy_whisper_run(
    ledger: EvidenceLedger,
    *,
    job_manifest_path: str | Path,
    structured_transcript_path: str | Path,
    actor: str,
    source_item_id: str,
    source_language: str = "en",
) -> dict[str, Any]:
    """Import a legacy run while preserving missing-provider-receipt limitations."""
    job = json.loads(Path(job_manifest_path).read_text(encoding="utf-8"))
    structured = json.loads(Path(structured_transcript_path).read_text(encoding="utf-8"))
    source = ledger.register_external_item(
        item_id=source_item_id,
        evidence_class="PRIMARY_SOURCE",
        declared_sha256=job["source"]["sha256"],
        declared_size_bytes=int(job["source"]["size_bytes"]),
        external_uri=f"gdrive://{job['source']['drive_id']}",
        actor=actor,
        metadata={
            "file": job["source"]["file"],
            "duration_seconds": job["source"]["duration_seconds"],
            "legacy_run_id": job.get("run_id"),
            "hash_verification_state": "DECLARED_LEGACY_CONTROL_NOT_MATERIALIZED",
        },
    )
    chunk_items = {}
    for chunk in job["chunks"]:
        sequence = int(chunk["sequence"])
        chunk_items[sequence] = ledger.register_external_item(
            item_id=f"{source_item_id}-CHUNK-{sequence:03d}",
            evidence_class="DERIVATIVE",
            declared_sha256=chunk["sha256"],
            declared_size_bytes=int(chunk["size_bytes"]),
            external_uri=f"gdrive://{chunk['drive_id']}",
            actor=actor,
            parent_item_ids=(source.item_id,),
            transformation={
                "operation": "LEGACY_PROVIDER_WINDOW_SPLIT",
                "start_seconds": chunk["start_seconds"],
                "end_seconds": chunk["end_seconds"],
                "duration_seconds": chunk["duration_seconds"],
            },
            metadata={"file": chunk["file"], "legacy_run_id": job.get("run_id")},
        )
    segment_counts = Counter(row["unit_id"] for row in structured["segments"])
    expected_units = 0
    zero_segment_ids = []
    for chunk in job["chunks"]:
        sequence = int(chunk["sequence"])
        unit_count = math.ceil(float(chunk["duration_seconds"]) / 60.0)
        expected_units += unit_count
        for unit_number in range(1, unit_count + 1):
            unit_id = f"unit-{sequence:03d}-{unit_number:02d}"
            count = segment_counts.get(unit_id, 0)
            if count == 0:
                zero_segment_ids.append(unit_id)
            start = float(chunk["start_seconds"]) + (unit_number - 1) * 60.0
            end = min(float(chunk["end_seconds"]), start + 60.0)
            item = chunk_items[sequence]
            ledger.register_unit_receipt(
                UnitReceipt(
                    unit_id=unit_id,
                    source_item_id=item.item_id,
                    source_sha256=item.sha256,
                    provider="legacy_whisper_cpp_import",
                    architecture_family="whisper_encoder_decoder",
                    start_seconds=round(start, 6),
                    end_seconds=round(end, 6),
                    state="EMITTED_SEGMENTS" if count else "ZERO_SEGMENT",
                    segment_count=count,
                    raw_response_sha256=None,
                    command_receipt_sha256=None,
                    provider_exit_code=0,
                    created_at=utc_now(),
                    language=source_language,
                    metadata={"legacy_import": True, "provider_native_receipt_state": "MISSING"},
                ),
                actor=actor,
            )
    converted = []
    for row in structured["segments"]:
        sequence = int(row["source_chunk_sequence"])
        converted.append(
            TranscriptSegment(
                segment_id=row["segment_id"],
                unit_id=row["unit_id"],
                source_item_id=chunk_items[sequence].item_id,
                start_seconds=float(row["absolute_start_seconds"]),
                end_seconds=float(row["absolute_end_seconds"]),
                original_text=row.get("cleaned_text") or row.get("raw_text") or "",
                source_language=source_language,
                provider=structured.get("model", "legacy_whisper_cpp"),
                architecture_family="whisper_encoder_decoder",
                confidence=(float(row["mean_token_probability"]) if row.get("mean_token_probability") is not None else None),
                speaker_label=row.get("speaker"),
                speaker_role=None,
                word_timestamps_present=False,
                raw_response_sha256=None,
                metadata={
                    "legacy_raw_text": row.get("raw_text"),
                    "original_offsets": row.get("original_offsets"),
                    "timeline_anomaly": row.get("timeline_anomaly"),
                    "provider_native_receipt_state": "MISSING",
                    "quotation_state": "BLOCKED_PENDING_HUMAN_LISTENING",
                },
            )
        )
    ledger.register_transcript_segments(converted, actor=actor)
    return {
        "contract": "EVIDENCEOPS_LEGACY_AUDIO_IMPORT_V1",
        "state": "IMPORTED_WITH_PROVIDER_RECEIPT_LIMITATION",
        "source_item_id": source.item_id,
        "chunk_count": len(chunk_items),
        "processed_unit_count": expected_units,
        "emitted_segment_unit_count": expected_units - len(zero_segment_ids),
        "zero_segment_unit_count": len(zero_segment_ids),
        "zero_segment_unit_ids": zero_segment_ids,
        "segment_count": len(converted),
        "unit_accounting": ledger.audit_unit_accounting(),
        "truth_boundary": (
            "Legacy provider responses and command receipts remain missing unless separately materialized. "
            "This import makes the structured transcript searchable without upgrading its quotation or certification state."
        ),
    }
