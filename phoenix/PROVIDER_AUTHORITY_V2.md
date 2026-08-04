# Phoenix Provider Authority v2

## Purpose

This package performs the final provider-side Phoenix cutover after the legacy
workflow registry has been quarantined and the Core and Ops archives have been
verified.

The executable controller is:

`phoenix/provider_cutover_v2.py`

Dry-run is the default. No provider mutation occurs unless `--apply` is
supplied.

## Accepted authority

The two target repositories belong to the personal account `mosianekk-lang`.
Creating them through GitHub's authenticated-user repository endpoint requires
one of these user-scoped authority models:

- a GitHub App user access token; or
- a fine-grained personal access token.

The credential must permit repository Administration write and the authenticated
user must be `mosianekk-lang`.

A GitHub App installation access token is not accepted for this cutover. It is
limited to repositories already granted to that installation and cannot perform
the required personal-account repository creation route.

The credential must remain in a trusted local environment variable named
`GH_ADMIN_TOKEN`. Do not store it in Drive, email, ChatGPT, source control,
workflow artifacts or receipts.

## Verified archive inputs

Use the current provider-verified artifacts, not an arbitrary local copy.
Always pass their expected SHA-256 values to the controller.

The v2 controller:

1. checks each archive digest;
2. rejects absolute paths, parent traversal, links and device entries;
3. confirms that neither export contains GitHub workflow files;
4. confirms that Core contains no runtime directory;
5. authenticates through `/user` and verifies the expected owner;
6. verifies administrator authority over the legacy repository;
7. creates or validates the Core and Ops repositories;
8. pushes the exact extracted baselines;
9. applies read-only workflow defaults and disables Actions at bootstrap;
10. installs active branch rulesets;
11. verifies visibility, exact main SHA, rulesets, Actions state and absence of
    workflow directories;
12. disables Actions globally in the legacy repository;
13. archives the legacy repository only when the separate archive flag is used;
14. writes a non-secret provider readback receipt.

## Sole-owner-safe ruleset

The default ruleset requires pull requests, signed commits, linear history,
resolved review threads, and blocks deletion and non-fast-forward updates.

The default approval count is zero. This prevents a personal repository with one
owner from becoming impossible to update.

Use `--require-second-reviewer` only after a real second reviewer has repository
access and can satisfy code-owner and latest-push approval requirements.

## Dry-run

```bash
python provider_cutover.py \
  --core-archive Federation-Omega-Core.tar.gz \
  --ops-archive Federation-Omega-Ops.tar.gz \
  --expected-core-sha256 <verified-core-digest> \
  --expected-ops-sha256 <verified-ops-digest> \
  --receipt phoenix-provider-cutover-v2-dry-run.json
```

A successful dry-run returns `DRY_RUN_VERIFIED`. It validates the archives but
does not test or use provider authority.

## Apply

```bash
export GH_ADMIN_TOKEN='<short-lived-user-scoped-token>'

python provider_cutover.py \
  --core-archive Federation-Omega-Core.tar.gz \
  --ops-archive Federation-Omega-Ops.tar.gz \
  --expected-core-sha256 <verified-core-digest> \
  --expected-ops-sha256 <verified-ops-digest> \
  --apply \
  --receipt phoenix-provider-cutover-v2-receipt.json

unset GH_ADMIN_TOKEN
```

Do not request legacy archival during the first provider run. Confirm the Core
and Ops readback receipt first. Archive the legacy repository only through a
separate rerun with `--archive-legacy` after all earlier checks remain green.

## Completion standard

The provider cutover is complete only when the receipt status is `VERIFIED` and
all of these are true:

- Core and Ops exist with the expected visibility;
- each main branch SHA exactly matches its exported baseline;
- both repositories have active rulesets;
- both repositories have read-only default workflow permissions;
- Actions is disabled at bootstrap in Core and Ops;
- neither repository contains `.github/workflows`;
- legacy Actions is disabled;
- no credential value is recorded;
- no legacy history is rewritten;
- any requested legacy archival is confirmed through provider readback.
