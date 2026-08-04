# Alpha→Omega Phoenix Authorized Execution v25

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

## Material operational slice

V25 binds the v20 exact owner-authorization decision, v21 one-time authorization-consumption state machine, Phoenix v3.1 provider controller and a new authorization-enforced Ops entrypoint into one fail-closed provider execution package.

Before any provider apply, the coordinator verifies the exact decision, source commit, Core and Ops archive digests, accepted provider-authority mode, execution identity and provider-authority presence. Missing provider authority does not consume the authorization.

After durable `APPLY_STARTED`, a missing, unreadable or semantically invalid provider receipt becomes `PROVIDER_OUTCOME_RECONCILIATION_REQUIRED`. The same authorization is never automatically retried. A later run may only admit an existing receipt that passes embedded SHA-256 integrity and exact provider semantic readback, including after the original authorization has expired. Exact verified retries are idempotent and cross-execution replay is rejected.

## Provider-native proof

The repair PR #225 passed the Federation Omega Airlock, the Public Repository Leak Guard, 52 Phoenix v3-family tests including 11 authorized-executor tests, and six export regressions. It merged at `90248d6f95f28b0cafce359405665f1c78724450`. PR #226 then added the fail-fast stale-base ancestry gate at `3a715d0ac00501c045b856569c81242fdc05bca6`. The latest independent main-line resource-lifecycle repair established current final head `3d08384ccc2a727f47013a21b0c16545f985f8ab`.

Final-head Phoenix run `30949598671`, job `92128076000`, published `phoenix-freeze/verified = success` and exact immutable artifacts:

- Cutover artifact `8908533143`, digest `sha256:60cc36066a82ee4f68c0414e5f9021ad6852133e5efede4e2ead3dc7f0d15848`.
- Freeze artifact `8908532469`, digest `sha256:610ffa44405210d8960219afe47318a7df9c43931efbe40fcfc3d00fd8971e1b`.
- Core archive SHA-256 `4783a29388ee93b3f6a0e6883a3e6c16f2fdb8939f8d74693c3b7de1c9d6fc26`.
- Ops archive SHA-256 `86b59f255bbfe2407ff4d20c1c5644918cc6215987726b16dbabbffd356eb2b9`.
- Export receipt SHA-256 `5526930ccd05af6ae258d499d01609f8f6a1b287772f98111bea668146c8734a`.

## Provenance discrepancy record

The initial v25 implementation files were written directly to `main` because the connector branch parameter was supplied incorrectly. Provider-native Phoenix verification then exposed an over-strict base-export fixture contract. The defect was repaired through PR #225 and the final head passed all required Phoenix proof gates.

The release does **not** claim retroactive Airlock admission for the earlier direct writes. It records them explicitly as `DIRECT_MAIN_WRITES_DETECTED_AND_REPAIRED_NO_RETROACTIVE_AIRLOCK_ADMISSION_CLAIMED`.

## Google Drive release

Private release file: `1AIfd_i_LbF_rhhTOUC8GLEGNRoR8XRbrIQgxzVQ0dGY`.

Fresh readback and permission inspection verified owner-only access, a 4,696-byte text export and SHA-256 `9a7bc9399cd4724e0fb188a2836ed6674a08ecc53b8ba5da1ca382ccf3174317`.

## Commercial boundary

The service-enabled platform remains prioritised and self-service SaaS remains held. No Core or private Ops repository was created, no provider apply occurred, no Cloud Run operation was proven, no payment-provider operation was performed, and no demand, customer contract, enterprise assurance, partner adoption, production scale or revenue event is claimed.

The next consequential gate remains `PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED`. It requires a fresh short-lived exact owner authorization and suitable GitHub provider authority in the separate private Ops execution plane. Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
