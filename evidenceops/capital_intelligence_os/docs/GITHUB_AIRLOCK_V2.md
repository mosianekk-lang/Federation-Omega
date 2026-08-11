# Federation Omega GitHub Airlock v2

## Why v1 was not enough

A repository-local workflow can detect a policy violation after a direct push, but it cannot reject that push before the commit reaches `main`. After Control Plane v1 merged, a later direct commit changed the RESOLVE workflow from `contents: read` to `contents: write` and restored bot receipt commits to `main`.

Airlock v2 therefore separates two controls:

1. **Platform admission** — a GitHub repository ruleset rejects direct updates to `main` and requires the `admission` check before merge.
2. **Repository validation** — the Airlock workflow validates workflow authority, triggers, immutable action pins, proof destinations and change budgets.

Both controls are required. Repository validation alone is not described as permanent prevention.

## Target architecture

```text
Feature branch
    |
    v
Pull request / merge queue
    |
    v
GitHub platform ruleset
    |- pull request required
    |- signed commits
    |- code-owner review
    |- latest-push approval
    |- admission status required
    |- linear history
    |- force-push and deletion blocked
    |
    v
Federation Omega Airlock
    |- workflow allowlist
    |- read-only token authority
    |- immutable action SHAs
    |- approved event contracts
    |- no git commits or pushes
    |- no runtime receipts in source
    |- workflow change budget
    |
    v
Source-only main branch
    |
    +--> immutable Actions artifacts
    +--> external append-only proof store
```

## Four-plane operating model

### 1. Source plane

`mosianekk-lang/Federation-Omega` stores source, tests, schemas and architecture. It is not a runtime database, scheduler ledger or receipt store.

### 2. Admission plane

The importable ruleset is stored at:

`governance/federation_omega_main_airlock.ruleset.json`

The required check is the Airlock job named `admission`.

### 3. Execution plane

Long-running, scheduled and cloud-authorised automation should move to a separate private operations repository. The public source repository should retain only bounded validation and manual deployment gateways.

### 4. Evidence plane

Workflow receipts are uploaded as immutable GitHub Actions artifacts or written to an approved append-only external store. They are not committed to `main`.

## Default-deny workflow policy

Only workflows named in `governance/github_airlock_policy.json` may be added or changed. Unlisted legacy workflows are frozen: deletion is allowed, modification is rejected until the workflow is converted into an approved gateway or retired.

The policy also rejects:

- `contents: write`;
- direct Git mutations;
- mutable action tags;
- persisted checkout credentials;
- unapproved OIDC;
- unapproved workflow triggers;
- runtime proof committed under receipt or state directories;
- more than three workflow-file changes in one pull request.

## Platform activation

`ops/apply_github_airlock.py` idempotently creates or updates the repository ruleset and changes the repository's default `GITHUB_TOKEN` permission to read-only. It requires a fine-grained token with repository Administration write permission in `GH_ADMIN_TOKEN`.

The token is not stored, printed or copied into any receipt. Successful activation produces a non-secret readback receipt.

## Truth boundary

Repository files and a passing Airlock workflow prove that the desired control package is buildable and testable. They do **not** prove that GitHub's platform ruleset is active. Platform enforcement is verified only when the ruleset and Actions-permission endpoints read back the expected values.

## Migration path

1. Activate and verify the main-branch ruleset.
2. Set default workflow permissions to read-only.
3. Freeze all unlisted workflows.
4. Convert useful legacy workflows into central task modules.
5. Move schedules and cloud execution to the private operations plane.
6. Delete obsolete workflow files.
7. Remove committed runtime receipts from source history where appropriate.
8. Promote whole-repository strict mode only when the legacy workflow count reaches zero.
