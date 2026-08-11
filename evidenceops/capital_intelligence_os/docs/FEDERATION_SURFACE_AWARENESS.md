# Federation Omega Surface Awareness

## Purpose

This contract gives Federation Omega, the Formation Innovation Engine, the Alpha-to-Omega Foundry, Secondary Brain and Kim Dataverse adapters a shared startup view of the authorised operating estate.

It is intentionally split into two planes:

1. **Public-safe contract plane** — GitHub stores aliases, schemas, hashes, startup order, freshness rules and truth boundaries.
2. **Private exact-pointer plane** — Kim Dataverse resolves exact Drive, Gmail and provider metadata through `FEDERATION_AWARENESS_PRIVATE_V1`.

No credential value is stored in either plane.

## Startup command

The current startup block is `NCB-002`, represented by the reusable command:

`restore federation awareness`

The bootstrap must read current GitHub source, verify the public awareness contract, resolve and hash-check the private manifest, read current canonical state and route authority, initialise Formation and Alpha-to-Omega, load the current startup pointer, and revalidate the selected provider route before execution.

## Credential and authority model

Credential records are capability handles, not secret values. A handle may identify a platform-managed connector session, an environment variable name, a provider vault reference or a route-specific identity contract.

A stored handle does not prove:

- that the credential is currently available;
- that it has the required scope;
- that it is fresh;
- that it belongs to the expected identity;
- that the target exists;
- that a provider action succeeded.

Every material provider route requires fresh identity, target, scope, action and readback verification. Consequential actions remain owner-reserved.

## Continuity model

Gmail messages, restore capsules and historical registers are source evidence and lineage. They are not automatically current runtime state. Historical restore rows remain preserved, but `NCB-002` and later compatible blocks control current startup priority.

The system does not claim invisible access to closed chats, universal cross-chat memory or an unauthorised background runtime. Context is loaded through authorised connectors and current canonical pointers.

## Formation and innovation model

The Formation Innovation Engine and Alpha-to-Omega Foundry remain mandatory for non-trivial work. Surface awareness occurs before route formation so the engines can:

- distinguish real capabilities from stored claims;
- reuse verified assets before rebuilding;
- compare available execution surfaces;
- preserve rejected routes and negative results;
- avoid authority overclaim;
- choose the strongest evidence-matched path;
- produce proof and terminal learning events.

## Failure behaviour

The awareness bootstrap fails closed when the public contract is missing, the private alias cannot be resolved, the private hash mismatches, current route state cannot be read, a credential handle is unavailable, provider authority is unverified or secret material is detected.

The fallback is limited to independently verified public-safe source and read-only analysis until the affected private or provider route is restored.
