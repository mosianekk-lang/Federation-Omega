# IPEP / EvidenceOps Audio Platform

Repository-native evidence processing for audio, authenticity, legal traceability and portable proof packets.

## Safety boundary

No source evidence, credentials, API keys, private transcripts or case-specific personal data belongs in this repository. Runtime secrets must be supplied through an authorised secret manager.

## Initial stack

- Google Drive: evidence workspace and approved outputs
- Google Cloud Run: processing runtime
- Google Cloud Storage: optional controlled derivatives
- Google Secret Manager: provider credentials
- Google Apps Script: lightweight Drive orchestration
- OpenAI / Google provider adapters: transcription providers
- GitHub Actions: tests and deployment provenance
- Canva: QA-approved report visualisation only
