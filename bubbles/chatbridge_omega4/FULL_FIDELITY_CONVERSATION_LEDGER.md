# ChatBridge Ω4.8 — Full-Fidelity Conversation Ledger

## Purpose

The Full-Fidelity Conversation Ledger (FFCL) solves the continuity failure exposed when a
ChatGPT conversation reaches the hard maximum-length boundary before its complete native
transcript has been exported or durably captured.

A state checkpoint preserves the current objective and next action. It does not necessarily
preserve every message, intermediate decision, abandoned option, attachment, correction or
tool result. FFCL adds a second continuity layer: an append-only start-to-finish event record.

## Core rule

> Capture every observable conversation event before it can be lost; prove completeness
> from sequence watermarks and cryptographic integrity; never invent an uncaptured event.

## Data model

Each source conversation is bound to:

- an exact `conversation_key`;
- one exact ChatBridge namespace;
- one source provider identity;
- an expected first sequence;
- an optional expected final sequence when sealed;
- a privacy policy; and
- a closure reason.

Each event stores:

- monotonic sequence number;
- role and event type;
- exact governed content or explicit availability downgrade;
- occurrence timestamp;
- source/provider event identifiers where available;
- idempotency key;
- execution state;
- sensitivity class;
- attachment references;
- metadata;
- content hash;
- previous-event hash;
- event hash; and
- capture timestamp.

## Integrity model

For each event:

1. Canonicalize the immutable event material.
2. Compute `content_hash = SHA256(canonical_event)`.
3. Compute `event_hash = SHA256(conversation_key + sequence + previous_event_hash +
   content_hash)`.
4. Persist the event and read it back inside the same SQLite transaction.
5. Advance the conversation watermark only after readback succeeds.

At verification time, the entire chain is recomputed. The ledger also derives a Merkle root
from the ordered event hashes. The chain head and Merkle root are evidence of record
integrity; neither proves the substantive truth of what participants said.

## Exact coverage

A conversation qualifies for `EXACT_TRANSCRIPT_RESTORE` only when all of the following are
true:

1. the conversation is sealed;
2. expected first and last sequence watermarks are known;
3. every sequence in that inclusive range is present;
4. every event content hash and previous-event link verifies;
5. every context-required payload is available as `RAW_GOVERNED`;
6. every context-required attachment reference is `VERIFIED_AVAILABLE`; and
7. no integrity finding remains open.

Otherwise the restore mode is bounded and exposes:

- missing sequence ranges;
- unavailable/redacted/hash-only payload sequences;
- unresolved artifact dependencies;
- first and last captured sequence;
- coverage percentage;
- terminal state;
- chain head;
- Merkle root; and
- exact truth boundary.

## Capture algorithm

For every ChatBridge-active conversation:

```text
OBSERVE EVENT
    ↓
RESOLVE EXACT SOURCE CONVERSATION ID
    ↓
BIND CONVERSATION ID TO EXACT NAMESPACE
    ↓
VALIDATE MONOTONIC SEQUENCE + IDEMPOTENCY
    ↓
CLASSIFY EXECUTION / PAYLOAD / SENSITIVITY / ARTIFACT STATE
    ↓
HASH CONTENT + LINK PREVIOUS EVENT
    ↓
ATOMIC APPEND + PROVIDER/STORE READBACK
    ↓
UPDATE WATERMARK
    ↓
RUN CONVERSATION EXHAUSTION GUARD
    ↓
CHECKPOINT / MIGRATE / CONTINUE
```

Capture precedes heavy reasoning and provider mutation so the prompt/event that triggered the
operation is already durable if the operation fails or the chat becomes terminal.

## Terminal rule

A visible terminal product warning changes the execution semantics:

- the last visible user command may be captured as `NOT_EXECUTED_TERMINAL`;
- it may not be represented as `EXECUTED_VERIFIED` without separate provider proof;
- no new same-chat state checkpoint is claimed;
- the ledger may be sealed at the last observed event;
- recovery moves to a successor chat; and
- the successor replays the exact captured sequence before resuming the next action.

This directly prevents the failure in which `chatbridge - LEX` appeared after the terminal
warning and was mistakenly treated as an executed restore command.

## Corrections and evolving understanding

Historical events are immutable. A later correction is a new `CORRECTION` event referencing
the earlier sequence or source ID. The transcript therefore preserves:

- what was said;
- what was later found wrong;
- when the correction occurred;
- which state superseded which; and
- the evidence basis for the change.

## Attachments and tool events

Conversation text is not enough when meaning depends on an attachment, connector result or
tool action. FFCL records stable references containing:

- artifact key;
- filename;
- MIME type;
- byte size;
- SHA-256 where available;
- durable locator;
- availability state; and
- whether the artifact is required to reconstruct context.

Tool calls and tool results are separate ordered events. Execution state distinguishes a
request, verified result, verified failure and unverified outcome.

## Privacy and matter walls

Full fidelity does not mean uncontrolled copying.

The default policy is governed local storage with minimum-necessary access. An event can be
stored as raw governed content, redacted content, hash-only or pointer-only. Any downgrade
prevents an exact-content claim unless the payload can be independently resolved during
restore.

Sensitive matter transcripts remain in their governed workstream store. Federation-wide
learning receives only sanitized operational patterns and evidence pointers.

Encryption at rest, key management and provider deployment are separate infrastructure gates.
The provider-neutral SQLite implementation does not claim those controls merely because the
ledger schema exists.

## Legacy import

For a conversation created before Ω4.8:

1. obtain the strongest available primary source, such as a ChatGPT data export, shared
   conversation copy, browser archive or complete provider transcript;
2. preserve original order, role, timestamps and identifiers;
3. import in ascending sequence;
4. allow explicit gaps only when the source is incomplete;
5. seal with the best supported first/last watermarks;
6. verify hashes and dependencies; and
7. classify the result as exact or bounded.

A screenshot or final checkpoint can support a bounded restore. It cannot supply messages
that are absent from every source.

## Failure modes

FFCL fails closed on:

- conversation ID or namespace conflict;
- sequence reuse with different content;
- idempotency-key reuse with different content;
- out-of-order or skipped event without explicit legacy-gap authority;
- mutation after sealing;
- hash-chain or Merkle inconsistency;
- exact restore request against incomplete coverage;
- terminal execution claim without proof; and
- unresolved required attachment dependencies.

## Runtime boundary

The source implementation can preserve every event it receives. It cannot invisibly read all
native ChatGPT conversations. Full protection therefore requires a provider/client adapter,
ChatGPT App, browser companion or another authorised event source to call the capture method
on every observable event.

Deployment proof must separately establish:

- the adapter is active;
- all intended event classes reach the ledger;
- capture occurs before risky operations;
- storage and access controls are enforced;
- independent restore can reconstruct a real long conversation; and
- provider readback matches the local ledger receipt.

Until then, Ω4.8 is source-complete and deterministically testable, while universal native
coverage remains a separate provider-live gate.
