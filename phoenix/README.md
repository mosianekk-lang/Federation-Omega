# Federation Omega Phoenix Cutover

This package migrates the quarantined legacy repository into two clean repositories:

- `Federation-Omega-Core` for canonical source, runnable Core tests, schemas and documentation.
- `Federation-Omega-Ops` for private execution, initially with no active workflow.

## Generated artifacts

A successful Phoenix freeze run creates a source-clean Core archive, a private Ops archive, an export receipt and an execution-freeze receipt. Both receipts contain hashes and source commit identifiers.

Core excludes GitHub Actions workflows at every directory depth, runtime state, generated receipts, credential-bearing paths, private-key formats and migration-control code. Tests that depend on intentionally excluded source-repository controls are classified through `core.excluded_test_globs` in `phoenix/export_policy.json`. This includes the Phoenix cutover family, provider Airlock activation, repository agent-governance, emergency-freeze runtime and WIF workflow-control tests. Their controllers, active workflows or repository-only instructions do not belong in Core, so the corresponding tests do not belong there either.

The source Airlock runs these controls before export. It also builds a Core archive from the exact repository head, extracts it in isolation and executes every retained `test*.py` module. Promotion fails unless that real exported suite completes successfully. The exporter separately computes the excluded-control-test count from the actual included file set, fails closed if the count is non-zero, and records the verified zero in `PHOENIX_CORE_MANIFEST.json`.

Ops contains only its governance template and the current provider cutover controller.

Export generation is side-effect free. `build_exports.py`, `build_exports_v2.py` and `build_exports_v3.py` may read source files and write the requested local artifacts, but they must not enable, disable or dispatch workflows, call provider mutation endpoints, or access provider credentials. Metadata added by a versioned builder is included in the final receipt hash.

## Provider cutover

Use the v3.1 dual-authority exact-lease controller documented in `PROVIDER_AUTHORITY_V3.md`. Run it without `--apply` first. Dry-run mode verifies the exact Core and Ops archive digests, safely extracts both archives and writes a plan without changing GitHub.

Apply mode requires fresh provider authority supplied only through the trusted `GH_ADMIN_TOKEN` environment variable. The v3.1 controller supports a governed installation-template route and a user-scoped route, but neither route is considered operational until exact provider readback returns `VERIFIED`. The controller does not print or persist the credential value.

Archiving the legacy repository is a separate explicit gate using `--archive-legacy` after the initial Core and Ops provider readback is verified.

## Fail-closed behavior

- Existing non-empty targets are not overwritten by default.
- Legacy Actions are disabled only after Core and Ops pass provider readback.
- Legacy archiving occurs only after all earlier gates pass.
- No legacy history is rewritten.
- No newly created repository is automatically deleted after a later failure.
- The initial Ops repository contains no schedule, deployment workflow or provider credential.
- Core contains no GitHub Actions workflow, Phoenix migration controller, provider Airlock activator or source-repository-only test that depends on excluded controls.
- The complete retained Core test suite is executed from the generated archive before admission.
- Export generation does not dispatch unrelated work or mutate a provider surface.
- A receipt is not valid unless its SHA-256 covers the complete final payload.

The connected repository surface cannot complete the owner-reserved provider cutover by itself. Final completion is established only by a `VERIFIED` receipt from the exported `provider_cutover.py` under fresh, suitable provider administration authority.
