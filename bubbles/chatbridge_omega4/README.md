# ChatBridge Ω4 — Governed Durable Conversation OS

ChatBridge Ω4 is a source-backed continuity kernel for preserving and restoring governed
conversation state without pretending that a summary is a verbatim transcript.

The current source generation is **ChatBridge Ω4.9**. It combines:

- Ω4.7 Conversation Exhaustion Guard and empirical playbook;
- Ω4.8 Full-Fidelity Conversation Ledger (FFCL); and
- Ω4.9 Alpha→Omega multi-path / multi-stream capture assurance.

## What Ω4.9 adds

A single capture route can fail, truncate, misorder or contradict another route. Ω4.9
therefore registers multiple acquisition paths and conversation streams around one exact
source conversation identity.

Capture paths include provider API/export, rendered DOM, browser archive, shared
transcript, connector readback, attachment store and checkpoint capsule. Streams include
user, assistant, system, developer, tool call/result, connector, attachment, decision,
correction, checkpoint and terminal events.

The runtime:

- binds every path and stream to an exact `conversation_key` and namespace;
- stages out-of-order observations until the missing earlier sequence arrives;
- deduplicates identical observations across paths;
- quarantines same-identity/different-payload conflicts;
- ranks failover routes with AO-HARMONIC's `FormationEngine`;
- appends one stable canonical event to FFCL;
- preserves path corroboration outside the FFCL event hash so later evidence cannot mutate
  the canonical chain;
- verifies global and per-stream watermarks;
- distinguishes exact single-path transcript recovery from stronger multi-path/multi-stream
  assurance;
- emits sequence-preserving, hash-addressed replay chunks below the configured payload
  budget; and
- never treats terminal-visible intent as executed work.

See:

- `ALPHA_OMEGA_MULTIPATH_MULTISTREAM.md`
- `FULL_FIDELITY_CONVERSATION_LEDGER.md`
- `CONVERSATION_EXHAUSTION_AND_EMPIRICAL_PLAYBOOK.md`
- `governance/chatbridge_alpha_omega_multipath_multistream_v1.json`
- `governance/chatbridge_full_fidelity_ledger_v1.json`

## Current runtime

Package-level imports use Ω4.9:

```python
from bubbles.chatbridge_omega4 import ChatBridgeOmega4
```

Explicit versions remain available:

- `ChatBridgeOmega49` — current Alpha→Omega multi-path/multi-stream runtime;
- `ChatBridgeOmega48` — FFCL runtime;
- `ChatBridgeOmega47` — exhaustion-guard runtime.

## Restore modes

Ω4.9 produces these assurance modes:

- `EXACT_MULTIPATH_MULTISTREAM_RESTORE`
- `EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE`
- `BOUNDED_MULTIPATH_MULTISTREAM_RESTORE`
- `REJECT_CONFLICTED`
- `NO_ALPHA_OMEGA_CAPTURE`

The strongest mode requires:

1. exact sealed FFCL coverage from declared start to finish;
2. explicit global sequence for every event;
3. complete required stream watermarks;
4. at least two independent path groups supporting every canonical event;
5. no unresolved critical conflict; and
6. all required payloads and artifacts available.

Anything weaker remains useful but is labelled precisely rather than promoted.

## Identity and continuity stack

```text
Exact source conversation_key
    ↓
Human namespace / immutable namespace_id
    ↓
Generation / immutable handoff_id / checkpoint fingerprint
    ↓
Governance Capsule / Operating Profile
    ↓
HOT / WARM / COLD continuity state
    ↓
Conversation Exhaustion Guard checkpoint
    ↓
Alpha→Omega PATH_REGISTER + STREAM_REGISTER
    ↓
Full-Fidelity Conversation Ledger
    ↓
Ordered event hashes + chain head + Merkle root
    ↓
Stream watermarks + path corroboration + conflict/gap ledger
    ↓
Token-bounded replay chunks
    ↓
Provider continuation reference
    ↓
Exact next action
```

## Example

```python
from bubbles.chatbridge_omega4 import (
    CaptureObservation,
    CapturePath,
    CapturePathKind,
    ChatBridgeOmega4,
    ConversationStream,
    StreamExpectation,
)

runtime = ChatBridgeOmega4(store)
runtime.register_capture_path(
    CapturePath(
        conversation_key="native-conversation-id",
        path_id="provider-export",
        kind=CapturePathKind.NATIVE_EXPORT,
        source_provider="CHATGPT_EXPORT",
        independent_group="provider-native",
        authoritative=True,
    )
)

runtime.capture_multipath_stream_events([observation])
runtime.declare_stream_expectations(
    "native-conversation-id",
    [StreamExpectation(ConversationStream.USER, 1, 12)],
)
runtime.finalize_multipath_stream_capture(
    "native-conversation-id",
    "exact-namespace",
    expected_last_sequence=37,
)
```

## Deterministic test suites

Run from repository root:

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
  bubbles.chatbridge_omega4.test_alpha_omega_capture \
  bubbles.chatbridge_omega4.test_runtime_omega49 \
  -v
```

## Legacy conversation recovery

Ω4.9 can reconcile available native exports, shared transcripts, browser archives,
rendered DOM captures, connector readbacks, attachment stores and prior checkpoints.
It cannot create a message that was never captured or exported. An older chat becomes exact
only when a complete primary transcript exists and the sequence/integrity gates pass.

## Provider boundary

The code can preserve every event delivered by an authorised adapter. It does **not**
invisibly read every native ChatGPT conversation. Browser installation, signed-in session
binding, live warning interception and provider-wide capture remain separate gates that
require provider-native readback.

Maturity is always separated:

```text
BUILT → TESTED → MERGED → INSTALLED → BOUND → RUNNING → READ_BACK → ACCEPTED
```

A hash-valid record proves record integrity, not the truth of every statement contained in
that record. Source completeness, factual truth and provider execution remain distinct.
