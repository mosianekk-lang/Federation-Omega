# Federation Omega Phoenix Cutover

This package migrates the quarantined legacy repository into two clean repositories:

- `Federation-Omega-Core` for canonical source, tests, schemas and documentation.
- `Federation-Omega-Ops` for private execution, initially with no active workflow.

## Generated artifacts

A successful Phoenix freeze run creates a source-clean Core archive, a private Ops archive, an export receipt and an execution-freeze receipt. Both receipts contain hashes and source commit identifiers.

Core excludes GitHub Actions workflows, runtime state, generated receipts, credential-bearing paths, private-key formats and migration-control code. Ops contains only its governance template and the provider cutover controller.

## Provider cutover

Run the controller without `--apply` first. Dry-run mode validates the two extracted directories and writes a plan without changing GitHub.

Provider execution uses an administration credential supplied through the `GH_ADMIN_TOKEN` environment variable. The controller does not print or persist that value.

Example dry run:

```bash
python Federation-Omega-Ops/provider_cutover.py \
  --core-dir Federation-Omega-Core \
  --ops-dir Federation-Omega-Ops
```

Example provider execution:

```bash
python Federation-Omega-Ops/provider_cutover.py \
  --core-dir Federation-Omega-Core \
  --ops-dir Federation-Omega-Ops \
  --apply
```

Archiving the legacy repository is a separate explicit gate using `--archive-legacy`.

## Fail-closed behavior

- Existing non-empty targets are not overwritten by default.
- Legacy Actions are disabled only after Core and Ops pass provider readback.
- Legacy archiving occurs only after all earlier gates pass.
- No legacy history is rewritten.
- No newly created repository is automatically deleted after a later failure.
- The initial Ops repository contains no schedule, deployment workflow or provider credential.

The connected repository surface cannot create repositories or change repository rulesets/settings. Final completion is therefore established only by a `VERIFIED` receipt from `provider_cutover.py` under provider administration authority.
