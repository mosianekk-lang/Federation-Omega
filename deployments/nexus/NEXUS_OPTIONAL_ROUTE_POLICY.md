# NEXUS-CODEX Optional Route Policy

Status: `CLOSED_OPTIONAL_ROUTE`

Effective checkpoint: 2026-08-04

## Current determination

NEXUS-CODEX v3.1.1 is preserved as a hash-locked, workload-specific deployment capability. It is not a required Federation Omega maturity dependency and is not deployed or proven operational.

The latest provider-native authentication receipt is `deployments/nexus/NEXUS_OPERATOR_AUTH_CANARY_RECEIPT.json`, recorded on 2026-08-03. It classifies the route as `BLOCKED_NO_TRUSTED_SECRET_ROUTE` and records the configured WIF provider as `NOT_FOUND`. No authenticated operator status, Cloud Run baseline read, deployment, build, target service readback, endpoint health proof, or rollback reference was produced.

The canonical release remains:

- Drive artifact: `1_r1qlRHeEcF7Xl-BSJpfWUWIRYs4C_Pm`
- Name: `nexus-codex-runtime-v3.1.1.zip`
- SHA-256: `fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518`
- Target project: `sov-hybrid-suite`
- Target region: `africa-south1`
- Target service: `nexus-codex-runtime`

## Active-control decision

The two push-trigger-capable diagnostic workflows are removed from the active workflow directory in this branch:

- `.github/workflows/nexus-operator-auth-canary.yml`
- `.github/workflows/nexus-secret-access-diagnostic.yml`

Their complete history, commits, receipts and source remain recoverable through Git history. This change prevents unrelated future edits to the diagnostic or bootstrap files from launching an obsolete authentication probe or writing another diagnostic receipt to `main`.

The following bounded manual routes remain preserved for workload-specific requalification:

- `.github/workflows/nexus-direct-preflight.yml`
- `.github/workflows/nexus-direct-runtime-target.yml`
- `.github/workflows/nexus-operator-recovery-now.yml`

These routes must not be dispatched merely to test an unchanged failed provider configuration.

## Reactivation gate

A NEXUS deployment or authentication route may be reactivated only when all of the following are true:

1. A concrete approved workload selects `nexus-codex-runtime` as its required target.
2. The exact project number, WIF pool, provider, attribute mapping, attribute condition and service-account bindings are freshly read back from Google Cloud.
3. A trusted secret-free identity or already-authorised secret route is proven without exposing credential values.
4. Authenticated operator `STATUS` and source-service baseline read both succeed.
5. The canonical artifact name, size and SHA-256 are verified before and after staging.
6. Deployment begins at zero traffic and returns a provider-native build ID.
7. The created revision, image digest, runtime service account and endpoint health are independently read back.
8. Semantic canary proof succeeds before traffic promotion.
9. The exact prior traffic map and executable rollback route are recorded.
10. Required receipts are persisted without secret values and independently read back.

## Security-remediation boundary

Historical evidence records a plaintext OpenAI credential exposure. Replacement, dependent-runtime migration, health verification and revocation of the exposed credential remain unproven. No credential value may be copied into a repository, receipt, issue, pull request, log or chat. Remediation must follow this order:

1. create or identify a secure replacement destination;
2. bind each confirmed dependent runtime;
3. verify runtime health and semantic readback;
4. revoke the exposed credential;
5. sanitize retained diagnostic material without destroying audit history;
6. issue a redacted remediation receipt.

## Closure state

- Deployment: `NOT_PROVEN`
- Runtime health: `NOT_PROVEN`
- Rollback: `NOT_PROVEN`
- Automatic diagnostic probes: `QUARANTINED_IN_BRANCH`
- Canonical artifacts and history: `PRESERVED`
- Owner action currently required: `FALSE`
- Next action: wait for an actual workload and materially changed provider authority before requalification.
