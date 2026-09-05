# Architecture and threat model

## Single effectful path

GitHub Actions authenticates to Google Cloud through the existing Workload Identity Federation provider and the dedicated deployer service account. The workflow builds an immutable image, deploys a private zero-traffic revision, obtains an identity token, proves `/health`, and promotes only when explicitly requested. Source pushes never deploy.

At runtime Cloud Run attaches the user-managed runtime service account. The connector requests a short-lived OAuth access token from the metadata server and calls Vertex AI. No service-account key is created, copied or stored. If the optional Developer API route is selected, an auth key must be injected as `GEMINI_API_KEY` from Secret Manager; the connector sends it only in `x-goog-api-key`.

## Data flow

1. An IAM-authorized caller submits text or audio with a correlation ID and idempotency key.
2. The connector validates authorization, body size, schema, model allowlist, quotas and concurrency.
3. Audio is represented inline or as a Vertex-only `gs://` locator. Inline bytes are hashed before inference; a locator is hashed but is not mislabelled as a content hash.
4. One configured provider receives one bounded `generateContent` request.
5. The connector normalizes the response, hashes the output, adds safety/usage metadata and labels transcription as requiring human verification.
6. Structured logs contain operational fields only. Secret-, token- and audio-like fields are redacted.

## Failure semantics

- Invalid input is a 4xx error and never reaches Gemini.
- Missing configuration is a 503 readiness or provider-construction failure.
- Provider authentication and permission failures remain provider failures; there is no silent cross-provider retry.
- Network timeout becomes `GEMINI_TIMEOUT`; upstream 5xx becomes a normalized 502.
- Disconnect aborts the request where the runtime supports it.
- Idempotency replays only completed in-memory responses. A reused key with a different body returns 409.
- Concurrency and daily limits fail with 429 before model invocation.

## Known boundaries

- Idempotency, quotas and metrics are per instance and reset when an instance restarts. A persistent store is a designed, not implemented, feature.
- The connector does not fetch arbitrary URLs.
- The Developer Files API upload lifecycle and long-audio chunk orchestration are not implemented.
- Model transcription is not forensic speaker identification and is not an authenticity determination.
- No current deployment claim is made by source code, workflow presence or local tests.
