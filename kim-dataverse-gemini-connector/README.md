# Kim DataVerse Gemini EvidenceOps Connector

Production-foundation connector for controlled Gemini generation and evidence-aware audio transcription. It is designed for a private Cloud Run service, keyless Vertex AI access through the attached runtime service identity, and an optional Google AI Studio Developer API key injected only through Secret Manager.

## What is implemented

- deterministic provider routing: `vertex`, `developer`, or `auto`;
- keyless Vertex authentication through the Cloud Run metadata server;
- AI Studio Developer API authentication via `x-goog-api-key`, never a query string;
- private-service assumptions plus optional constant-time bearer-token defense;
- strict model, input-size, audio-size, output-token, concurrency and daily-budget controls;
- JSON audio transcripts with uncertainty markers, integrity hashes and an explicit human-verification status;
- idempotency conflict detection, correlation IDs and secret-redacted structured logs;
- health, readiness, capability and bounded operational-metrics endpoints;
- non-root container, zero-traffic canary workflow, billing/API/IAM preflight and explicit promotion gate.

The [feature registry](docs/feature-registry.json) separates `IMPLEMENTED`, `DESIGNED` and `RESEARCH` capabilities. A feature count is not a completion claim.

## Run locally

Node.js 22 or newer is required.

```bash
npm install --ignore-scripts
npm test
npm run smoke
npm run validate:features
KDV_PROVIDER=vertex GOOGLE_CLOUD_PROJECT=sov-hybrid-suite GOOGLE_OAUTH_ACCESS_TOKEN=local-test-only node src/server.mjs
```

`GOOGLE_OAUTH_ACCESS_TOKEN` is intentionally not read by the production entry point. Tests inject tokens directly. For a real local Vertex session, use an approved ADC-aware adapter or run the container on Google Cloud with a service identity. Do not export a service-account key.

## API

`GET /health` is a liveness probe. `GET /ready` checks configuration only; it does not spend model tokens. `GET /v1/capabilities` and `GET /metrics` require the configured defense-in-depth token when `KDV_SHARED_TOKEN` is set.

`POST /v1/generate`:

```json
{
  "prompt": "Summarise the procedural issue.",
  "model": "gemini-2.5-flash",
  "maxOutputTokens": 2048,
  "idempotencyKey": "matter-CASE-EXAMPLE-001-summary-001"
}
```

`POST /v1/transcribe` with inline audio:

```json
{
  "caseId": "CASE-EXAMPLE-001",
  "evidenceId": "hearing-2026-08-01",
  "audio": {"mimeType": "audio/mpeg", "dataBase64": "..."},
  "timestamps": true,
  "diarization": true,
  "language": "en-ZA",
  "idempotencyKey": "CASE-EXAMPLE-001-hearing-20260801-v1"
}
```

Vertex can also accept `{"mimeType":"audio/mpeg","uri":"gs://bucket/object.mp3"}`. The Developer API route deliberately rejects `gs://`; files over the inline limit require a governed Files API or Cloud Storage ingestion stage.

Every transcript is labelled `MODEL_GENERATED_REQUIRES_HUMAN_VERIFICATION`. Hashes prove which bytes or locator and which model output were processed; they do not prove speaker identity, accuracy, authenticity or legal admissibility.

## Deployment boundary

Push and pull-request events run tests only. Cloud access occurs only through a manual workflow dispatch. Deployment additionally requires:

1. the exact confirmation `DEPLOY_KIM_DATAVERSE_CONNECTOR`;
2. successful WIF identity, billing, Vertex API, Artifact Registry and runtime IAM readbacks;
3. production-environment approval;
4. a zero-traffic canary and authenticated health proof;
5. a separate `promote=true` choice to receive traffic.

Rollback:

```bash
gcloud run services update-traffic kim-dataverse-gemini-connector --project sov-hybrid-suite --region africa-south1 --to-revisions PREVIOUS_REVISION=100
```

## Security invariants

- Never commit API keys, service-account JSON, OAuth tokens, cookies or browser-session material.
- Never infer cloud authority from a signed-in desktop screenshot.
- Never silently switch providers after an authentication or permission failure.
- Never call a generated transcript verified evidence without human and source review.
- Never call a workflow, container or deployment “live” without provider-side readback.

See [architecture](docs/ARCHITECTURE.md), [lessons learned](docs/LESSONS_LEARNED.json), and [build contract](BUILD_CONTRACT.json).
