# Federation Omega Phoenix Provider Authority v3

## Status

`DUAL_AUTHORITY_CUTOVER_ENGINE_BUILT_PENDING_PROVIDER_NATIVE_PROMOTION`

Phoenix v3 removes the false assumption that a user-scoped token is the only possible repository-creation route. It supports two governed authority models and automatically prefers the least ambiguous one available.

## Authority model A — installation-template bootstrap

A GitHub App installation access token may create the two Phoenix repositories through GitHub's template-generation endpoint when all of the following are true:

- the app installation belongs to the destination account;
- the app can access `mosianekk-lang/Federation-Omega`;
- the app has repository Administration write;
- the app has Contents read;
- the installation is configured for all repositories on the destination account, as required by GitHub for repository creation through installation authority;
- the existing repository can be temporarily marked as a template;
- exact readback confirms the template flag is restored after generation.

Endpoint:

`POST /repos/mosianekk-lang/Federation-Omega/generate`

The controller:

1. inventories existing targets;
2. records the source repository's original `is_template` state;
3. sets `is_template: true` only when a target is missing and the source is not already a template;
4. generates only the missing repositories;
5. waits for provider readback;
6. restores the original template state in a `finally` block;
7. verifies the restoration before continuing;
8. replaces the generated template contents with the hash-verified Core/Ops exports;
9. applies rulesets and Actions restrictions;
10. verifies exact provider state.

The template route does not rewrite or delete legacy history.

## Authority model B — user-scoped creation

The fallback route accepts either:

- a GitHub App user access token; or
- a fine-grained personal access token.

It must:

- authenticate as `mosianekk-lang`;
- provide Administration write;
- provide repository contents authority needed for the baseline push;
- create repositories through `POST /user/repos`;
- exist only in the trusted local environment variable `GH_ADMIN_TOKEN`.

## Automatic authority selection

`--authority-mode auto` performs:

1. user-scoped `/user` preflight;
2. if that fails, installation `/installation/repositories` preflight;
3. fail closed when neither route satisfies its authority contract.

Explicit modes are also supported:

- `--authority-mode user`
- `--authority-mode installation`

## Credential handling

Credential values must never be placed in:

- ChatGPT;
- Google Drive;
- Gmail;
- repository source;
- workflow artifacts;
- logs;
- receipts.

The controller never prints or writes the token value.

## Archive controls

Before any provider mutation, the controller:

- recalculates both archive SHA-256 values;
- rejects mismatches;
- rejects absolute paths;
- rejects `..` path traversal;
- rejects symbolic links;
- rejects hard links;
- rejects device entries;
- confirms both exports contain files;
- confirms neither export contains `.github/workflows`;
- confirms Core contains no `runtime/` state.

## Sole-owner safety

The default branch ruleset uses zero mandatory approvals because the GitHub account currently has one confirmed owner and no independently verified second reviewer.

The default still requires:

- pull requests;
- signed commits;
- linear history;
- resolved review threads;
- no branch deletion;
- no non-fast-forward updates.

`--require-second-reviewer` may be enabled only after a real second reviewer has access. It activates:

- one approving review;
- code-owner review;
- stale-review dismissal;
- approval of the latest push.

## Target-state verification

Completion requires exact readback proving:

- `Federation-Omega-Core` exists with the selected visibility;
- `Federation-Omega-Ops` exists as private;
- each `main` SHA equals the pushed export commit;
- `.github/workflows` is absent from both targets;
- Actions is disabled at bootstrap in both targets;
- default workflow permissions are read-only;
- Actions cannot approve pull-request reviews;
- both branch rulesets are active;
- the legacy repository's Actions setting is disabled;
- the legacy repository is not left in template mode;
- no legacy history was rewritten;
- no credential value was recorded.

## Archive gate

The first successful provider cutover must run without `--archive-legacy`.

Legacy archival is a separate explicit operation after every prior readback remains green. The controller never deletes repositories automatically.

## Dry-run example

```bash
python provider_cutover.py \
  --core-archive Federation-Omega-Core.tar.gz \
  --ops-archive Federation-Omega-Ops.tar.gz \
  --expected-core-sha256 <verified-core-sha256> \
  --expected-ops-sha256 <verified-ops-sha256> \
  --authority-mode auto \
  --receipt phoenix-provider-cutover-v3-dry-run.json
```

Expected status:

`DRY_RUN_VERIFIED`

## Apply example

```bash
export GH_ADMIN_TOKEN='<short-lived-authorised-token>'
python provider_cutover.py \
  --core-archive Federation-Omega-Core.tar.gz \
  --ops-archive Federation-Omega-Ops.tar.gz \
  --expected-core-sha256 <verified-core-sha256> \
  --expected-ops-sha256 <verified-ops-sha256> \
  --authority-mode auto \
  --apply \
  --receipt phoenix-provider-cutover-v3-receipt.json
unset GH_ADMIN_TOKEN
```

Do not add `--archive-legacy` to the first apply run.

## Truth boundary

The v3 engine and regression tests do not prove the installed GitHub App currently has the required repository-generation permissions or all-repositories installation scope. That fact is proven only when an apply run returns exact provider readback with status `VERIFIED`.

Until then, the valid state is:

`V3_ENGINE_BUILT / LOCAL_TESTS_PASS / PROVIDER_NATIVE_PROMOTION_PENDING / TARGET_REPOSITORIES_NOT_YET_PROVEN`
