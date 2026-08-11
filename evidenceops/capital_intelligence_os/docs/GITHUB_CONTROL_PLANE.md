# Federation Omega GitHub Control Plane v1

## Mission

Apply the Formation Innovation Engine and Alpha→Omega operating contract to the GitHub surface so that repository automation is governed, testable, reversible and unable to recreate the direct-write race that caused repeated Actions failures and notification storms.

## Formation sequence

`INTAKE → DISCOVERY → DECOMPOSITION → ARCHITECTURE → BUILD → TEST → DEPLOY → VERIFY → OPERATE → MAINTAIN`

This implementation covers the repository-control layer. It does not claim that unresolved external provider authority, credential rotation or production deployment has been completed.

## Permanent invariants

1. GitHub source branches are not runtime databases.
2. CI, observers, canaries, diagnostics, preflights and watches are read-only.
3. Automated workflows do not commit or push generated receipts to `main`.
4. Proof is stored as an immutable Actions artifact or in a separately governed append-only provider store.
5. `workflow_run` consumers never receive repository write authority.
6. `pull_request_target` workflows never receive OIDC token authority.
7. Scheduled and workflow-run consumers are serialized with explicit concurrency controls.
8. Checkout credentials are not persisted in changed workflows.
9. Authority-bearing changes require CODEOWNERS review.
10. Provider maturity is promoted only after deployment receipt, execution log, exact readback, health, persistence and rollback proof.

## Ratchet model

The repository contains legacy workflows that predate this control plane. A full manual scan records those findings without falsely claiming they are fixed. Every new or changed workflow is enforced immediately against the target policy. This prevents new violations while the legacy inventory is reduced to zero in controlled tranches.

## Current deployment tranche

The initial deployment:

- converts the IPEP CI receipt and observer to immutable artifacts;
- converts the PST shard fanout observer to an immutable artifact;
- repairs FEVX overlay reconstruction by selecting only canonical two-digit parts;
- removes FEVX bootstrap repository mutation;
- installs policy-as-code and regression tests;
- installs a mandatory changed-workflow control-plane gate;
- adds CODEOWNERS and root secret/runtime exclusions.

## Evidence and truth boundary

A passing control-plane workflow proves that the changed workflows satisfy the policy encoded in `governance/github_control_plane_policy.json`. It does not prove that every historical workflow has been remediated. Full-repository scans remain inventory evidence until `strict_full_repository_scan` is deliberately promoted to `true` after the legacy finding count reaches zero.

## Rollback

The change is isolated on a dedicated branch and can be reverted as one pull request. No external provider, credential, IAM, billing, traffic or production resource is mutated by this deployment.
