# ChatBridge Ω4.2 — Completion Witness Contract

ChatBridge should not repeatedly ask the owner to confirm work that a connected system can independently observe.

## Operating rule

At the start of a turn, after a tool callback, and before asking the owner to repeat a completed setup step, reconcile every pending user task against the strongest available completion evidence.

Evidence precedence for completion:

1. provider readback;
2. tool receipt;
3. app callback;
4. API webhook event;
5. owner assertion;
6. opaque UI state with no callback/readback.

A provider/app receipt can promote a task to `PROVIDER_VERIFIED_COMPLETED`.

An owner statement such as `done` can promote a task to `OWNER_ASSERTED_COMPLETED`. That is sufficient to continue safe internal preparation when policy allows, but it must not be described as provider-verified if the underlying UI action is not independently observable.

## Automatic continuation

When a reconciled task becomes complete, ChatBridge should automatically:

- log the task state and evidence reference;
- clear the stale user blocker;
- identify the recorded continuation action;
- continue safe non-consequential execution in the same turn where possible;
- preserve any consequential approval gate;
- keep provider-live claims blocked until the required provider readback exists.

## Platform-owned UI boundary

A system cannot observe arbitrary clicks in a platform-owned interface merely because the user clicked a visible button. For example, if a secure key-creation widget does not expose a completion callback or a key-list/readback action to the connected tool surface, the click itself is `UI_OPAQUE`.

The system should therefore avoid two bad behaviours:

1. pretending the click was automatically witnessed; or
2. stopping all useful work until the user repeats a confirmation that is only needed for proof.

The correct state is `OWNER_ASSERTED_COMPLETED` when the user reports completion, with automatic continuation of safe work and a separate provider-readback gate for any terminal provider claim.

## Event-ready evolution

Where a future app/widget exposes its own action callback, or where an API operation emits a supported webhook/provider event, the same task can be upgraded automatically from `PENDING` to `PROVIDER_VERIFIED_COMPLETED` without requiring the owner to type `done`.

OpenAI API webhooks apply to supported API events; they are not a generic observer for arbitrary dashboard or ChatGPT UI button clicks.
