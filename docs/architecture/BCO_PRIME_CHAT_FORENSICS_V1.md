# BCO-Prime Chat Forensics v1

## Outcome

BCO-Prime Chat Forensics v1 is an additive, deterministic capability pack for auditing stalled, blank-terminal, overloaded, or contradictory conversation runs from evidence already captured by authorized adapters. It adds 24 functions and does not change the canonical BCO-Prime 100-capability invariant.

## Algorithm

1. Bind the expected and observed conversation ID and exact title. Fail closed on a collision.
2. Inventory and rank every accessible source. Prefer native export; otherwise route through labeled fallbacks.
3. Scope-filter evidence, canonicalize it, and produce a tamper-evident event chain without echoing raw content.
4. Reconstruct the terminal sequence: last user instruction, execution steps, final tool action, and visible response commit.
5. Classify failure only to the available proof ceiling. A blank terminal after a tool action is FINAL_OUTPUT_COMMIT_FAILURE; an exact server cause remains UNVERIFIED without native telemetry.
6. Separate workload and connector pressure from proven causation.
7. Require a pinned provider reference and matching artifacts before declaring provider durability.
8. Compare promised outputs with proven fruit.
9. Map the audit to CFF states: COMPLETE_VERIFIED, PARTIAL_CHECKPOINTED, or AUDIT_BLOCKED.
10. Emit deterministic extension receipts plus reusable receipts from the canonical BCO-Prime core.

## Capability map

| Domain | Operations |
|---|---|
| Acquisition | bind conversation identity; inventory sources; rank sources; capability probe |
| Normalization | scope filter; fallback route; canonical hash; event chain |
| Completion | timestamp coverage; terminal event; blank turn; trace lineage |
| Failure | finalization failure; checkpoint gap; workload pressure; connector pressure |
| Proof | error provenance; provider durability; claim-fruit; CFF status |
| Recovery | SHIELD state; recovery plan; audit receipt; harvest summary |

## Boundaries

- Authority ceiling: A1_INTERNAL.
- Effects: none. The pack does not browse, write providers, dispatch actions, or obtain credentials.
- Inputs: bounded evidence metadata and hashes supplied by an authorized caller.
- Privacy: raw evidence is hashed; receipts contain identifiers and bounded metadata only.
- Truth: hidden prompts, deleted messages, native token counters, router state, and exact backend exceptions remain unverified unless supplied by a trusted native source.
- Promotion: tests can prove local deterministic behavior only. Operational promotion still requires independent provider readback and observed value.

## CLI

The module exposes list, run, and audit commands through Python module execution. Payloads are JSON mappings. Unknown capabilities, identity collisions, manual-user tasks, external effects, and authority expansion fail closed.

## Recovery invariant

Before a long-running assistant turn finalizes, the execution layer should persist a bounded checkpoint, emit a finalization receipt, and independently read back any claimed provider artifact. Failure of the user-visible response must not erase the last proven execution state.
