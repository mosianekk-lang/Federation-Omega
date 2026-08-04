# IPEP / EvidenceOps Audio Platform

Repository-native evidence processing for audio, authenticity, legal traceability and portable proof packets.

## Canonical implementation

`ipep/audio_engine_v2/` is the current proof-carrying implementation. It integrates Alpha→Omega work stages, Formation truth boundaries and in-place evidence controls. The engine validates preservation manifests, verifies chunk hashes, selects an authorised transcription provider, resumes interrupted jobs, assembles transcripts and writes redacted receipts.

## Safety boundary

No source evidence, credentials, API keys, private transcripts or case-specific personal data belongs in this repository. Runtime secrets must be supplied through an authorised secret manager or ephemeral environment binding.

## Current stack

- Google Drive: evidence workspace and approved outputs
- Google Cloud Run: processing runtime
- Google Cloud Storage: controlled Speech-to-Text staging
- Google Secret Manager: provider credentials
- Google Apps Script: lightweight Drive orchestration
- Local whisper.cpp, Google Speech-to-Text V2 and Gemini Files API: provider adapters
- GitHub Actions: tests, immutable source packages and deployment provenance
- Canva: QA-approved report visualisation only

## Proof rule

Source code, passing tests or a successful package build do not prove provider deployment or transcription completion. A transcript is released only after source/chunk integrity, provider execution, transcript hashing, assembly and QA receipts all pass.
