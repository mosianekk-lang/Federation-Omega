# ChatBridge Ω4.7 — Conversation Exhaustion Guard and Empirical ChatGPT Playbook

## Purpose

ChatBridge Ω4.7 prevents a long-running workstream from becoming unrecoverable when a
ChatGPT conversation reaches its product maximum-length boundary. It also turns qualified
operational experience from ChatBridge-active conversations into a governed empirical
playbook.

The design does not depend on a hidden remaining-token or remaining-conversation-quota
meter. No such meter is assumed. The guard uses observable risk signals and continuous
write-ahead checkpointing so that an unexpected terminal boundary has a bounded recovery
cost.

## Conversation Exhaustion Guard

### Invariant

No material workstream state may exist only inside the live conversation.

### Required sequence

```text
MATERIAL DELTA
    -> WRITE-AHEAD CHECKPOINT
    -> PROVIDER/STORE READBACK
    -> CONTINUE

HEAVY OPERATION
    -> PRE-OPERATION CHECKPOINT
    -> READBACK
    -> EXECUTE
    -> VERIFY RESULT
    -> DELTA CHECKPOINT
```

### Observable signals

The guard accepts only explicit signals supplied by the active runtime, including:

- substantive turn count;
- turns since the last checkpoint;
- estimated cumulative context characters;
- recent tool-output volume;
- large-output frequency;
- uncheckpointed material deltas;
- stream errors and retries;
- attachment volume;
- latency warnings;
- namespace binding and checkpoint-readback state;
- pending heavy operations; and
- an observed maximum-length warning.

The score is a conservative operational-risk estimate. It is not an OpenAI quota reading.

### States

- **GREEN** — normal operation, but every material delta and every pre-heavy-operation
  boundary still checkpoints.
- **AMBER** — increase checkpoint frequency, bind/repair the namespace and prepare a
  migration package.
- **RED** — stop nonessential expansion, create and verify a full HOT-state checkpoint and
  migrate before further major work.
- **TERMINAL** — do not pretend a new same-chat checkpoint can be created. Restore only
  from the last independently verified checkpoint and label any later unexternalised tail
  as a possible recovery gap.

## Empirical Playbook

### Scope

The learning fabric covers every conversation in which ChatBridge is actually active and
receives observable turn signals. It does not claim invisible access to every native
ChatGPT conversation or to hidden OpenAI telemetry.

### What is captured

Only minimum-necessary operational observations are eligible, such as:

- failure signatures;
- observable product behaviour;
- successful or failed recovery routes;
- provider-readback facts;
- reproduced canary outcomes;
- repair patterns;
- contradiction and supersession evidence; and
- bounded conversation-health measurements.

Raw transcripts, secrets, unrestricted medical information and matter-specific evidence are
not copied into the playbook. They remain in their governed source systems and are linked by
bounded evidence pointers where appropriate.

### Evidence hierarchy

1. Provider readback
2. Reproduced canary
3. Primary artifact
4. Official documentation
5. User-reported observation
6. System inference

Official documentation remains useful, but documentation alone cannot promote an empirical
playbook rule.

### Rule promotion

A rule may be promoted to all ChatBridge-active chats only when:

- at least two verified supporting events exist;
- they come from at least two independent conversations;
- at least one event has provider-readback or reproduced-canary support;
- no verified contradiction remains unresolved;
- all supporting events permit Federation operational sharing; and
- no event is matter-bound.

One verified event can establish a bounded rule, but not a global promoted rule. A verified
contradiction forces `HOLD_CONTRADICTION`. Documentation-only support forces
`HOLD_INSUFFICIENT_EMPIRICAL_PROOF`.

### Learning is not model-weight training

ChatBridge learning is durable operational state, tested rules and evidence-linked memory.
It does not claim to alter OpenAI model weights or to guarantee OpenAI platform behaviour.
Every rule carries evidence, scope, confidence and revalidation triggers.

## Persistence

The local provider-neutral kernel adds three SQLite WAL tables alongside ChatBridge's
existing namespace/generation store:

- `chat_learning_events`
- `chat_playbook_rules`
- `conversation_health_log`

Every event and rule is fingerprinted and read back after mutation. Existing event IDs are
idempotent only when their content matches exactly.

## Restore contract

Each restored Operating Profile carries:

- Conversation Exhaustion Guard enabled;
- continuous write-ahead checkpointing enabled;
- checkpoint and migration policies;
- empirical learning enabled;
- learning capture scope and privacy policy; and
- the current playbook authority boundary.

Restore assurance must verify that these controls survived the handoff before declaring the
workstream fully conformed.

## Current proof boundary

The source and deterministic regression suite prove the provider-neutral control logic. They
do not prove an invisible ChatGPT hook, automatic interception of every product conversation,
provider deployment or guaranteed detection of the exact final permissible turn. Live
provider and cross-chat canaries remain separately evidence-gated.
