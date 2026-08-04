# Alpha→Omega Phoenix Authorized Execution v25

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

## Material operational slice

V25 binds the v20 exact owner-authorization decision, v21 one-time authorization-consumption state machine, Phoenix v3.1 provider controller and a new authorization-enforced Ops entrypoint into one fail-closed provider execution package.

Before any provider apply, the coordinator verifies the exact decision, source commit, Core and Ops archive digests, accepted provider-authority mode, execution identity and provider-authority presence. Missing provider authority does not consume the authorization.

After durable `APPLY_STARTED`, a missing, unreadable or semantically invalid provider receipt becomes `PROVIDER_OUTCOME_RECONCILIATION_REQUIRED`. The same authorization is never automatically retried. A later run may only admit an existing receipt that passes embedded SHA-256 integrity and exact provider semantic readback, including after the original authorization has expired. Exact verified retries are idempotent and cross-execution replay is rejected.

## Provider-native proof

The repair PR #225 passed the Federation Omega Airlock, the Public Repository Leak Guard, 52 Phoenix v3-family tests including 11 authorized-executor tests, and six export regressions. It merged at `90248d6f95f28b0cafce359405665f1c78724450`. PR #226 then added the fail-fast stale-base ancestry gate and established current final head `3a715d0ac00501c045b856569c81242fdc05bca6`.

Final-head Phoenix run `30949262846`, job `92126950928`, published `phoenix-freeze/verified = success` and exact immutable artifacts:

- Cutover artifact `8908396862`, digest `sha256:1fef9271987dab8b2c4c925d201a87cb0deff3ebcab73f4cadb926e2cf37e366`.
- Freeze artifact `8908396404`, digest `sha256:12a1d3214b402abfbb6f39742211474ba3055b2aa7d23091f4a075d9033fed1d`.
- Core archive SHA-256 `5141dbfaad0e0d059ff1aa8dc9d7919f0a9008f90afad0b02dd988014510e368`.
- Ops archive SHA-256 `72184d5235e09019017af49314239c950de12853e133f36017d8f6113b6166b0`.
- Export receipt SHA-256 `01e59233b647ed907b70d3254946ca49fc67fed071fc9e44275f400b7c8f936f`.

## Provenance discrepancy record

The initial v25 implementation files were written directly to `main` because the connector branch parameter was supplied incorrectly. Provider-native Phoenix verification then exposed an over-strict base-export fixture contract. The defect was repaired through PR #225 and the final head passed all required Phoenix proof gates.

The release does **not** claim retroactive Airlock admission for the earlier direct writes. It records them explicitly as `DIRECT_MAIN_WRITES_DETECTED_AND_REPAIRED_NO_RETROACTIVE_AIRLOCK_ADMISSION_CLAIMED`.

## Google Drive release

Private release file: `1AIfd_i_LbF_rhhTOUC8GLEGNRoR8XRbrIQgxzVQ0dGY`.

Fresh readback and permission inspection verified owner-only access, a 4,562-byte text export and SHA-256 `4dce6469d1c4e8297ed1adfcaa9b885f28122e8b719e88f12d10c1aa66c61aa7`.

## Commercial boundary

The service-enabled platform remains prioritised and self-service SaaS remains held. No Core or private Ops repository was created, no provider apply occurred, no Cloud Run operation was proven, no payment-provider operation was performed, and no demand, customer contract, enterprise assurance, partner adoption, production scale or revenue event is claimed.

The next consequential gate remains `PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED`. It requires a fresh short-lived exact owner authorization and suitable GitHub provider authority in the separate private Ops execution plane. Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
