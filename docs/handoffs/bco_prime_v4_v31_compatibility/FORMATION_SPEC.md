# Formation specification — BCΩ-PRIME v4 compatibility

## Mission

Mission `CFBE-BCO-V4-COMPAT-20260902`, version 1, implements one additive local
adapter over the exact v3.1 and v4 sources. Classification is `PROD FOUNDATION`
library, CLI, integration adapter, and test suite. The governing action is the
single-use `A1-LOCAL-BUILD` permit supplied by the parent Formation cycle.

## Boundaries

| Boundary | Decision |
|---|---|
| Frontend | Not applicable; Python and CLI only. |
| Backend | Adapter validates and routes three v4 operations or delegates unchanged to v3.1. |
| Database / queue / scheduler / cache | Not applicable; no new persistence or background runtime. |
| Worker | The invoking Python process only; nothing survives return. |
| Storage | Caller-selected local v3.1 workspace; adapter adds no state root. |
| Authentication | No credentials; source identity is pinned by Git/SHA-256 evidence. |
| Provider effect | Prohibited. |
| Dispatch | Prohibited. |
| Source mutation | Prohibited at runtime. |
| Stable promotion | Prohibited. |

## Lifecycle

`REQUESTED -> VALIDATED -> DELEGATED_OR_COMPILED -> RECEIPT_RETURNED`

Any invalid input, unknown operation, dependency absence, authority request, or
inherited v3.1 hold moves to `REJECTED` or `BLOCKED_WITH_ROUTE`. The adapter does
not retry and cannot promote a held state.

## Compatibility invariant

For every operation outside `V4_OPERATIONS`, the adapter calls the attested exact
v3.1 registry once and returns its receipt unchanged. Therefore v3.1 namespaces,
schemas, operation counts, input digests, output semantics, and authority flags
remain owned by v3.1. Health and manifest are additive views; they do not modify
the base registry.

## Input and output controls

- Inputs must be finite JSON-compatible values with string object keys.
- V4 objects have explicit field allowlists, required fields, scalar types,
  numeric ranges, and bounded list/count controls.
- Authority and executable-effect key variants are normalized and rejected when
  truthy at any depth.
- V4 dataclasses are converted to canonical JSON values; every receipt is bound
  by SHA-256 over sorted compact JSON.
- External-effect observations may drive `HOLD_PROVIDER`, but output authority is
  always false.

## Failure controls

- `INVALID_INPUT`: typed rejection before v4 compilation.
- `AUTHORIZATION_FAILURE`: authority/effect requests fail closed.
- `TIMEOUT`: no retry, network, scheduler, or unbounded loop is added; collection
  sizes and numeric counts are bounded.
- `PARTIAL_WRITE`: adapter produces no write; inherited v3.1 operations retain
  their existing atomic/ledger controls.
- `MISSING_CONFIGURATION`: missing exact v3.1 closure returns
  `V31_REGISTRY_UNAVAILABLE` with its pinned closure test.
- `EXTERNAL_API_FAILURE`: not applicable; there is no external API.

## Observability and proof

Health exposes source main, inherited health, compatibility mode, operation
counts, and all authority flags. Manifest adds exact component hashes and the
authority boundary. Receipts include operation, namespace, input hash, main SHA,
output, and receipt hash. Tests cover unit, integration, deterministic reorder,
failure-first, security, authority, and inherited path traversal behavior.

## Rollback and stop

Stop by terminating the invoking process. Roll back by deleting/reverting only
the additive adapter, test, contract, and four handoff files. The v3.1 and v4
source baselines remain unchanged. Re-materialize from pinned identities and
rerun the documented proof sequence to restore.
