# FO Transcription Bridge

Private, evidence-aware audio transcription service for Federation Omega.

## Deployment target

- Google Cloud project: `sov-hybrid-suite`
- Cloud Run region: `africa-south1`
- Speech-to-Text V2 processing location: `eu`
- Service: `fo-transcription-bridge`
- Authentication: Cloud Run IAM only; anonymous invocation is disabled
- Runtime identity: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`
- Output document: `FO Transcription Bridge — MPMB298-26 — Controlled Transcript Output`

## Processing

1. `POST /v1/uploads` creates a private GCS object and a resumable upload session.
2. The caller uploads the original audio directly to Cloud Storage.
3. `POST /v1/jobs/{job_id}/start` queues preparation.
4. Audio longer than 15 minutes is converted into 16 kHz mono FLAC chunks with `ffmpeg`.
5. Each chunk is submitted to Speech-to-Text V2 batch recognition using Chirp 3, punctuation, diarization and word offsets.
6. Cloud Tasks polls the operations without holding an HTTP request open.
7. The service emits TXT, SRT, VTT, structured JSON, an evidence manifest and a completion receipt.
8. The readable transcript is appended to the controlled Google Doc shared with the runtime service account.

## Evidence limitations

- The output is an automated working transcript, not a certified verbatim transcript.
- Speaker labels are machine-generated. Identity must be independently authenticated.
- Speaker continuity across separately processed chunks is explicitly marked `UNVERIFIED`.
- Material passages must be checked against the original recording.

## Local tests

```bash
python -m pip install -r requirements.txt pytest
pytest -q
```

## Authenticated client

Use `ops/fo_transcription_client.sh` from an authenticated Google Cloud Shell or a workstation with `gcloud` configured for `sov-hybrid-suite`.
