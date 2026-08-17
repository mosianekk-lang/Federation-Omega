# ChatBridge Ω4.9 — Alpha→Omega Multi-Path / Multi-Stream Conversation Assurance

## Purpose

ChatBridge Ω4.8 solved the core storage problem: every event delivered by an authorised
adapter can be preserved in an append-only, hash-chained Full-Fidelity Conversation
Ledger (FFCL). Ω4.9 addresses the next failure mode: one acquisition route can miss,
misorder, duplicate, truncate or contradict another route.

Ω4.9 therefore composes the proven AO-HARMONIC route discipline with FFCL. It treats
conversation recovery as a multi-path, multi-stream evidence problem rather than a single
summary or checkpoint problem.

## Alpha→Omega cycle

```text
ALPHA_BIND
  exact conversation key + exact namespace
      ↓
PATH_DISCOVERY
  provider API / export / rendered DOM / browser archive / shared transcript /
  connector readback / attachment store / checkpoint capsule
      ↓
STREAM_DISCOVERY
  user / assistant / system / developer / tool call / tool result / connector /
  attachment / decision / correction / checkpoint / terminal
      ↓
STAGE
  preserve every observation with its source path, source IDs and raw payload
      ↓
RECONCILE
  deduplicate identical observations and rank eligible routes with FormationEngine
      ↓
CONFLICT_AND_GAP_TEST
  quarantine contradictory payloads, sequence collisions and missing ranges
      ↓
CANONICAL_APPEND
  append one stable event to FFCL with explicit global ordering authority
      ↓
OMEGA_COMPLETION_WITNESS
  test FFCL completeness, stream watermarks, independent path corroboration and findings
      ↓
REPLAY
  emit sequence-preserving, hash-addressed, token-bounded replay chunks
      ↓
READBACK
  restore exact only when all gates pass; otherwise return a bounded gap manifest
```

## Path register

Every source route is registered against one exact conversation. A path record includes:

- path identity and path kind;
- source provider;
- availability state;
- proof strength, completeness, freshness and speed;
- privacy, maintenance and owner-burden costs;
- independent evidence group; and
- whether the source is authoritative.

AO-HARMONIC's `FormationEngine` ranks routes. A failed route does not freeze the
objective. ChatBridge moves to the next eligible route, while preserving the failed route
and any evidence it already captured. A route failure is not treated as an objective
failure.

## Stream register

Global event order and per-stream order are both preserved. The source adapter may declare
expected first/last watermarks for each required stream. Exact Alpha→Omega promotion
requires every required stream to be complete.

A globally complete transcript can still be classified as `EXACT_SINGLE_PATH_TRANSCRIPT`
when the FFCL range is complete but multi-path or multi-stream assurance is absent. That is
useful and honest, but it is not the stronger Ω4.9 assurance state.

## Reconciliation rules

1. Same source identity + same payload = idempotent duplicate or corroboration.
2. Same source identity + different payload = critical conflict; fail closed.
3. Same event observed through independent paths = one canonical FFCL event plus a
   corroboration manifest.
4. Explicit provider/global sequence controls ordering where available.
5. Derived timestamp order is allowed only for bounded recovery and blocks the strongest
   exact promotion.
6. Out-of-order events are staged until the missing prior sequence arrives.
7. Missing events are never synthesized.
8. Corrections append; they do not rewrite history.
9. Terminal-visible intent is not execution.
10. Path-specific source metadata remains in the Alpha→Omega tables so later
    corroboration cannot mutate the canonical FFCL hash.

## Restore modes

- `EXACT_MULTIPATH_MULTISTREAM_RESTORE`
  - FFCL is sealed and exact;
  - every canonical event has explicit global ordering;
  - required stream watermarks are complete;
  - every canonical event is corroborated by at least two independent path groups;
  - no critical conflict is open.

- `EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE`
  - FFCL is sealed and exact, but one or more Ω4.9 assurance gates are absent.

- `BOUNDED_MULTIPATH_MULTISTREAM_RESTORE`
  - captured content can be replayed, but a sequence, stream, dependency, ordering or
    corroboration gap remains explicit.

- `REJECT_CONFLICTED`
  - a critical path/content/sequence conflict or FFCL integrity failure remains open.

- `NO_ALPHA_OMEGA_CAPTURE`
  - no Ω4.9 canonical capture exists for the conversation.

## Token-bounded replay

Large transcripts are replayed in canonical sequence using chunks below the configured
budget (default 3,800 approximate tokens). Event boundaries are preserved where possible.
An oversized event is fragmented with:

- original sequence;
- fragment index/count;
- original content SHA-256;
- reassembly policy; and
- chunk SHA-256.

This avoids provider-payload overload without losing the original event.

## Legacy recovery

Older chats can be imported through several paths:

- native ChatGPT export;
- shared conversation transcript;
- browser archive;
- rendered DOM capture;
- connector/provider readback;
- verified attachments and artefact stores; and
- prior ChatBridge checkpoints.

The engine reconciles what exists. It cannot create messages that were never captured or
exported. Exact recovery of an older chat is possible only when a complete primary
transcript source exists.

## Provider boundary

Ω4.9 is a provider-neutral source/runtime implementation. It cannot invisibly read every
native ChatGPT conversation. A browser companion, ChatGPT App, provider API/export or
another authorised client adapter must deliver the observable events.

Therefore these maturity states remain separate:

```text
BUILT → TESTED → MERGED → INSTALLED → BOUND → RUNNING → READ_BACK → ACCEPTED
```

Source and deterministic tests do not prove browser installation, signed-in session
binding or universal provider coverage. Those require provider-native readback.
