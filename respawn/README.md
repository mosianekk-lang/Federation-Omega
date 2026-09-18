# Federation Respawn Bootstrap

Purpose: give every FUSE/Federation system spawn a deterministic startup path that recovers prior solved work before rebuilding it.

The Respawn runtime is the existing shared continuity root. ChatGPT-native recall/resume capability is absorbed here rather than introduced as a competing top-level memory system.

## Contract

A spawn performs:

1. identify system + matter + chat/workstream
2. load system Bible / provider projection
3. load federation registry
4. load recent sync events / shared learnings / conflicts
5. run `Already Solved?`
6. separate strict current evidence from verified historical/source evidence
7. reuse, resume or supersede prior work with provenance
8. execute new work
9. publish a delta and bibliography entry through the existing governed route

## REST API surface

- `GET /health`
- `POST /bootstrap` → returns startup context for a system/matter
- `POST /delta` → accepts a new work delta and computes affected systems
- `POST /already-solved` → searches known reusable patterns / prior work signatures

## MCP / ChatGPT read surface

- `federation_health`
- `bootstrap_spawn` — compact task-specific context is the default
- `already_solved`
- `get_current_federation_state` — use before claiming that a capability exists/live **now**
- `resume_federation_mission` — use for `n`, continue, proceed, restore and resume semantics
- `get_federation_corpus_coverage` — use before claiming complete/all-chat ChatGPT history
- `search`
- `fetch`

`publish_delta` remains the existing governed mutation tool and is not broadened by the ChatGPT-native context additions.

## ChatGPT thin-shim rule

ChatGPT is a Federation intelligence client, not the sole Federation database. The MCP surface should return the smallest sufficient task-specific context rather than dumping an entire Bible into the model context.

A documented capability is not operational merely because it has a name. Operational/current claims require discoverable state plus appropriate execution/provider evidence.

## Truth rules

- Never claim a provider mutation unless a provider/tool result proves it.
- Never silently overwrite a conflicting canonical fact.
- Do not promote generic `VERIFIED`/`TESTED` historical evidence into a claim of current/live state.
- `COMPLETE_FOR_PROVIDED_EXPORT` does not prove complete native ChatGPT account history.
- Preserve old state, new state, source, actor, timestamp and reason.
- Domain authority wins over broad propagation: legal conclusions remain Lex-owned; evidence truth-state remains TruthGrid/EvidenceOps-owned; systems/runtime state remains Bubbles/Federation-owned.

## Deployment

The service is provider-neutral. It can run locally, on Cloud Run, another container host, or behind an MCP/ChatGPT App control surface. Google Drive IDs and runtime credentials are supplied through environment variables; no secrets are committed.

The repository-side implementation is intentionally useful before provider deployment: it gives a stable manifest, deterministic routing, bounded context compilation and a testable bootstrap/resume contract.
