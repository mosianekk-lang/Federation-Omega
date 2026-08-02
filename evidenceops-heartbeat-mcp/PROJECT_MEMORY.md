# Project memory

## Durable decisions

1. This gateway is separate from `evidenceops-mcp-adapter`; the administrator
   adapter and its `FO_ADMIN_TOKEN` must never become a heartbeat dependency.
2. `evidenceops.heartbeat_api` is the canonical private contract. Header names,
   route methods, snake-case ingest schema and response models must match it.
3. Inbound OAuth `Authorization` is verified at `/mcp` and never forwarded.
   Cloud Run identity travels only in `X-Serverless-Authorization`.
4. OpenAI connector compatibility requires the exact `search` and `fetch`
   result shapes and a single JSON text content item.
5. `heartbeat_emit` is the only write surface and must remain metadata-only,
   idempotent, scope-gated and readback-verified.
6. Deployment is not proof. Keep maturity below DEPLOYED until fresh HTTPS,
   OAuth, IAM, backend and semantic readback canaries pass.
