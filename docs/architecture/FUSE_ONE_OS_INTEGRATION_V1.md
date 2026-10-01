# FUSE-ONE OS integration

FUSE-ONE is the unified experience over the existing FUSE Sovereign Plane and
SOL 6.2 runtime. This extension reuses their authority, mission state, provider
adapters, recovery and proof controls. It does not create another operating
system kernel, controller, scheduler or memory root.

## Experience and API

The existing web client provides the owner interface. Chat uses `POST /v1/chat`;
missions use the existing create, status and wake endpoints. Provider selection
and consequential effects stay behind the established server-side controls.
Browser assets contain no provider credentials.

Mission creation now acquires SQLite's write lock before checking ownership.
Mission registration, initial state, owner binding, derived plan/policy, intent
and events commit in one transaction. Identical same-owner retries preserve state
and events; another owner, orphaned binding or conflicting definition receives
HTTP 409. Busy storage returns a recoverable HTTP 503. Real multiprocess races,
injected failures and termination-before-commit tests verify the shared-SQLite
transaction boundary. This does not certify cross-database or multi-region
isolation, nor the broader multi-tenant production requirements.

`GET /v1/os/catalog` is an authenticated, non-cached projection of the existing
unified configuration and ecosystem service definitions. It returns:

| Field | Meaning |
| --- | --- |
| `schema` | `FUSE_UNIFIED_SERVICE_CATALOG_V1` |
| `services[].service_id` | Canonical service identifier from the existing configuration |
| `source_state` | `DEFINED`, `LEGACY_ALIAS`, or `UNRESOLVED_DEFINITION` |
| `source_supported` | A matching composition definition exists; not execution proof |
| `alias_of` | Existing identifier used by an explicit compatibility mapping |
| `required_capabilities` | Existing definition's requirements, or null when unresolved |
| `runtime_readiness` | `NOT_ASSESSED`; this endpoint never invokes a provider |
| `callable_now` | null until a separate current runtime assessment exists |

Use the same verified owner session as `/v1/capabilities`, supplied in
`X-Fuse-Authorization: Bearer <session>` or `Authorization: Bearer <session>`.
Missing, invalid or expired credentials are rejected before catalog access.
Invalid source contracts return HTTP 503 with `FUSE_OS_CATALOG_INVALID`.
This API does not accept catalog file paths, credentials, arbitrary URLs or code.

For Python integrations, `build_unified_kernel(fabric)` in
`federation.fuse_unified_service_catalog_v1` supplies canonical aliases to the
existing `FuseEcosystemKernel`. It retains legacy service callers and preserves
the existing currentness, maturity, authority, privacy and effect gates.
`resolve_unified_service(service_id)` distinguishes an unknown identifier from
a known service whose composition definition is still missing.

## Provider roles

Provider adapters remain replaceable, task-scoped resources. Existing Google
Workspace and Apps Script paths handle data and bounded automation; Gemini and
OpenRouter paths handle eligible inference; Canva handles authorized creative
work; local/cloud models and Microsoft paths retain their own authentication,
capacity, privacy and proof requirements. A provider appearing in a source
registry does not establish that a deployed runtime can invoke it.

Historical chat, Gmail and Drive material supplies evidence and reusable source.
It cannot provide current execution authority or prove unseen chats processed.
Commercial comparisons require measured task outcomes, not counts of algorithms,
registered services or logical agents.

## Run and verify

Install the pinned service dependencies in an isolated Python environment, plus
pytest for tests. Node.js supplies the JavaScript syntax check. From the
repository root:

```sh
python -m pip install -r services/sol62_client_runtime/requirements.txt
python -m pip install pytest==8.3.5
python scripts/verify_fuse_one_os.py
python -m services.sol62_client_runtime
```

The runtime defaults to loopback port 8762. A bare source checkout has no
provider/session authority; the established deployment supplies those bindings.
Keep production secrets in the existing authorized runtime, never the UI or
source files. The verification runner isolates state and removes provider
configuration relevant to the tested gateway from its child process environment.
It does not call external providers or install schedulers.

Run the reproducible browser checks with Playwright and Chromium available:

```sh
FUSE_BROWSER_TEST_PYTHON=/path/to/venv/bin/python node scripts/fuse_one_os_browser_test.mjs
```

The browser runner launches an isolated local runtime with an ephemeral test
session, creates one local test mission, and checks the real API and responsive
interface. It strips inherited provider configuration before runtime import.
Reports and screenshots default to an operating-system temporary directory;
`FUSE_BROWSER_TEST_OUTPUT` may select another directory outside the source tree.
`PLAYWRIGHT_MODULE_PATH` and `CHROMIUM_EXECUTABLE_PATH` select preinstalled tools.
The fixture does not add a session-issuing endpoint to the production application.

## Admission, deployment and recovery

Preserve the existing FDOF/SICF admission path. Reconcile latest source and all
active leases before applying a candidate. A legacy active repository lease
cannot be overridden by a disjoint local file list. Apply only surviving changes
under a lawful fence, then require exact-head Airlock, source provenance, public
leak guard and independent review. Use the existing SOL62 canary workflow and
immutable container build; no additional deployment controller is introduced.

The admission workflow reads the current legacy repository lease before applying
scoped-registry checks. An expired scoped lease still protects its own write set,
while unrelated scopes can proceed; explicit recovery and a newer fence remain
mandatory before reuse. A live legacy repository-wide lease remains exclusive.
Malformed hosted pull-request events fail closed. Merge-group coordination is
held until its event adapter supplies equivalent claim and current-state proof.

Exact source-to-test mappings include the actual API, atomic-ownership and
browser suites. The admission bridge verifies that pytest collected these tests;
a successful zero-test discovery cannot satisfy those courts. Unknown production
paths retain the conservative full-suite fallback. ProofOS uses a shared deadline
for courts, repeatability and diagnostics, records progress before each court,
terminates owned child-process groups, and blocks incomplete coverage. Browser
setup has a separate deadline. These controls reserve report headroom during
ordinary operation; process startup, detached sessions and platform failures are
not a universal wall-clock guarantee. No repository-local control replaces a
provider-enforced required-check ruleset.

At the candidate revision, verify authentication denial, mission isolation,
catalog schema, chat failure handling, interrupted/resumed work, no duplicate
effects, runtime health, and provider-native semantic outputs. Test rollback to
the prior admitted immutable image before production promotion. This extension
does not migrate the mission database; revert the candidate code/image while
preserving existing mission state and effect journals through the established
approved recovery path.

## Release claims and commercial acceptance

Source tests, browser tests, canary deployment, provider invocation, independent
completion proof and customer value are separate acceptance stages. The UI and
catalog cannot certify commercial readiness. Required remaining product gates
include tenant/matter isolation, credential revocation, provenance and software
inventory, reproducible installation/update, recovery/load/security testing,
privacy-aware routing, support ownership and measured unit economics.

Use a frozen representative task set to compare accepted outcomes, time,
operator interventions, cost and recovery against named baselines. Select a
specific customer workflow for a controlled pilot. Do not promise superiority
over companies or products without matched evidence.

Official review baseline:

- Microsoft agent testing: https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/sec-gov-phase4
- Google managed agent operation: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale
- OpenRouter data-retention routing: https://openrouter.ai/docs/guides/features/zdr

These references inform release criteria; they do not certify this software or
establish that any provider binding is deployed.
