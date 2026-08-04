# EvidenceOps Audio Processing — Canonical Architecture

## Mission

Preserve, transcribe, verify and analyse evidentiary audio without altering source evidence or overstating automation maturity.

## Control hierarchy

1. **Evidence source and preservation record** — immutable reference.
2. **IPEP v2 manifest and state machine** — canonical job truth.
3. **Alpha→Omega orchestrator** — discovery, route selection, build, test, deploy, verify, operate and maintain.
4. **Formation permits** — provider-specific authority and effect gate.
5. **Provider adapters** — Google Speech V2, OpenAI Audio Transcriptions, Gemini Files API and local whisper.cpp.
6. **Runtime adapter** — private Cloud Run/Cloud Tasks/GCS execution where Google authority is available.
7. **Proof ledger** — hashes, receipts, provider readback, QA and release state.

## Data flow

```text
Original audio + preservation copy
        ↓
Source SHA-256 and metadata manifest
        ↓
Controlled FLAC chunks + individual hashes
        ↓
Provider preflight and route selection
        ↓
Single-chunk canary
        ↓
Resumable chunk processing
        ↓
Provider output + redacted receipt + transcript hash
        ↓
Absolute timestamp reconciliation
        ↓
Speaker and uncertainty QA
        ↓
Master TXT / DOCX / SRT / VTT / JSON
        ↓
Jurisdiction argument and new-matter analysis
        ↓
Final release receipt
```

## State machine

`DISCOVERED → PRESERVED → NORMALISED → CHUNKED → READY_FOR_TRANSCRIPTION → TRANSCRIBING → TRANSCRIBED → QA_PENDING → QA_PASSED → RELEASED`

A blocked provider produces `BLOCKED_*`; it never advances the evidence state.

## Provider route order

1. Google Speech-to-Text V2 where controlled GCP authority and GCS staging exist.
2. OpenAI `gpt-4o-transcribe-diarize` where a securely bound project API key exists.
3. Gemini Files API for forensic verification and difficult-segment review.
4. Local whisper.cpp for offline fallback and independent checking.

Route selection requires a current preflight and an action-specific canary. Transport success without semantic output is rejected.

## Security invariants

- no source audio, private transcripts or case IDs in the public repository;
- no credential or approval value in Sheets, Drive manifests, logs or receipts;
- provider secrets are resolved from Secret Manager or an ephemeral environment;
- source evidence is never overwritten;
- all case-specific outputs remain in the controlled Drive/GCS case workspace;
- runtime services are private and least-privilege;
- every material mutation has rollback and independent readback.

## Release gates

A transcript may be marked `RELEASED` only when:

- all source and chunk hashes match;
- every mandatory chunk is transcribed;
- transcript outputs have SHA-256 receipts;
- chunk timestamps reconcile to the source timeline;
- uncertainty, inaudible and overlap markers are indexed;
- speaker labels are explicitly machine-generated or independently verified;
- a QA sample and material-passage audio check pass;
- no credential material appears in outputs;
- the final release receipt lists all source and output hashes.

## Supersession

`services/fo_transcription_bridge` is the Google runtime adapter beneath this architecture. Historical GATW and ARCHITRON audio components are reusable implementation sources, not competing canonical systems.
