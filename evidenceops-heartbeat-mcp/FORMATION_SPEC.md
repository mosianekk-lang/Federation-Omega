# Formation specification

- Mission: expose the verified A0 capability-heartbeat through one private-data
  MCP resource server without extending heartbeat authority.
- Classification: PROD FOUNDATION, backend API plus tool-only connector.
- Authority ceiling: A0 recommendation-only heartbeat metadata.
- Read paths: status, standard search, standard fetch.
- Sole effectful path: closed heartbeat ingest followed by immutable readback.
- Authentication: external OAuth 2.1 JWT resource-server validation; internal
  Google Cloud service identity plus an injected application secret.
- Data boundary: metadata-only schemas; no evidence bodies, work-account data,
  email content, files, OAuth-token forwarding, or Federation Omega admin token.
- Persistence: not owned by this gateway; the private API's immutable store is
  authoritative.
- Queue, scheduler, cache, UI and agent autonomy: not applicable to this narrow
  synchronous gateway.
- Rollback unit: a future immutable container image/revision. No deployment or
  rollback action has been performed.
- Completion state: implemented and locally tested, deployment blocked pending
  separately proven cloud identity, IAM, OAuth and secret configuration.
