# Federation Omega Provider Airlock Activation

## Purpose

`phoenix/provider_airlock_activate.py` activates and verifies the narrow provider controls required to prevent direct updates to `main`.

It is intentionally separate from the broader Core/Ops repository cutover. The activator changes only:

1. the repository ruleset named `Federation Omega Main Airlock`;
2. the repository default GitHub Actions workflow permissions.

It does not create repositories, archive the legacy repository, modify source files, execute commercial actions, send communications, or persist credential values.

## Current provider truth

Read-only GitHub provider readback on 28 August 2026 established that provider prevention is **not active**:

- `main` is reported as unprotected;
- required status-check enforcement is `off`;
- the repository ruleset collection is empty.

The source activator, ruleset payload and local defense-in-depth controls therefore remain preparation, not provider enforcement. Do not infer an active ruleset from the existence of these files or from green CI.

## Authority boundary

The connected ChatGPT GitHub installation reports repository admin standing for `mosianekk-lang/Federation-Omega`, but the connector exposes no ruleset, branch-protection, repository-creation or Actions-default mutation action.

Provider apply therefore requires a short-lived credential supplied only through the trusted local environment variable `GH_ADMIN_TOKEN` and separate explicit provider-write authority.

Supported credential modes:

- GitHub App user access token;
- GitHub App installation access token that includes this repository and has Administration write plus Contents write for the temporary canary;
- fine-grained personal access token with equivalent permissions.

Do not place the credential in ChatGPT, Drive, email, repository files, workflow logs or receipts.

## Controls applied

The canonical payload is:

`governance/federation_omega_main_airlock.ruleset.json`

The activator validates that it:

- targets the default branch;
- has active enforcement;
- has zero bypass actors;
- blocks deletion and non-fast-forward updates;
- requires linear history and signed commits;
- requires pull requests and resolved review threads;
- remains sole-owner safe with zero mandatory approvals;
- requires the strict three-check release court:
  - `admission` — Federation Omega Airlock;
  - `contract` — Bubbles Command Bus;
  - `scan` — Public Repository Leak Guard.

Conditional Bubbles jobs such as `command` and `provider-surface-readback` are intentionally not mandatory because they are skipped for ordinary pull requests.

It also sets:

- `default_workflow_permissions = read`;
- `can_approve_pull_request_reviews = false`.

## Linear-history transition

The dormant canonical ruleset requires linear history and permits only squash/rebase merges. Once provider activation is genuinely verified, the release process must stop relying on two-parent merge commits on `main` and instead preserve exact admitted PR-head identity in the provider/source-provenance receipt before the GitHub-signed linear main commit is accepted as final readback.

Until that provider transition occurs, signed merge commits may exist on the currently unprotected `main`; they are lineage evidence, not proof that provider branch prevention was active.

## Safe negative canary

The direct-update rejection test never targets `main`.

The activator:

1. records the original `main` SHA;
2. creates a uniquely named temporary branch at that SHA;
3. creates a temporary ruleset containing the same controls but targeting only that branch;
4. verifies the expected active rule types through GitHub readback;
5. creates an orphanable no-op Git commit using the same tree;
6. attempts a non-force update of the temporary branch;
7. requires GitHub to reject the update with HTTP 403, 409 or 422;
8. deletes the temporary ruleset and temporary branch;
9. applies the canonical ruleset to `main`;
10. verifies that `main` never changed.

If the temporary branch update succeeds, provider activation fails closed and the canonical ruleset is not applied.

## Dry run

```bash
python phoenix/provider_airlock_activate.py \
  --ruleset governance/federation_omega_main_airlock.ruleset.json \
  --receipt provider-airlock-dry-run.json
```

Expected status:

`DRY_RUN_VERIFIED`

The dry-run receipt also records the required status contexts `admission`, `contract`, and `scan` and performs no provider mutation.

## Provider apply

Run only from a trusted local shell with explicit provider-write authority:

```bash
export GH_ADMIN_TOKEN='<short-lived-token>'
python phoenix/provider_airlock_activate.py \
  --ruleset governance/federation_omega_main_airlock.ruleset.json \
  --apply \
  --receipt provider-airlock-activation-receipt.json
unset GH_ADMIN_TOKEN
```

Completion requires receipt status:

`VERIFIED`

## Required readback

The provider receipt must prove:

- authenticated authority can administer the target repository;
- the temporary direct-update canary was rejected;
- the canonical ruleset was created or updated;
- the returned ruleset exactly matches the canonical payload;
- the exact required status contexts are `admission`, `contract`, and `scan`;
- active `main` rules include every required rule type;
- workflow defaults are read-only;
- Actions cannot approve pull-request reviews;
- the `main` SHA remained unchanged;
- no credential value was recorded.

## Truth boundary

The activator is implemented and regression tested, but provider prevention is currently absent by live read-only GitHub readback. It must not be called active until GitHub returns a hash-bound `VERIFIED` provider receipt proving the exact three-context ruleset, workflow permissions, negative canary and unchanged `main` SHA.
