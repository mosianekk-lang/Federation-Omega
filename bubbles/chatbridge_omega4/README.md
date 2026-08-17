# ChatBridge Ω4 — Governed Durable Conversation OS

ChatBridge Ω4 evolves the Drive/Kim-Dataverse continuity protocol into a source-backed
durable conversation kernel while preserving the existing ChatGov governance contract.

The current source generation is **ChatBridge Ω4.8**. It retains every event that an
authorised ChatBridge adapter can observe in a Full-Fidelity Conversation Ledger (FFCL):

- every user, assistant, system, developer, tool and connector event is captured in order;
- each event has a canonical content hash and a previous-event hash;
- the complete sequence also has a Merkle root and start/end watermarks;
- duplicate capture is idempotent, while conflicting reuse fails closed;
- attachments are represented by stable IDs, hashes, locators and availability state;
- corrections append new events instead of rewriting prior history;
- exact restore is allowed only when the complete start-to-finish range is present;
- legacy or incomplete conversations restore with an explicit gap manifest;
- terminal intent is never represented as successful execution; and
- uncaptured content is never guessed or reconstructed as fact.

Ω4.8 includes all Ω4.7 protections:

- Conversation Exhaustion Guard with continuous write-ahead checkpoints;
- pre-heavy-operation checkpoint and readback;
- observable Green / Amber / Red / Terminal risk states;
- preemptive migration before likely context exhaustion;
- fail-closed terminal recovery from the last verified checkpoint;
- privacy-minimised empirical learning-event storage;
- evidence-bound ChatGPT playbook rules with contradiction holds; and
- documentation as supplementary evidence rather than ground truth.

See:

- `FULL_FIDELITY_CONVERSATION_LEDGER.md`
- `CONVERSATION_EXHAUSTION_AND_EMPIRICAL_PLAYBOOK.md`
- `governance/chatbridge_full_fidelity_ledger_v1.json`

## Current runtime

Package-level imports use Ω4.8:

```python
from bubbles.chatbridge_omega4 import ChatBridgeOmega4
```

The explicit classes remain available:

- `ChatBridgeOmega48` — current full-fidelity runtime;
- `ChatBridgeOmega47` — prior Ω4.7 runtime for compatibility and historical tests.

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
- empirical learning-event and playbook-rule persistence;
- rule promotion that requires independent empirical support;
- exact source-conversation identity binding;
- append-only ordered event capture;
- SHA-256 content and previous-event hash chaining;
- Merkle-root transcript sealing;
- expected first/last sequence watermarks;
- explicit missing-range and external-dependency reporting;
- exact versus bounded transcript restore modes;
- terminal attempted-action versus verified-execution separation; and
- legacy import without invented content.

Run the deterministic package suites from repository root:

```bash
python -m unittest \
  bubbles.chatbridge_omega4.test_omega4 \
  bubbles.chatbridge_omega4.test_operating_profile \
  bubbles.chatbridge_omega4.test_restore_assurance \
  bubbles.chatbridge_omega4.test_assurance_gate \
  bubbles.chatbridge_omega4.test_conversation_exhaustion \
  bubbles.chatbridge_omega4.test_empirical_playbook \
  bubbles.chatbridge_omega4.test_full_fidelity_ledger \
  bubbles.chatbridge_omega4.test_runtime_omega48 \
  -v
```

## Identity and continuity stack

```text
Exact source conversation_key
    ↓
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
Full-Fidelity Conversation Ledger checkpoint
    ↓
Ordered event hashes + chain head + Merkle root
    ↓
Attachment/provider-event manifest
    ↓
Empirical playbook cursor
    ↓
Provider continuation reference
    ↓
Exact next action
```

## Full-fidelity capture contract

An authorised adapter should call the Ω4.8 guard for every observed event. Capture occurs
before heavy reasoning or provider mutation. The adapter supplies:

- exact source conversation key;
- monotonic event sequence;
- role and event type;
- raw governed content or an explicit downgraded availability state;
- event occurrence time and provider/source IDs where available;
- execution state;
- attachment references and hashes; and
- minimum necessary metadata.

A conversation is sealed with expected first and last sequence watermarks. Verification
then produces one of four outcomes:

- `EXACT_TRANSCRIPT_RESTORE`
- `BOUNDED_TRANSCRIPT_RESTORE`
- `REJECT_TAMPERED`
- `NO_TRANSCRIPT`

Exact means the entire declared range is present, the hash chain verifies, all payloads
needed for context are available and all required artifact references are verified.
Anything weaker is bounded and includes the precise reason.

## Legacy conversation recovery

Ω4.8 cannot retroactively create messages that were never stored. For an older exhausted
conversation, an adapter may import an available ChatGPT export, shared-conversation copy,
browser archive or another primary transcript source. Imported events preserve their
original order and provenance. Any missing sequence remains an explicit gap.

This means:

- future ChatBridge-active conversations can be reconstructed start to finish;
- older conversations can become exact only when a complete source transcript is supplied;
- screenshots and checkpoints remain useful, but they do not silently become a verbatim
  transcript.

## Provider continuation modes

Ω4 deliberately keeps the runtime persistence mode explicit and mutually exclusive:

- `CLIENT_SESSION` — a client-managed Agents SDK session/store identifier;
- `OPENAI_CONVERSATION` — an OpenAI Conversations API conversation identifier;
- `OPENAI_PREVIOUS_RESPONSE` — lightweight Responses API continuation;
- `NONE` — no provider continuation binding.

The provider adapter must select one strategy for a given turn rather than combining
client-managed session history with server-managed continuation.

## Truth boundaries

The source and deterministic tests do not prove an invisible native ChatGPT hook or
automatic access to every existing conversation. A connected adapter must deliver the
events to the ledger. Full-fidelity capture therefore applies wherever ChatBridge Ω4.8 is
actually active and bound.

The implementation also does not claim:

- exact visibility into a hidden provider quota;
- automatic recovery of content never captured or exported;
- provider deployment merely because source code exists;
- model-weight learning;
- external legal or operational effects without provider readback; or
- that a hash-valid transcript proves the truth of every statement inside it.

Integrity of the record and truth of the underlying claims remain separate questions.
