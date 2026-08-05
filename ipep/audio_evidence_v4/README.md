# EvidenceOps Audio Evidence Completion System v4.0

A permanent EvidenceOps subsystem for professional collection, preservation, processing, automated transcription, translation, human verification, quotation release and evidence retrieval.

## What v4 adds

The existing v2 provider layer and v3.1 multi-architecture consensus layer remain useful. v4 adds the missing evidence-lifecycle controls around them:

- content-addressed source preservation;
- hash-chained custody events;
- normalized and fixed-window derivative lineage;
- one raw provider receipt for every processed unit;
- explicit `EMITTED_SEGMENTS`, `ZERO_SEGMENT`, and `FAILED` states;
- the accounting invariant `processed = emitted + zero-segment + failed`;
- original-language transcript preservation;
- provider-neutral automated translation with raw receipts;
- bilingual human-review gates for translated quotations;
- audio-window extraction and hashing for listening verification;
- excerpt-level quotation release receipts;
- an external-attestation-only transcript certification gate;
- a SQLite full-text evidence index with provenance-aware results;
- Merkle-sealed workspace snapshots.

## Critical truth boundary

The software never declares an automated transcript “certified verbatim.” Automation creates a working record. An excerpt becomes `VERIFIED_FOR_QUOTATION` only after the required architecture, timestamp, speaker-role, entity, human-listening and audio-window-hash gates pass. A whole transcript remains `NOT_CERTIFIED` until every segment is human verified and an external signed attestation is supplied.

## Professional workflow

1. **Collect** the original recording with custodian, capture-time, device and location metadata.
2. **Preserve** a byte-identical copy and verify its SHA-256.
3. **Normalize** to a provider-safe lossless derivative; never overwrite the original.
4. **Split** into deterministic windows and register each unit as an evidence derivative.
5. **Transcribe** with at least two independent ASR architecture families for material passages.
6. **Retain** every raw provider response and command receipt, including zero-segment units.
7. **Translate** only into derivative records; preserve the source-language text unchanged.
8. **Fuse and review** disagreements using the v3.1 consensus engine.
9. **Listen** to exact material windows and record the reviewed-window hash.
10. **Release** only passage-specific quotations whose gates pass.
11. **Index** originals, translations, timings, speakers, reviews and provenance for search.
12. **Seal** each release snapshot with hashes and a Merkle root.

## CLI

```bash
pip install -e ipep/audio_evidence_v4

evidenceops-audio-v4 init ./case-audio \
  --matter MPMB298-26 \
  --case-wall CASE-WALL-MPMB298-26-PRIMARY \
  --owner "Kim Kagiso Mosiane"

evidenceops-audio-v4 collect ./case-audio recording.m4a \
  --item-id SRC-AUDIO-31JUL-2026-001 \
  --actor "Kim Kagiso Mosiane" \
  --captured-at "2026-07-31T09:33:42+02:00"

evidenceops-audio-v4 prepare-units ./case-audio \
  --source-item-id SRC-AUDIO-31JUL-2026-001 \
  --actor "EvidenceOps" \
  --unit-seconds 60

evidenceops-audio-v4 transcribe ./case-audio ./case-audio/manifests/SRC-AUDIO-31JUL-2026-001-unit-plan.json \
  --actor "EvidenceOps" \
  --binary /secure/runtime/whisper-cli \
  --model /secure/models/ggml-large-v3.bin \
  --vad-model /secure/models/ggml-silero.bin

evidenceops-audio-v4 translate ./case-audio \
  --command "/secure/bin/evidenceops-translate" \
  --target-language en \
  --actor "EvidenceOps"

evidenceops-audio-v4 import-legacy ./case-audio \
  EVIDENCEOPS_AUDIO_JOB.json 05_structured_transcript.json \
  --source-item-id SRC-AUDIO-LEGACY-001 \
  --actor "EvidenceOps Legacy Import"

evidenceops-audio-v4 index ./case-audio
evidenceops-audio-v4 search ./case-audio "jurisdiction promotion agreement"
evidenceops-audio-v4 audit ./case-audio
evidenceops-audio-v4 seal ./case-audio --actor "EvidenceOps"
```

## Translation adapter contract

The configured command receives JSON on stdin:

```json
{
  "segment_id": "SEG-001",
  "text": "source-language text",
  "source_language": "zu",
  "target_language": "en"
}
```

It returns JSON on stdout:

```json
{
  "translated_text": "translated text",
  "model": "approved-provider/model-version"
}
```

Credentials remain in the approved runtime or secret manager. They must never be written into chat, source control, Drive evidence files or receipts.

## Integration with v2 and v3.1

- v2 provider adapters may feed per-unit provider responses into v4.
- v3.1 consensus outputs may be imported as additional architecture-supported hypotheses.
- v4 remains the custody, verification, release and retrieval control plane.
