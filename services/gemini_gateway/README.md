# SOVARA Gemini Gateway v1

Private Cloud Run execution cell for Gemini through Vertex AI.

## Security model

- Canonical Google Cloud project is hard-bound to `sov-hybrid-suite` / `257649435135`.
- The workload uses the Cloud Run service account through Application Default Credentials.
- No Gemini API key, service-account key, refresh token, or OAuth token is stored in source.
- OAuth access tokens are fetched only from the Google metadata server and are never returned.
- Cloud Run remains private; callers must pass Cloud Run IAM authentication.
- `/health` proves only process/configuration health.
- `/ready` proves runtime metadata identity, not Gemini inference.
- `/v1/handshake` is the provider promotion gate and requires exact semantic-nonce return plus Vertex `responseId`, `modelVersion`, finish state, usage metadata and runtime identity.
- Every provider result is SHA-256 bound. CI/source success never substitutes for provider execution proof.

## Endpoints

- `GET /health`
- `GET /ready`
- `POST /v1/handshake` with `{"semantic_nonce":"..."}`.
- `POST /v1/generate` with `{"prompt":"...", "temperature":0, "max_output_tokens":512}`.

## Runtime identity

Recommended dedicated service account:

`sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com`

Minimum project role for model invocation: `roles/aiplatform.user`.

Use `ops/bootstrap_gemini_gateway.sh --plan` first. Applying identity/API bindings is gated and produces an explicit verification receipt.

## Promotion rule

Do not call the lane live until the zero-traffic canary returns:

- `status = VERIFIED`
- exact semantic nonce
- non-empty Vertex `provider_request_id`
- non-empty `model_identity`
- canonical project
- exact expected runtime service account
- receipt hash
