# FKPF-Ω∞ v3 — Federation Sovereign Cognitive Execution Fabric

## Objective
Make a verified discovery anywhere in the Federation become usable, receiver-specific, policy-compliant and independently provable everywhere it belongs, without copying authority, matter scope, maturity or factual truth between systems.

## Six constitutional planes

1. **Mission Plane** — owner objective → deterministic `MissionIR`, dependency graph and idempotency key.
2. **Knowledge Plane** — append-only content-addressed Knowledge Deltas, receiver ACKs, watermarks, supersession and replay.
3. **Execution Plane** — durable workflow, replayable event distribution, A2A agent discovery and MCP tool boundaries.
4. **Proof Plane** — source proof, semantic/provider readback, independent verifier, artifact attestation and behavioural canaries.
5. **Authority Plane** — policy-as-code, workload identity, authority/effect ceilings, privacy and matter walls.
6. **Evolution Plane** — failure fingerprints, semantic retry, circuit breaking, counterfactual replay and owner-value measurement.

## Hard truth-state separation

`DESCRIBED != BUILT != TESTED != SOURCE_ADMITTED != PROVIDER_READBACK != BEHAVIOUR_VERIFIED != VALUE_OBSERVED`

Knowledge propagation never transfers:
- legal factual truth;
- provider authority;
- credentials or secret values;
- matter scope or privacy permission;
- deployment/running state;
- owner approval;
- maturity or value proof.

## Event lifecycle

`DISCOVER -> SEAL -> SIGN -> PUBLISH -> RECEIVE -> COMPATIBILITY -> POLICY -> ADOPT/ADAPT/HOLD/N-A -> APPLY -> READBACK -> INDEPENDENT VERIFY -> BEHAVIOUR CANARY -> VALUE -> STANDARD/SUPERSEDE`

A node may claim `ACTIVE_CURRENT` only when its local propagation watermark equals the canonical head or every newer applicable delta has an explicit disposition.

## Current protocol/technology targets

- **A2A 1.0** — horizontal independent-agent discovery, capability description and task interoperability.
- **MCP 2026-07-28+ generation** — vertical tools/data/context boundary with strict authority/effect contracts.
- **Temporal** — durable workflow target. The Python state machine is the deterministic local reference adapter.
- **NATS JetStream** — replayable event-distribution target. `ReplayBus` is the local reference adapter.
- **OPA/Rego** — policy-as-code target; default deny and evidence/matter/authority firewalls.
- **SPIFFE/SPIRE** — short-lived workload identity target (`spiffe://federation.internal/...`). Trust-root/bootstrap remains separately qualified.
- **Sigstore/Cosign / GitHub attestations** — artifact/source/builder/test provenance target.
- **OpenTelemetry** — causal mission/tool/provider/readback traces and metrics.
- **PostgreSQL/object storage** — target structured/immutable persistence after shadow parity; current kernel uses SQLite for deterministic source tests.

## A2A and MCP relationship

A2A is the horizontal agent-to-agent plane: SOVARA can discover EvidenceOps, Lex, CFBE, Sentinel or ChatBridge through capability cards instead of hard-coded implementation knowledge.

MCP is the vertical agent-to-tool/data plane. Each MCP server declares allowed/denied tools, authority ceiling, effect ceiling, readback requirement and `no_raw_secret_values` invariant.

Neither protocol creates authority by itself.

## Failure-to-win semantics

Before a retry, normalize a `FailureFingerprint` from objective, route, target, provider, source epoch and error. Unchanged permission/auth/stale-provider/effect-unknown errors do not receive blind retries.

Examples:
- stale Sheets grid/revision ID → refresh provider metadata and recompile request;
- 403 → change authority or route;
- EFFECT_UNKNOWN → probe provider before any retry;
- timeout/502/503 → one bounded retry, then reroute/circuit break.

## Consequential-effect transaction

`PREPARE -> OWNER/EXACT AUTHORITY -> IDEMPOTENCY RESERVE -> EXECUTE -> PROVIDER READBACK -> INDEPENDENT VERIFY -> COMPLETE`

If the effect outcome is uncertain, state becomes `EFFECT_UNKNOWN` and retry is prohibited until provider probing resolves it.

## Workload identity target

Every runtime actor should eventually receive a short-lived workload identity such as:

`spiffe://federation.internal/evidenceops/verifier`

The identity is bound to MissionIR authority and effect ceilings. Static master tokens are not an architectural target.

## Proof-carrying artifacts

A releasable build should eventually bind:
- artifact SHA-256;
- exact source commit;
- builder workload identity;
- deterministic test receipt;
- SBOM reference;
- signature/attestation bundle;
- transparency/provenance reference where applicable;
- rollback target.

Source/CI proof does not establish provider deployment.

## Migration from FKPF v1 / canonical Head-2

1. Preserve Head-2 tables and Bibles as immutable provider-bound baseline.
2. Source-admit v3 as an extension of the existing Federation fabric, not a competing control plane.
3. Dual-write future deltas into existing CFBE propagation projection plus v3 adapter in shadow.
4. Add A2A/MCP discovery contracts without changing existing authority.
5. Run NATS/Temporal/OPA only as shadow adapters until parity, replay, failure and rollback tests pass.
6. Introduce workload identity and artifact signing only after exact trust-root/identity canaries.
7. Promote from shadow only after provider-native readback and prospective behavioural evidence.
8. Promote to `VALUE_OBSERVED` only from measured owner/operational outcomes.

## Production boundary

The repository source proves architecture and deterministic source tests only. It does not prove production NATS, Temporal, OPA, SPIRE, Sigstore, OpenTelemetry, PostgreSQL or A2A/MCP endpoints are deployed, nor does it create legal/external/provider authority.
