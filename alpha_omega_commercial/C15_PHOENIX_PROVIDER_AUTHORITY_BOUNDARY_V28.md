# C15 Phoenix Provider Authority Boundary v28

## Release state

The Alpha→Omega Commercial Maturity programme advances the service-enabled platform path:

`C03 → C06 → C07 → C11 → C14 → C15`

Self-service SaaS remains held. This release reconciles the provider-authority capability merged by PR #237 and the current-main export-contract repair merged by PR #240.

## Smallest complete operational slice

The private Ops execution package now:

1. probes GitHub provider authority using GET-only endpoints;
2. distinguishes owner user-scoped authority from installation-template authority;
3. requires an all-repositories installation with Administration write, Contents write and Metadata read;
4. rejects selected-repository-only installations;
5. binds a hash-valid authority receipt to the exact authorization decision, live source SHA, post-merge cutover candidate and Core/Ops archives;
6. fails before authorization state or provider calls on missing, blocked, mismatched or altered authority evidence;
7. retains one-time authorization consumption, live-source rechecks and read-only uncertain-outcome reconciliation.

The canonical apply entrypoint is `provider_cutover_authority_bound.py`. No provider apply occurred.

## Verified implementation lineage

| Control | Evidence |
|---|---|
| Provider-authority implementation | PR #237, merge `613c1c19010c3484abf3de5c90ce29930889aae2` |
| Current-main export repair | PR #240, merge `7065290d98fa384858b8d609df4960a35ece563b` |
| Airlock | run `30960807002`, job `92164099868`, artifact `8912854487` |
| Leak Guard | run `30960806998`, success |
| Current-main Phoenix proof | run `30960914268`, job `92164426068`, success |
| Cutover artifact | `8912892480`, `sha256:45452a2fa62a202f9f60dedba2e29d26b0d2562b809fbfd10ee05e22fbd23d93` |
| Freeze artifact | `8912892183`, `sha256:ebca6e3763df2341a8e23f21a6d15a923e00e2f7040292dca5e8cb998a735030` |

Provider-native regressions passed: Airlock 12/12, stale-base 6/6, source provenance 5/5, activator 8/8, cutover v2 10/10, cutover v3 family 113/113, exports 6/6, OpenAI semantics 17/17 and Apps Script authorization 4/4.

## Current export proof

- Export policy: `1.0.9`
- Export receipt: `9087683799930e54bb8c622b34eb90a245f43fa0a92e9cec6fce4d00f4210fad`
- Core archive: `cc8e3477d44a68934aef4a14a8f0d5ad80bf7fa3057102691918a3ce2e08883e`
- Ops archive: `ef2865a4477e8fb5e5ce848940d819a13baae93a1976e748ce2583c7b16c2c83`
- Core workflows: 0
- Ops workflows: 0
- Provider apply performed: false
- Source mutation attempted: false

## Fresh provider-authority readback

The authenticated provider account is `mosianekk-lang`. Installation `149462480` exposes only `mosianekk-lang/Federation-Omega` through the connected installation. The intended Core and Ops targets are absent.

The exact current boundary is:

`PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED`

This readback does not prove target repository creation or provider apply.

## Private Google Drive release

- File ID: `1PSTw8mxxZxEJ6vNWUuNKvztQOGS4ZyKzBwa_nxSYQ_o`
- Title: `Alpha Omega Phoenix Provider Authority Boundary v28 Release`
- Export size: `7319` bytes
- Export SHA-256: `102a25cb5d19c7436790ef087288aff8ba2f51e1e151867cae32c31c32adb52c`
- Shared: false
- Owner: `mosianekk@gmail.com`
- Readback: verified

## Commercial truth boundary

No customer demand, signed contract, payment-provider operation, revenue, subscription, invoice, Cloud Run operation, enterprise assurance, partner adoption, external case study or production scale is claimed.

Verified live revenue events remain `0`. Full commercial maturity is not claimed.

## Owner authority

Financial commitments, contracts, external communications, consequential releases, execution-plane cutover and revenue recognition remain owner-reserved.

The next consequential gate requires fresh short-lived exact owner authorization plus either owner user-scoped provider authority or an all-repositories installation with the required permissions.
