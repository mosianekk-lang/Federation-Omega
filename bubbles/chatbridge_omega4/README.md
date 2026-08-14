# ChatBridge Ω4 — Governed Durable Conversation OS

ChatBridge Ω4 evolves the Drive/Kim-Dataverse continuity protocol into a source-backed durable conversation kernel while preserving the existing ChatGov governance contract.

## What this package proves

This package implements a provider-neutral local core using Python's standard library only:

- dynamic user namespaces (`chatbridge "X"` semantics);
- immutable namespace IDs separate from human labels;
- atomic active-generation rebinding;
- immutable checkpoint generations;
- exact historical restore without silently moving the active pointer;
- clone/branch ancestry;
- rename without rewriting generation history;
- release/tombstone rather than deletion;
- session-bound restore leases for idempotent reuse;
- Governance Capsule persistence and approval-gate survival;
- HOT/WARM/COLD state preservation;
- provider continuation metadata with mutually exclusive persistence strategies;
- fail-closed namespace scope collisions;
- restore-preview reasons for historical, released, branched, materially changed or governance-degraded state.

Run the deterministic suite from repository root:

```bash
python -m unittest bubbles.chatbridge_omega4.test_omega4 -v
```

## Identity stack

```text
Human namespace
    ↓
Immutable namespace_id
    ↓
Generation
    ↓
Immutable handoff_id
    ↓
Checkpoint fingerprint
    ↓
Governance Capsule
    ↓
HOT / WARM / COLD continuity state
    ↓
Provider continuation reference
    ↓
Exact next action
```

## Provider continuation modes

Ω4 deliberately keeps the runtime persistence mode explicit and mutually exclusive:

- `CLIENT_SESSION` — a client-managed Agents SDK session/store identifier;
- `OPENAI_CONVERSATION` — an OpenAI Conversations API conversation identifier;
- `OPENAI_PREVIOUS_RESPONSE` — lightweight Responses API continuation;
- `NONE` — no provider continuation binding.

The provider adapter must select one strategy for a given turn rather than combining client-managed session history with server-managed continuation.

## Current truth boundary

`CHATBRIDGE-Ω4.0-SOURCE-CANDIDATE` is source-complete for the local provider-neutral continuity kernel and deterministic tests. It does **not** yet call the OpenAI API, instantiate `OpenAIConversationsSession`, deploy Postgres/Redis infrastructure, bind a ChatGPT App, or prove a native cross-chat event hook.

The next provider-bound gate is documented in `PROVIDER_BINDING.md`. That step requires an authorised OpenAI API credential and separate provider readback. Google Drive / Kim Dataverse remains the canonical audit/archive fabric until a successor runtime is independently verified.
