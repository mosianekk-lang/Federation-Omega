# EvidenceOps Capability Heartbeat MCP Gateway

Maturity: **IMPLEMENTED AND LOCALLY TESTED; NOT DEPLOYED**.

This is a separate, tool-only Streamable HTTP MCP resource server for the
EvidenceOps heartbeat. It does not modify or route through the legacy
administrator MCP adapter. Its only backend is the private
`evidenceops.heartbeat_api` contract.

## Security boundary

- Public endpoint: `POST|GET|DELETE /mcp`, protected by OAuth 2.1 Bearer JWT
  validation (signature, issuer, exact audience, expiry and per-tool scope).
- Protected-resource metadata:
  path-specific `GET /.well-known/oauth-protected-resource/mcp`; the root path
  `GET /.well-known/oauth-protected-resource` is retained as a compatibility alias.
- Required scopes: `heartbeat:read` for `heartbeat_status`, `search`, and
  `fetch`; `heartbeat:emit` for `heartbeat_emit`.
- The inbound OAuth access token is never logged or forwarded.
- Private Cloud Run authentication uses a Google ID token in
  `X-Serverless-Authorization`. Application-internal authentication uses
  `X-EvidenceOps-Internal-Auth`. No `FO_ADMIN_TOKEN` route exists.
- `heartbeat_emit` accepts only the private API's closed, snake-case
  `IngestRequest`; unknown/raw-content fields are rejected. A successful write
  is followed by private semantic readback before the tool returns.

Current OpenAI Apps descriptors receive `securitySchemes` both at the top level
and mirrored in `_meta.securitySchemes`. The server uses the production v1 MCP
SDK; v2 pre-alpha APIs are not used.

## Required configuration

All endpoint and identity values are injected at runtime. Startup fails closed
if any required value is absent or invalid.

| Variable | Contract |
| --- | --- |
| `HEARTBEAT_BACKEND_URL` | HTTPS service origin of the private heartbeat API; no path, query, credentials or fragment |
| `HEARTBEAT_BACKEND_AUDIENCE` | Exact same normalized HTTPS service origin, used as the Google ID-token audience |
| `HEARTBEAT_INTERNAL_AUTH_VALUE` | Shared application-internal secret, at least 32 characters |
| `MCP_RESOURCE_URL` | Exact public HTTPS resource URL ending in `/mcp`; also the JWT audience |
| `OAUTH_ISSUER` | Exact HTTPS access-token issuer |
| `OAUTH_JWKS_URI` | HTTPS JWKS endpoint |
| `OAUTH_JWT_ALGORITHMS` | Comma-separated allowlist from `RS256`, `PS256`, `ES256` |

Optional bounded settings are `PORT` (default `8080`),
`HEARTBEAT_BACKEND_TIMEOUT_MS` (default `10000`) and
`HEARTBEAT_MAX_BACKEND_RESPONSE_BYTES` (default `2000000`).

The authorization server must publish its own OAuth metadata and issue tokens
whose `aud` is exactly `MCP_RESOURCE_URL`. The gateway is a resource server, not
an authorization server, and does not implement token passthrough.

The private backend URL and Google ID-token audience are one trust boundary:
startup rejects different origins, non-HTTPS values, embedded credentials,
queries, or path-bearing audience variants rather than relying on ambiguous URL
normalization.

## Local verification

Node.js 20 or newer is required.

```sh
npm ci
npm run check
npm test
npm run build
```

Run the compiled server after injecting the required variables:

```sh
npm start
```

Container build (local only):

```sh
docker build -t evidenceops-heartbeat-mcp:local .
```

No Cloud Run service, IAM binding, OAuth client, secret, image, revision,
traffic change, connector registration, or canary was created by this build.

## Tool contract

- `heartbeat_status`: exact private API status readback.
- `search`: standard OpenAI connector shape; performs bounded native registry
  pagination, code-pattern matching, and returns `{results:[{id,title,url}]}`.
- `fetch`: standard OpenAI connector shape; returns canonical metadata-only JSON
  text and a semantic hash.
- `heartbeat_emit`: the sole effectful route; idempotent, A0-only ingest plus
  verified readback. It does not accept files, evidence bodies, messages, free
  text, credentials, or secrets.

Failures are sanitized at the tool boundary. Backend response size and timeout
are bounded. The gateway performs no write retry; idempotency and immutable
conflict handling remain authoritative in the private API.
