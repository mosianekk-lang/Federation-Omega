# FO Transcription Bridge — IPEP Runtime Adapter

Private, evidence-aware runtime adapter for the canonical `ipep/audio_engine_v2` EvidenceOps Audio Processing Solution.

This is no longer a separate top-level transcription system. Its Cloud Run, Cloud Storage, Cloud Tasks and Speech-to-Text components are the Google provider/runtime lane beneath the IPEP v2 state machine, manifest validator, provider router, proof receipts and release gates.

## Deployment target

- Google Cloud project: `sov-hybrid-suite`
- Cloud Run region: `africa-south1`
- Speech-to-Text V2 processing location: `eu`
- Service: `fo-transcription-bridge`
- Authentication: Cloud Run IAM only; anonymous invocation is disabled
- Runtime identity: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`

## Canonical processing contract

1. IPEP validates source/preservation metadata and the chunk manifest.
2. The runtime receives only a controlled derivative or a provider-authorised object reference.
3. Each chunk is hash-verified before transcription.
4. The provider adapter submits and polls the selected transcription operation.
5. TXT, structured JSON, SRT and VTT are generated with chunk and absolute timestamps.
6. IPEP writes redacted receipts and refuses release while any mandatory chunk or QA gate is missing.
7. Google Speech output may be verified against OpenAI, Gemini or offline whisper.cpp without changing the source evidence.

## Existing runtime capabilities retained

- private GCS/resumable upload sessions;
- 16 kHz mono FLAC preparation;
- Speech-to-Text V2 batch recognition;
- Cloud Tasks polling;
- word-to-speaker-turn segmentation;
- TXT/SRT/VTT rendering;
- controlled Google Doc write-back;
- evidence manifest and completion receipts.

## Evidence limitations

- Automated output is a working transcript, not a certified transcript.
- Speaker identity is unverified until independently supported.
- Speaker continuity across chunks must be reconciled and logged.
- Material passages must be checked against the original recording.
- No deployment, provider execution or transcript completion is claimed without provider-native readback and output hashes.

## Local tests

```bash
python -m pip install -r requirements.txt pytest
pytest -q
```

## Authenticated client

Use `ops/fo_transcription_client.sh` from an authenticated environment. Provider credentials and approval material must remain in Secret Manager or ephemeral environment bindings, never in the repository or command sheets.
