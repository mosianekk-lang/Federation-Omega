from __future__ import annotations

import json
import sys
from pathlib import Path

from evidenceops_audio_v4.gates import quotation_release_gate, transcript_certification_gate
from evidenceops_audio_v4.hashing import sha256_bytes, sha256_file
from evidenceops_audio_v4.index import EvidenceIndex
from evidenceops_audio_v4.ledger import EvidenceLedger, utc_now
from evidenceops_audio_v4.models import QuoteRequest, TranscriptSegment, UnitReceipt
from evidenceops_audio_v4.providers import CommandTranslationAdapter, WhisperCppConfig, WhisperCppUnitAdapter


def make_ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger.create(
        tmp_path / "workspace",
        matter="TEST-001",
        case_wall="CASE-WALL-TEST-001",
        owner="Kim Kagiso Mosiane",
    )


def add_source_and_units(ledger: EvidenceLedger, tmp_path: Path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"source-audio-bytes")
    source_item = ledger.ingest_file(source, item_id="SRC-001", evidence_class="PRIMARY_SOURCE", actor="tester")
    unit1 = tmp_path / "unit1.bin"
    unit2 = tmp_path / "unit2.bin"
    unit1.write_bytes(b"unit-one")
    unit2.write_bytes(b"unit-two")
    item1 = ledger.ingest_file(
        unit1,
        item_id="UNIT-001",
        evidence_class="DERIVATIVE",
        actor="tester",
        parent_item_ids=(source_item.item_id,),
        transformation={"operation": "TEST_SPLIT", "start": 0, "end": 60},
    )
    item2 = ledger.ingest_file(
        unit2,
        item_id="UNIT-002",
        evidence_class="DERIVATIVE",
        actor="tester",
        parent_item_ids=(source_item.item_id,),
        transformation={"operation": "TEST_SPLIT", "start": 60, "end": 120},
    )
    return source_item, item1, item2


def receipt(unit_id, item, state, count, raw):
    return UnitReceipt(
        unit_id=unit_id,
        source_item_id=unit_id,
        source_sha256=item.sha256,
        provider="test-asr",
        architecture_family="architecture-a",
        start_seconds=0 if unit_id == "UNIT-001" else 60,
        end_seconds=60 if unit_id == "UNIT-001" else 120,
        state=state,
        segment_count=count,
        raw_response_sha256=raw * 64,
        command_receipt_sha256="b" * 64,
        provider_exit_code=0,
        created_at=utc_now(),
        language="en",
    )


def test_hash_chained_custody_and_zero_segment_accounting(tmp_path: Path):
    ledger = make_ledger(tmp_path)
    _, unit1, unit2 = add_source_and_units(ledger, tmp_path)
    ledger.register_unit_receipt(receipt("UNIT-001", unit1, "EMITTED_SEGMENTS", 1, "a"), actor="tester")
    ledger.register_unit_receipt(receipt("UNIT-002", unit2, "ZERO_SEGMENT", 0, "c"), actor="tester")
    ledger.register_transcript_segments(
        [
            TranscriptSegment(
                segment_id="SEG-001",
                unit_id="UNIT-001",
                source_item_id="UNIT-001",
                start_seconds=0,
                end_seconds=2,
                original_text="The jurisdiction point was raised.",
                source_language="en",
                provider="test-asr",
                architecture_family="architecture-a",
                confidence=0.9,
                word_timestamps_present=True,
                raw_response_sha256="a" * 64,
            )
        ],
        actor="tester",
    )
    accounting = ledger.audit_unit_accounting()
    custody = ledger.verify_custody_chain()
    assert accounting["state"] == "PASS"
    assert accounting["processed_unit_count"] == 2
    assert accounting["emitted_segment_unit_count"] == 1
    assert accounting["zero_segment_unit_count"] == 1
    assert accounting["failed_unit_count"] == 0
    assert accounting["zero_segment_unit_ids"] == ["UNIT-002"]
    assert custody["state"] == "PASS"
    assert custody["event_count"] >= 6


def test_quote_and_certification_gates_never_self_certify():
    blocked = quotation_release_gate(
        QuoteRequest(
            segment_id="SEG-001",
            quote_language="en",
            supporting_architecture_families=("whisper_encoder_decoder",),
            word_timestamps_present=True,
            speaker_role_supported=False,
            legal_entities_verified=False,
            human_listened=False,
            source_text_human_verified=False,
            translation_human_verified=False,
            audio_window_sha256=None,
        ),
        source_language="en",
    )
    assert blocked["state"] == "BLOCKED_NOT_VERIFIED_FOR_QUOTATION"
    passed = quotation_release_gate(
        QuoteRequest(
            segment_id="SEG-001",
            quote_language="zu",
            supporting_architecture_families=("whisper_encoder_decoder", "nvidia_parakeet_tdt"),
            word_timestamps_present=True,
            speaker_role_supported=True,
            legal_entities_verified=True,
            human_listened=True,
            source_text_human_verified=True,
            translation_human_verified=True,
            audio_window_sha256="f" * 64,
        ),
        source_language="en",
    )
    assert passed["state"] == "VERIFIED_FOR_QUOTATION"
    certification = transcript_certification_gate(
        total_segments=1,
        human_verified_segments=1,
        custody_chain_passed=True,
        unit_accounting_passed=True,
        signed_attestation_sha256=None,
        attesting_person=None,
        attesting_role=None,
    )
    assert certification["state"] == "NOT_CERTIFIED"


def test_translation_preserves_source_and_builds_searchable_index(tmp_path: Path):
    ledger = make_ledger(tmp_path)
    _, unit1, _ = add_source_and_units(ledger, tmp_path)
    ledger.register_unit_receipt(receipt("UNIT-001", unit1, "EMITTED_SEGMENTS", 1, "a"), actor="tester")
    segment = TranscriptSegment(
        segment_id="SEG-001",
        unit_id="UNIT-001",
        source_item_id="UNIT-001",
        start_seconds=12.5,
        end_seconds=18.0,
        original_text="The employer raised a jurisdiction point.",
        source_language="en",
        provider="test-asr",
        architecture_family="architecture-a",
        confidence=0.88,
        word_timestamps_present=True,
        raw_response_sha256="a" * 64,
    )
    ledger.register_transcript_segments([segment], actor="tester")
    script = tmp_path / "translator.py"
    script.write_text(
        "import json,sys\n"
        "p=json.load(sys.stdin)\n"
        "print(json.dumps({'translated_text': 'Umqashi uphakamise udaba lwegunya.', 'model':'test-model'}))\n",
        encoding="utf-8",
    )
    adapter = CommandTranslationAdapter([sys.executable, str(script)])
    translation = adapter.translate(
        segment_id=segment.segment_id,
        text=segment.original_text,
        source_language="en",
        target_language="zu",
        receipt_dir=tmp_path / "translation-receipts",
    )
    ledger.register_translation(translation, actor="tester")
    assert ledger.transcript_segments()[0]["original_text"] == segment.original_text
    assert ledger.translations()[0]["translated_text"].startswith("Umqashi")
    assert ledger.translations()[0]["source_text_sha256"] == sha256_bytes(segment.original_text.encode())
    index = EvidenceIndex(ledger.index_dir / "audio.sqlite")
    built = index.build(ledger)
    assert built["record_count"] == 1
    assert index.search("jurisdiction")[0]["segment_id"] == "SEG-001"
    translated = index.search("Umqashi")[0]
    assert translated["target_language"] == "zu"
    assert translated["citation"].startswith("audio:UNIT-001#segment=SEG-001")


def test_whisper_parser_handles_millisecond_offsets_and_empty_units(tmp_path: Path):
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    adapter = WhisperCppUnitAdapter(WhisperCppConfig(binary="whisper-cli", model=str(model)))
    segments, language = adapter._parse_segments(
        {
            "result": {"language": "en"},
            "transcription": [
                {
                    "text": "Good morning Commissioner.",
                    "offsets": {"from": 1000, "to": 3500},
                    "tokens": [{"p": 0.8}, {"p": 0.9}],
                }
            ],
        },
        unit_id="UNIT-001",
        source_item_id="UNIT-001",
        absolute_start=60.0,
        raw_response_sha256="a" * 64,
    )
    assert language == "en"
    assert segments[0].start_seconds == 61.0
    assert segments[0].end_seconds == 63.5
    assert segments[0].word_timestamps_present is True
    empty, _ = adapter._parse_segments(
        {"result": {"language": "en"}, "transcription": []},
        unit_id="UNIT-002",
        source_item_id="UNIT-002",
        absolute_start=120.0,
        raw_response_sha256="b" * 64,
    )
    assert empty == []


def test_workspace_seal_is_hash_verifiable(tmp_path: Path):
    ledger = make_ledger(tmp_path)
    add_source_and_units(ledger, tmp_path)
    sealed = ledger.seal_snapshot(actor="tester", note="test seal")
    assert sealed["custody_chain"]["state"] == "PASS"
    assert len(sealed["merkle_root_sha256"]) == 64
    seal_files = list(ledger.receipts_dir.glob("workspace-seal-*.json"))
    assert seal_files and len(sha256_file(seal_files[0])) == 64


def test_legacy_import_reconstructs_zero_segment_units(tmp_path: Path):
    from evidenceops_audio_v4.legacy import import_legacy_whisper_run

    ledger = make_ledger(tmp_path)
    job = {
        "run_id": "RUN-1",
        "source": {"file": "recording.m4a", "drive_id": "source-drive-id", "sha256": "1" * 64, "size_bytes": 100, "duration_seconds": 120},
        "chunks": [
            {"sequence": 1, "file": "chunk.flac", "drive_id": "chunk-drive-id", "sha256": "2" * 64, "size_bytes": 80, "start_seconds": 0, "end_seconds": 120, "duration_seconds": 120}
        ],
    }
    structured = {
        "model": "whisper.cpp",
        "segments": [
            {"segment_id": "unit-001-01-S001", "unit_id": "unit-001-01", "source_chunk_sequence": 1, "absolute_start_seconds": 1.0, "absolute_end_seconds": 2.0, "cleaned_text": "Test segment", "raw_text": "Test segment", "mean_token_probability": 0.9, "speaker": "SPEAKER_UNRESOLVED", "original_offsets": {"from": 1000, "to": 2000}, "timeline_anomaly": None}
        ],
    }
    job_path = tmp_path / "job.json"
    structured_path = tmp_path / "structured.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    structured_path.write_text(json.dumps(structured), encoding="utf-8")
    result = import_legacy_whisper_run(
        ledger,
        job_manifest_path=job_path,
        structured_transcript_path=structured_path,
        actor="tester",
        source_item_id="SRC-LEGACY",
    )
    assert result["processed_unit_count"] == 2
    assert result["emitted_segment_unit_count"] == 1
    assert result["zero_segment_unit_ids"] == ["unit-001-02"]
    assert result["unit_accounting"]["state"] == "PASS"
