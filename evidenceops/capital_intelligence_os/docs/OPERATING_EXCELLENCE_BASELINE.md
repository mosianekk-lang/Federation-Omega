# Federation Omega Operating Excellence Baseline

**Baseline ID:** `FO-OEB-20260729-001`  
**Effective date:** 2026-07-29  
**Scope:** Superior Logic Runtime, ECASP, live-thread services, OpenAI-backed workflows, GitHub CI/CD, Google Cloud Run, Firestore, connected-tool operations, evidence processing and completion claims.

## 1. Purpose

This baseline converts current authoritative engineering guidance and verified repository findings into mandatory operating gates. It is not a claim that every control is already implemented. It distinguishes:

- **REFERENCE ACQUIRED** — an authoritative source has been read and registered;
- **CONTROL SPECIFIED** — a testable rule has been defined;
- **CONTROL IMPLEMENTED** — code or configuration exists;
- **CONTROL TESTED** — the real path has passed a relevant test;
- **CONTROL DEPLOYED** — a specific immutable revision is running;
- **CONTROL READ BACK** — the target system was independently queried;
- **CONTROL PROVEN** — the implementation, test, deployment and readback chain is complete.

No document, prompt, ledger row, test fixture, branch, commit, pull request or CI result alone proves a live production capability.

## 2. Authoritative resource registry

### 2.1 OpenAI engineering and agent guidance

1. Agents SDK guide  
   https://developers.openai.com/api/docs/guides/agents
2. Agents SDK Python documentation  
   https://openai.github.io/openai-agents-python/
3. Agent definitions  
   https://openai.github.io/openai-agents-python/agents/
4. Running agents  
   https://openai.github.io/openai-agents-python/running_agents/
5. Guardrails  
   https://openai.github.io/openai-agents-python/guardrails/
6. Handoffs  
   https://openai.github.io/openai-agents-python/handoffs/
7. Tracing  
   https://openai.github.io/openai-agents-python/tracing/
8. Agent evaluation  
   https://developers.openai.com/api/docs/guides/agent-evals
9. Function calling  
   https://developers.openai.com/api/docs/guides/function-calling
10. Structured outputs  
    https://developers.openai.com/api/docs/guides/structured-outputs
11. Production best practices  
    https://developers.openai.com/api/docs/guides/production-best-practices
12. Safety best practices  
    https://developers.openai.com/api/docs/guides/safety-best-practices
13. Error codes  
    https://developers.openai.com/api/docs/guides/error-codes
14. Rate limits  
    https://developers.openai.com/api/docs/guides/rate-limits

### 2.2 Secure software and API engineering

1. NIST SP 800-218 — Secure Software Development Framework 1.1, final  
   https://csrc.nist.gov/pubs/sp/800/218/final
2. NIST SP 800-218A — Generative AI SSDF Community Profile, final  
   https://csrc.nist.gov/pubs/sp/800/218/a/final
3. NIST SP 800-218 Rev. 1 — SSDF 1.2, initial public draft  
   https://csrc.nist.gov/pubs/sp/800/218/r1/ipd
4. OWASP API Security Top 10 — 2023 edition  
   https://owasp.org/API-Security/editions/2023/en/0x11-t10/
5. GitHub Actions secure-use reference  
   https://docs.github.com/en/actions/reference/security/secure-use
6. SLSA supply-chain framework  
   https://slsa.dev/

### 2.3 Platform and runtime guidance

1. Cloud Run service identity  
   https://cloud.google.com/run/docs/securing/service-identity
2. Cloud Run authentication  
   https://cloud.google.com/run/docs/authenticating/overview
3. Firestore transactions and batched writes  
   https://cloud.google.com/firestore/docs/manage-data/transactions
4. FastAPI security  
   https://fastapi.tiangolo.com/tutorial/security/
5. Python `sqlite3` transaction control  
   https://docs.python.org/3/library/sqlite3.html#transaction-control
6. Python packaging with `pyproject.toml`  
   https://packaging.python.org/en/latest/guides/writing-pyproject-toml/

## 3. Source hierarchy and freshness rules

1. **Current provider documentation controls provider semantics.** Historical emails, prompts and architecture capsules are discovery seeds, not current API or deployment authority.
2. **Primary sources control technical implementation.** Use official API documentation, source repositories, standards bodies and provider-native readback before blogs or summaries.
3. **Repository state controls local implementation claims.** Read the actual default-branch file, commit, workflow and test result before describing a capability.
4. **Production state controls live claims.** Require revision identity, configuration, authenticated health, target readback and rollback evidence.
5. **Sensitive data is never a resource to reuse.** Potential keys, tokens and credentials are metadata-only remediation objects until provider-side revocation or rotation is proved.
6. **Currentness is explicit.** Record retrieval date, source version or commit, and any draft/final status.

## 4. Mandatory operating gates

### OEB-G0 — Exact task contract

Before material work, record:

- exact user directive and intended result;
- in-scope and out-of-scope surfaces;
- factual assumptions and unresolved unknowns;
- authority needed for reads, writes, execution and external effects;
- proof and rollback requirements;
- completion language permitted by the available evidence.

### OEB-G1 — Single-agent-first orchestration

Start with one clearly instructed agent or deterministic controller. Add specialists, agents-as-tools or handoffs only when a measured requirement cannot be met by the single-agent path.

For every specialist or council role, define:

- narrow responsibility;
- allowed sources and tools;
- expected structured output;
- stop and escalation conditions;
- guardrails and approval boundaries;
- run ID, trace ID and evidence path;
- retirement or disable procedure.

Role templates, names and declared agent counts never prove that agents exist or ran.

### OEB-G2 — Strict schemas and bounded outputs

- Use Pydantic or JSON Schema for all machine-consumed inputs and outputs.
- Enable strict function schemas where supported.
- Set `additionalProperties: false` and require all declared fields; represent optional values with nullable types.
- Reject unknown fields for consequential actions.
- Separate raw model text from validated operational objects.
- Limit input size, output size, list sizes, attachment counts and concurrency.

### OEB-G3 — Tool and action guardrails

Every consequential tool must have:

- pre-execution input validation;
- exact target and account binding;
- authorization and approval checks;
- idempotency key or duplicate suppression;
- timeout, retry and backoff policy;
- bounded concurrency and resource limits;
- post-execution output validation;
- target-system readback;
- rollback or compensating action;
- structured error classification.

Handoffs do not replace tool-level guardrails. Built-in or hosted tools must be governed at the application boundary when SDK tool guardrails do not apply.

### OEB-G4 — Transactional integrity

A business-state mutation and its proof-ledger event must be atomic or connected by a durable transactional outbox. The system must not commit state and then separately attempt to write the audit event without a reconciliation mechanism.

Required properties:

- atomic commit or outbox;
- unique operation and idempotency identifiers;
- optimistic or pessimistic concurrency policy;
- replay-safe handlers;
- explicit terminal states;
- orphan and gap reconciliation;
- immutable event ordering;
- integrity verification that includes all material envelope fields.

### OEB-G5 — Observability and proof

- Create a workflow name, trace ID, group ID and operation ID for material runs.
- Trace model calls, tool calls, handoffs, guardrails, approvals and custom state transitions.
- Suppress sensitive model/tool payloads by default.
- Use structured logs with severity, event type, object ID and correlation ID.
- Store requested state, actual state, provider response, target readback and residual risk.
- `QUEUED`, `STARTED`, `SENT`, `MERGED`, `CI PASSED` and `DEPLOYED` are distinct states.
- A ledger entry is not execution proof.

### OEB-G6 — Real-path evaluations

Use traces while debugging, then maintain repeatable datasets and eval runs.

Every material workflow needs cases for:

- happy path;
- missing evidence or dependency;
- malformed and adversarial input;
- prompt injection or instruction conflict;
- required and forbidden tool calls;
- authorization and human-approval gates;
- duplicate and replay behavior;
- timeout, rate-limit and provider failure;
- partial write and recovery;
- stale state and contradiction;
- rollback;
- false-completion language;
- secret and restricted-data handling;
- regressions from every material incident.

Grade behavior, tool use, state change, proof and policy compliance rather than volatile prose.

### OEB-G7 — Security and privacy

- Authenticate users and services.
- Authorize every object and function access.
- Apply least privilege to service identities.
- Keep services private unless public access is an explicit approved requirement.
- Validate all third-party responses and do not trust connector output blindly.
- Apply rate, cost, payload, concurrency and storage limits.
- Protect against broken object-level and function-level authorization.
- Maintain an API inventory and remove stale endpoints.
- Redact or avoid sensitive data in logs and traces.
- Never put API keys in source, prompts, Gmail bodies, screenshots, ledgers or public repositories.
- Revoke and rotate suspected exposed credentials through the provider and preserve only non-secret receipts.

### OEB-G8 — Human review for high-stakes outputs

Human review is mandatory before:

- legal filing or external legal communication;
- irreversible or consequential external action;
- production promotion;
- credential or IAM mutation;
- use of generated code in a privileged path;
- factual allegation, diagnosis or merits conclusion based on model synthesis;
- permanent exclusion or destruction of evidence or capability material.

The reviewer must have direct access to the underlying source and proof packet.

### OEB-G9 — CI/CD and software supply chain

- Pin third-party GitHub Actions to full commit SHAs.
- Use least-privilege workflow permissions and OIDC instead of long-lived cloud keys.
- Lock production dependencies and use automated update review.
- Run unit, integration, security, typing, lint and secret-scanning gates.
- Produce dependency and image inventories; prefer SBOM and provenance attestations.
- Build immutable images and deploy by digest.
- Separate staging and production projects, identities, limits and approvals.
- Require zero-traffic canary, authenticated health, rollback and post-promotion readback.
- Do not auto-promote when critical gates are missing.

### OEB-G10 — Health and readiness truth

A health endpoint must not return `HEALTHY` when a critical integrity check fails. Separate:

- liveness — process can respond;
- readiness — dependencies and state are fit to serve;
- integrity — event chains and storage invariants pass;
- capability readiness — required tools, credentials and permissions are available;
- AI readiness — provider access is configured and a bounded smoke path passes.

Return a non-success status for failed critical readiness or integrity checks.

### OEB-G11 — Honest completion claims

Completion language must match the weakest unresolved material gate. Examples:

- branch created → `BRANCH_CREATED`;
- pull request merged → `MERGED_TO_MAIN`;
- CI passed → `MERGED_TO_MAIN_CI_PROVEN`;
- image pushed → `IMAGE_PUBLISHED`;
- canary ready and authenticated health passed → `CANARY_READBACK_PROVEN`;
- production traffic promoted and re-read → `PRODUCTION_DEPLOYMENT_READBACK_PROVEN`;
- archive inventory complete but body/attachment analysis incomplete → `INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE`.

## 5. Verified repository strengths at baseline date

The current repository already contains important controls:

- ECASP fail-closed G1–G11 corpus-selection logic;
- typed FastAPI request models;
- capability, claim, fault-route and promotion controls;
- hash-chained event records;
- SQLite thread locking and WAL mode;
- Cloud Run zero-traffic canary deployment;
- keyless GitHub OIDC/WIF authentication;
- authenticated canary health readback;
- rollback on failed post-promotion verification;
- deterministic unit and API tests;
- Firestore transactions for live-thread message sequencing.

These are implementation facts in the repository, not proof of a current production revision.

## 6. Current material gaps

| Priority | Gap | Current evidence | Required closure |
|---|---|---|---|
| P0 | State mutation and proof event are separate commits | `SuperiorLogicRuntime` commits state, then calls `append_event` | Atomic transaction or durable outbox; failure-injection tests |
| P0 | API authorization is not enforced inside the application | Mutating FastAPI endpoints have no principal/role dependency | Authenticated principal, function/object authorization, least privilege and negative tests |
| P0 | Default SQLite path is ephemeral `/tmp` | Docker and service defaults | Durable store or explicit ephemeral-only designation plus backup/recovery proof |
| P0 | Health reports `HEALTHY` regardless of event-chain result | `/health` returns status before evaluating readiness outcome | Separate liveness/readiness/integrity and return 503 on critical failure |
| P0 | Live AI work uses in-process background tasks | FastAPI `BackgroundTasks` invokes responder | Durable queue/worker, retry, lease, idempotency, dead-letter and recovery |
| P0 | Broad exception swallowing hides failure class | `except Exception` maps all AI failures to one code | Typed transport/auth/quota/rate/model/content errors; safe diagnostics and retry policy |
| P0 | Potential historical credential exposure remains unresolved | restricted metadata records exist | Provider-native inventory, revoke/rotate and non-secret receipt |
| P1 | No trace or eval harness for OpenAI live-thread behavior | direct Responses streaming call | trace metadata, safety identifier, representative traces, dataset and regression graders |
| P1 | No explicit output moderation or high-stakes approval boundary in live thread | instruction-only safety | risk-based moderation/guardrails, user reporting and human-review route |
| P1 | No durable request-level idempotency for write endpoints | endpoint models lack operation IDs | operation ID, unique constraint and replay response |
| P1 | No application-level rate/cost limits | no limiter or quotas in service code | per-principal and per-room limits, payload/concurrency caps, spend alerts |
| P1 | No explicit timeout/retry settings for OpenAI calls | default client and streaming call | bounded timeout, exponential backoff for retryable errors and terminal classification |
| P1 | No strict model-produced operational schema | live reply is free text | structured output for any machine-consumed result; free text remains display-only |
| P2 | GitHub Actions use mutable version tags | `actions/checkout@v4`, setup actions by tags | pin verified full SHAs and automate reviewed updates |
| P2 | Dependency ranges are not fully locked | Firestore and OpenAI use version ranges | reproducible lock/constraints, automated update PRs and compatibility tests |
| P2 | CI lacks lint, typing, coverage, dependency and secret scanning | unit tests and syntax checks only | Ruff/typing/coverage, dependency audit, CodeQL or equivalent, secret scan |
| P2 | No formal threat model or security policy | no controlling repository document | threat model, `SECURITY.md`, incident and disclosure path |

## 7. Immediate execution order

1. **Credential incident closure** — verify provider-side key inventory and rotate/revoke any exposed key; never retrieve the secret from the archived message.
2. **Atomic ledger integrity** — refactor state mutation plus event append into one transaction or outbox and add failure-injection tests.
3. **Application authorization** — bind callers to principals and roles; enforce object/function access on all write and state endpoints.
4. **Truthful readiness** — split health, readiness and integrity; fail readiness on chain or dependency failure.
5. **Durable AI jobs** — replace in-process background generation with a durable queue and replay-safe worker.
6. **OpenAI operational controls** — timeouts, retry classification, safety identifiers, trace metadata, sensitive-data suppression and real-path evals.
7. **Resource controls** — rate, payload, concurrency, token, cost and storage limits.
8. **Supply-chain hardening** — action SHA pinning, dependency lock, automated updates, secret scanning, SAST, typing and coverage.
9. **Deployment evidence** — immutable image digest, zero-traffic canary, authenticated readback, promotion and rollback receipt.
10. **Continuous improvement** — every material defect becomes a regression case and fault-route record.

## 8. Completion criteria for this baseline

This baseline may be called **fully implemented** only when:

- every P0 and P1 item has code, tests and readback evidence;
- the real OpenAI path has trace-linked eval results;
- secret remediation is provider-confirmed;
- CI supply-chain and security gates pass;
- a canary revision passes authenticated readiness and integrity checks;
- production promotion, if authorized, is followed by independent readback and rollback verification;
- the exact immutable commit, image digest, revision and evidence packet are recorded.

Until then, the correct status is:

`REFERENCE_BASELINE_CREATED_IMPLEMENTATION_INCOMPLETE`
