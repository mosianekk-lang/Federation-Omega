# JARVIS Ultimate ↔ Federation Omega GCP Admin MCP v0.2.2

## Status

`SOURCE_READY_PROVIDER_DISABLED`

This stacked candidate binds the JARVIS Ultimate v1.4/T20 control plane to the exact published Federation Omega GCP Admin MCP v0.2.2 contract without enabling any provider transport or external effect.

## Exact source binding

- JARVIS/T20 base head: `b6d95e15fd1b63fecabb63d00fd3565989fcfaf0`
- T20 policy: `T20-AO-OMEGA-SCIENTIST-1.1`
- GCP Admin MCP PR: `#534`
- MCP candidate head: `bec80d87c5bb05e8a6a1a4453c71aef3d1d02ad6`
- MCP service tree: `c72557e541a1be9c1b5205c79f5a18b9f3caf473`
- MCP server version: `0.2.2`
- Exact tool count: 17

The machine-readable contract is packaged at `jarvis/resources/gcp_admin_mcp_adapter_v1.json`.

## Current behaviour

The adapter:

1. recognizes only the 17 exact v0.2.2 tool names and input fields;
2. rejects unknown fields and unknown tools;
3. exposes 14 read-only tools and three effectful tools as distinct risk classes;
4. rejects approval tokens, credentials, secret values and private keys at this disabled boundary;
5. hashes request arguments instead of persisting or returning their raw values;
6. always reports `NO_EFFECTS_EXECUTED`;
7. always refuses provider invocation with `GCP_ADMIN_MCP_PROVIDER_ROUTE_DISABLED`;
8. treats `/healthz` and `transport_liveness_only` as liveness only, never deployment proof;
9. validates fresh global and MCP-specific WIF receipts separately;
10. validates exact two-pass source → image digest → revision → private IAM → traffic lineage;
11. supports a separate rollback-lineage gate that must pass before any future promotion decision.

## Authority separation

The following lanes remain independent and disabled:

- inventory/read;
- canary;
- deployment;
- promotion.

A read-only provider route cannot inherit deployment or promotion authority. A successful health check cannot mint lineage proof. An MCP tool result cannot mint its own WIF authority. A promotion route cannot activate without separately verified rollback lineage and explicit owner authority.

## Required future proof

A later provider-enable patch must require all of the following as fresh, exact readback:

- `FEDOMEGA-WIF-CLOUD-VERIFIED` from the canonical global WIF verifier;
- `FEDOMEGA-GCP-ADMIN-MCP-WIF-VERIFIED` from the v0.2.2 service-specific numeric-identity verifier;
- `gcp_deployment_lineage_attest` with state `ATTESTED` and proof boundary `provider_identifiers_matched_across_two_independent_reads`;
- identical pass-one and pass-two joins;
- immutable `sha256:` image digest;
- immutable source identity and verification hashes;
- exact Cloud Run revision and traffic readback;
- private IAM with no `allUsers` or `allAuthenticatedUsers`;
- verified rollback lineage before any promotion.

## Non-effects

This candidate does not:

- discover or read credential values;
- create service-account keys;
- mutate IAM;
- enable a provider route;
- deploy a service;
- change Cloud Run traffic;
- promote a revision;
- send, draft or forward email;
- restore chat, case or unrelated workstream data;
- change `main`.

## Next best automated pathway

Admit this stacked source candidate through the existing Federation Airlock, Leak Guard and Bubbles controls. Keep it unmerged. After PRs #534, #546 and #548 are admitted in dependency order, obtain fresh provider-native WIF and two-pass lineage receipts in a trusted runtime. Only then prepare a separate, narrowly scoped provider-enable patch; do not modify this disabled adapter in place without new tests and exact readback.
