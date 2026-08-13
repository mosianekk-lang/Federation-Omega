# Federation Respawn Bootstrap

Purpose: give every Bubbles/Lex/Federation system spawn a deterministic startup path that recovers prior solved work before rebuilding it.

## Contract

A spawn performs:

1. identify system + matter + chat/workstream
2. load system Bible
3. load federation registry
4. load recent sync events / shared learnings / conflicts
5. run `Already Solved?`
6. reuse or supersede prior work with provenance
7. execute new work
8. publish a delta and bibliography entry

## API surface

- `GET /health`
- `POST /bootstrap` → returns startup context for a system/matter
- `POST /delta` → accepts a new work delta and computes affected systems
- `POST /already-solved` → searches known reusable patterns / prior work signatures

## Truth rules

- Never claim a provider mutation unless a provider/tool result proves it.
- Never silently overwrite a conflicting canonical fact.
- Preserve old state, new state, source, actor, timestamp and reason.
- Domain authority wins over broad propagation: legal conclusions remain Lex-owned; evidence truth-state remains TruthGrid/EvidenceOps-owned; systems/runtime state remains Bubbles/Federation-owned.

## Deployment

The service is provider-neutral. It can run locally, on Cloud Run, another container host, or behind an MCP/ChatGPT App control surface. Google Drive IDs and runtime credentials are supplied through environment variables; no secrets are committed.

The repository-side implementation is intentionally useful before provider deployment: it gives a stable manifest, deterministic routing and a testable bootstrap contract.