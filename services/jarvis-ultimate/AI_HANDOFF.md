# AI handoff

Continue from release 1.4.0. Do not rebuild the core or weaken any action schema.

Before external work:

1. Read `BUILD_CONTRACT.json`, `FORMATION_SPEC.md` and `PROJECT_MEMORY.md`.
2. Re-run all local tests and doctrine invariants.
3. Verify current Google documentation and exact SDK/provider configuration.
4. Obtain a current single-use Formation decision for the exact mutation.

The dependency lane is source-complete only when `uv lock --check`, `uv sync --frozen`, the installed-package regression, the full local suite, and the path-scoped GitHub Actions workflow all pass for the same commit. The compatible direct set is `google-adk==2.1.0`, `google-genai==1.75.0`, and `cryptography==46.0.0`; do not reintroduce the unsatisfiable GenAI 2.x pin while ADK 2.1.0 requires GenAI `<2`.

The next authorized engineering lane after that proof is provider identity, not feature expansion: repair and read the machine identity, run a bounded Gemini read canary, then deploy a private zero-traffic Cloud Run candidate. Reject generic HTTP health. Require two stable semantic results plus exact source→build→digest→revision→traffic lineage. Capture the prior revision and test rollback before promotion.

Workspace is a separate authority lane. Use incremental OAuth, exact user identity and minimal scopes. Do not assume ChatGPT Drive/Gmail connectors, Google Cloud IAM, Apps Script sharing, API keys or service-account ownership provide Workspace user-data authority.

If any gate fails, preserve the local/offline core, quarantine only that adapter, record the learning event, and stop without a live claim.
