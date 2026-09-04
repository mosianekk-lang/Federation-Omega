# MODISA Federation–KDV Cognitive Mesh Convergence Kernel v1.1

## Decision

Do not create another sovereign brain, event bus, capability graph, or memory root. Reuse `FEDERATION-OMNI-MESH-V1`, `KDV-GEN2-FTSC-v0`, BMF event sourcing, the unified capability graph, MissionIR and MODISA v3 receiver adaptation. FKCM is the compatibility/convergence compiler between those existing planes.

## Data flow

`source/provider delta -> existing Mesh topic -> FKCM normalizer -> event-first state/relation compilation -> KDV-GEN2 shadow projections -> dependency-impact router -> affected receivers only -> bounded Mission Context Capsule -> MODISA/SOVARA/Bubbles -> native readback -> proof/learning event`

## v1.1 BMF semantic bridge

The live dual-run proved that BMF compatibility must be semantic, not merely structural. FKCM therefore reproduces the existing BMF projection contract:

- order by `(recorded_at, stream_version, event_id)`;
- merge flat payloads for `STATE_SET`, `DECISION_ACCEPTED`, `RESULT_VERIFIED`, `BLOCKER_SET`, and `NEXT_ACTION_SET`;
- remove named keys for `STATE_UNSET`;
- preserve directive, mission, supersession and contradiction lineage;
- derive BMF entity identity from `stream_id`, never from mission identity; and
- reproduce provider-readback projection hashes before any cutover can be considered.

The BMF-specific compatibility layer is narrow. Native FKCM events retain their bitemporal ordering and typed-field semantics.

## Derived relationship projection

FKCM proposes one reproducible KDV-GEN2 projection, not a new authority store:

`ENTITY_RELATIONS(Relation_ID, Subject_Entity_ID, Predicate, Object_Entity_ID, Source_Event_ID, Authority_Source, Truth_Class, Privacy_Class, Valid_From, Superseded_By, Compiled_At, Relation_SHA256)`

## Core invariants

1. Events are append-only; current state is derived.
2. Provider-current claims require a query-time source lease.
3. Source, runtime, provider, behavior and value proofs do not inherit.
4. Authority and maturity do not propagate through graph edges.
5. Unknown nodes default read-only/shadow.
6. Dependency impact wakes only affected receivers.
7. Context capsules are bounded and provenance-carrying.
8. Shadow mode admits only NONE/READ_ONLY effects.
9. Mutable projection writes require compare-and-set, minimum changed cells and readback.
10. GEN1 remains fallback until equivalence, recovery and value gates pass.
11. A compatibility adapter cannot claim equivalence until it reproduces the incumbent projection on real persisted data.
