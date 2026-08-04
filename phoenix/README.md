# Federation Omega Phoenix Cutover

This package migrates the quarantined legacy repository into two clean repositories:

- `Federation-Omega-Core` for canonical source, runnable Core tests, schemas and documentation.
- `Federation-Omega-Ops` for private execution, initially with no active workflow.

## Generated artifacts

A successful Phoenix freeze run creates a source-clean Core archive, a private Ops archive, an export receipt and an execution-freeze receipt. Both receipts contain hashes and source commit identifiers.

Core excludes GitHub Actions workflows, runtime state, generated receipts, credential-bearing paths, private-key formats and migration-control code. Tests whose names start with `tests/test_phoenix_` are migration-control tests and are also excluded because their required controller is intentionally placed only in Ops. The Phoenix source workflow runs those tests before export; the exported Core test set must remain independently runnable without Phoenix migration files.

Ops contains only its governance template and the provider cutover controller.

## Provider cutover

Use the user-scoped provider controller documented in `PROVIDER_AUTHORITY_V2.md`. Run it without `--apply` first. Dry-run mode verifies the exact Core and Ops archive digests, safely extracts both archives and writes a plan without changing GitHub.

Provider execution requires a short-lived user-scoped administration credential supplied through the `GH_ADMIN_TOKEN` environment variable. The controller does not print or persist that value. Installation-only credentials are rejected.

Archiving the legacy repository is a separate explicit gate using `--archive-legacy` after the initial Core and Ops provider readback is verified.

## Fail-closed behavior

- Existing non-empty targets are not overwritten by default.
- Legacy Actions are disabled only after Core and Ops pass provider readback.
- Legacy archiving occurs only after all earlier gates pass.
- No legacy history is rewritten.
- No newly created repository is automatically deleted after a later failure.
- The initial Ops repository contains no schedule, deployment workflow or provider credential.
- Core contains no Phoenix migration controller or migration-only test that depends on it.

The connected repository surface cannot create repositories or change repository rulesets/settings. Final completion is therefore established only by a `VERIFIED` receipt from the exported `provider_cutover.py` under user-scoped provider administration authority.
