# EvidenceOps Audio Processing Solution v2

A proof-carrying upgrade of IPEP that combines:

- **Alpha→Omega:** discovery → decomposition → architecture → build → test → deploy → verify → operate → maintain.
- **Formation Engine:** provider effects remain permit- and readback-gated; local tests never imply hosted liveness.
- **In-Place Evidence Processing:** source evidence remains untouched; only controlled derivatives, transcripts and receipts are written.

## State machine

`DISCOVERED → PRESERVED → NORMALISED → CHUNKED → READY_FOR_TRANSCRIPTION → TRANSCRIBING → TRANSCRIBED → QA_PENDING → QA_PASSED → RELEASED`

Every transition is supported by an immutable JSON receipt. Failed preconditions produce a typed `BLOCKED_*` state rather than a completion claim.

## Providers

1. `local_whisper_cpp` — offline, requires `whisper-cli` and a local model.
2. `google_speech_v2` — dedicated long-form STT; requires Google ADC, a controlled GCS prefix and project authority.
3. `gemini_files_api` — uploads audio through the Gemini Files API and requests a forensic transcript; requires an API key.

No credentials are stored in source, manifests, transcript files or receipts.

## Core commands

```bash
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run validate
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run preflight
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run verify-chunk --sequence 13 --audio part_012.flac
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run transcribe-chunk --sequence 13 --audio part_012.flac
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run resume-plan
python -m evidenceops_audio.cli --manifest AUDIO_PROCESSING_MANIFEST.json --workspace run assemble
```

## Evidence controls

- source and chunk SHA-256 validation;
- contiguous duration coverage validation;
- resumable chunk-level processing;
- provider preflight and fail-closed routing;
- recursive credential redaction;
- transcript hashes and assembly receipt;
- no source mutation;
- no transcript claim unless an output file and digest exist.
