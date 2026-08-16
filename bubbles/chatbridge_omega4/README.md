# ChatBridge Ω4 — Governed Durable Conversation OS

ChatBridge Ω4 evolves the Drive/Kim-Dataverse continuity protocol into a source-backed
durable conversation kernel while preserving the existing ChatGov governance contract.

The current source generation is **ChatBridge Ω4.7**. It adds:

- a Conversation Exhaustion Guard with continuous write-ahead checkpoints;
- pre-heavy-operation checkpoint and readback;
- observable Green / Amber / Red / Terminal risk states;
- preemptive migration before likely context exhaustion;
- fail-closed terminal recovery from the last verified checkpoint;
- a privacy-minimised empirical learning-event store;
- evidence-bound ChatGPT playbook rules with contradiction holds;
- documentation-as-supplement rather than documentation-as-ground-truth; and
- Operating Profile inheritance of checkpoint, migration and learning policy.

See `CONVERSATION_EXHAUSTION_AND_EMPIRICAL_PLAYBOOK.md` for the complete contract.

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
- restore-preview reasons for historical, released, branched, materially changed or
  governance-degraded state;
- portable Operating Profiles and delta-aware restore assurance;
- pre-owner assurance and audit-before-architecture controls;
- write-ahead conversation-health checkpointing;
- terminal-warning false-backup prevention;
- empirical learning-event and playbook-rule persistence; and
- rule promotion that requires independent empirical support.

Run the deterministic package suites from repository root:

```bash
python -m unittest \
  bubbles.chatbridge_omega4.test_omega4 \
  bubbles.chatbridge_omega4.test_operating_profile \
  bubbles.chatbridge_omega4.test_restore_assurance \
  bubbles.chatbridge_omega4.test_assurance_gate \
  bubbles.chatbridge_omega4.test_conversation_exhaustion \
  bubbles.chatbridge_omega4.test_empirical_playbook \
  -v
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
Operating Profile
    ↓
HOT / WARM / COLD continuity state
    ↓
Conversation-health checkpoint
    ↓
Empirical playbook cursor
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

The provider adapter must select one strategy for a given turn rather than combining
client-managed session history with server-managed continuation.

## Conversation exhaustion truth boundary

ChatBridge does not assume access to an exact per-conversation remaining-quota meter.
Conversation risk is an operational estimate based on observable signals. The protection is
therefore two-layered:

1. checkpoint every material delta and before every heavy operation; and
2. migrate before risk reaches the terminal product boundary.

If a maximum-length warning is already observed, ChatBridge must not claim a new same-chat
checkpoint. Recovery uses the last independently verified checkpoint.

## Empirical learning truth boundary

The playbook learns from **ChatBridge-active chats**, not invisibly from every native ChatGPT
conversation. It stores sanitized operational observations and evidence pointers, not raw
matter transcripts, secrets or unrestricted sensitive content. It does not claim OpenAI
model-weight learning.

A global rule requires two independent verified empirical observations and provider or
canary support. Official documentation is supplementary evidence and cannot promote a rule
by itself. Verified contradictions force a hold and revalidation.

## Current provider boundary

The provider-neutral source and deterministic tests do **not** by themselves prove a native
cross-chat event hook, automatic interception of every ChatGPT conversation, external
provider deployment or guaranteed detection of the exact last permitted turn. Google Drive
/ Kim Dataverse remains the canonical audit/archive fabric until a successor runtime is
independently verified.
