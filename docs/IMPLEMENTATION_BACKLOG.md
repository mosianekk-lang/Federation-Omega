# Operating Excellence Implementation Backlog

**Backlog ID:** `FO-OEB-BACKLOG-20260729-001`  
**Governing baseline:** `docs/OPERATING_EXCELLENCE_BASELINE.md`  
**Current status:** `REFERENCE_BASELINE_CREATED_IMPLEMENTATION_INCOMPLETE`

This backlog is ordered by risk reduction and dependency. A work item is not complete because code was written or merged. Its acceptance evidence must include the stated tests and readback.

## P0 — Integrity, authority and secret containment

### OEB-P0-001 — Atomic state mutation and proof event

**Problem:** Runtime methods commit business state and then append the proof event in a second transaction. A process failure can leave state without its corresponding audit event.

**Implementation:**

- introduce a transaction helper or transactional outbox;
- write the state mutation and event/outbox record in one database transaction;
- use a stable operation ID and unique constraint;
- make replay idempotent;
- reconcile unsent outbox records;
- include operation ID, principal, target, previous state and new state in the event envelope.

**Acceptance tests:**

- injected failure before commit leaves neither state nor event;
- injected failure after atomic commit leaves state and durable outbox/event;
- duplicate operation ID does not repeat the state change;
- concurrent updates preserve valid ordering;
- event-chain verification passes after restart;
- orphan-reconciliation test proves eventual event publication.

**Completion evidence:** commit, test run, migration/readback, event-chain check and recovery transcript.

### OEB-P0-002 — Application authentication and authorization

**Problem:** Consequential API routes do not bind requests to authenticated principals or enforce function/object authorization.

**Implementation:**

- define principal, role and service-identity models;
- authenticate bearer or service identity through a documented trust boundary;
- authorize each endpoint by action, object and environment;
- deny by default;
- record principal and authorization decision without storing credentials;
- separate read, write, execute, approve and administer permissions;
- protect `/state`, capability registration, fault mutation, route clearing, promotion and external-action endpoints.

**Acceptance tests:**

- unauthenticated request denied;
- valid principal without function permission denied;
- object-level cross-tenant or cross-mission access denied;
- authorized bounded action succeeds;
- role escalation and forged claim denied;
- authorization decision appears in the proof event;
- no credential or authorization header appears in logs.

**Completion evidence:** threat model, policy matrix, tests, authenticated canary readback and negative-request transcript.

### OEB-P0-003 — Credential exposure remediation gate

**Problem:** Archive metadata indicates potential historical API-key exposure. Secret content is quarantined and rotation state is not proved.

**Implementation:**

- inventory relevant provider keys by safe metadata only;
- revoke or rotate suspected exposed credentials through the provider;
- update approved secret stores and dependent workloads;
- invalidate dependent sessions where applicable;
- scan repository history, logs, CI artifacts and connected storage;
- preserve non-secret provider receipts;
- add secret scanning and pre-commit/CI prevention.

**Acceptance tests:**

- old credential is rejected without printing it;
- replacement credential passes a bounded smoke test;
- repository and artifact scans report no active secret;
- logs and traces contain no plaintext secret;
- restricted register links to non-secret rotation receipt.

**Completion evidence:** provider-native revoke/rotate receipt, safe key identifier/fingerprint, scan results and smoke-readback result.

### OEB-P0-004 — Truthful liveness, readiness and integrity

**Problem:** `/health` reports `HEALTHY` even when a critical integrity field could be false.

**Implementation:**

- split liveness, readiness and integrity endpoints or clearly typed sections;
- return non-2xx readiness when event-chain integrity or required dependencies fail;
- declare optional versus critical dependencies;
- expose immutable version/commit information;
- avoid leaking environment or secret details.

**Acceptance tests:**

- process liveness remains available during dependency failure;
- readiness returns 503 for corrupted event chain;
- readiness returns 503 for unavailable critical storage;
- optional AI provider unavailability is represented accurately according to route requirements;
- healthy response includes exact service version and integrity result;
- deployment workflow fails on unhealthy readiness.

**Completion evidence:** API tests, corrupted-state test, authenticated canary readback and deployment-gate result.

### OEB-P0-005 — Durable live-AI job execution

**Problem:** In-process FastAPI background tasks can be lost during restart, scaling or worker failure.

**Implementation:**

- place AI jobs in a durable queue or transactional work table;
- use leases, retry counts, heartbeat, visibility timeout and dead-letter state;
- make the trigger sequence and job ID idempotent;
- recover abandoned jobs;
- separate queued, generating, completed, failed and dead-letter states;
- append the assistant message and final job state atomically or through an outbox;
- support graceful shutdown and bounded worker concurrency.

**Acceptance tests:**

- restart after enqueue retains the job;
- restart during generation safely retries or terminally classifies;
- duplicate trigger does not create duplicate assistant messages;
- expired lease is reclaimed once;
- retryable and non-retryable failures diverge correctly;
- dead-letter record contains safe diagnostic metadata;
- final assistant message hash and job proof agree.

**Completion evidence:** real queue/store transcript, restart test, duplicate test, dead-letter test and target readback.

### OEB-P0-006 — Durable production state

**Problem:** Default SQLite storage is `/tmp`, which is ephemeral in common container deployments.

**Implementation:**

- designate SQLite mode as local/test only or mount supported durable storage;
- select a production data store with transaction and recovery guarantees;
- define schema migration, backup, restore and retention procedures;
- encrypt data in transit and at rest through the platform;
- prove least-privilege service identity.

**Acceptance tests:**

- service restart and revision replacement preserve required state;
- backup restore recreates event chain and route memory;
- migration rollback is tested;
- unauthorized identity cannot access storage;
- recovery-point and recovery-time expectations are measured.

**Completion evidence:** architecture decision, restore drill, IAM readback and integrity verification.

## P1 — OpenAI path, evaluation and operational controls

### OEB-P1-001 — Typed OpenAI failure classification and retry

**Implementation:**

- distinguish transport, authentication, quota, rate-limit, model/project access, invalid request, safety/content and internal failures;
- set bounded connect/read/total timeouts;
- retry only retryable failures with exponential backoff and jitter;
- honor provider retry guidance where available;
- cap attempts and elapsed time;
- store safe error class, request/trace identifier and terminal state;
- never log a key or full sensitive prompt.

**Acceptance tests:** simulated cases for every error class, retry budget, non-retryable immediate stop and redacted diagnostics.

### OEB-P1-002 — Trace-linked OpenAI observability

**Implementation:**

- assign workflow, trace, group and operation IDs;
- attach model, prompt/instruction version and policy version;
- trace model calls, guardrails, tool calls, handoffs and approvals;
- suppress sensitive input/output by default;
- preserve provider request identifiers when safely available;
- link final message and proof event to the trace.

**Acceptance tests:** one successful and one failed real-path run with trace linkage; sensitive-data redaction test; orphan trace detection.

### OEB-P1-003 — Real-path evaluation harness

**Implementation:**

- create `evals/cases.jsonl`, graders and a real-path runner;
- isolate/reset state per case;
- include happy path, missing evidence, injection, unsafe request, authorization, duplicate, timeout, rate limit, stale state, contradiction, rollback, false-completion and restricted-secret cases;
- grade output structure, tool use, guardrail result, state changes, evidence references and completion language;
- write machine-readable results and fail CI on critical regression.

**Acceptance tests:** all cases run through the actual responder/controller path; deliberate regression causes non-zero exit; results preserve trace IDs without secrets.

### OEB-P1-004 — Model-output boundary and structured operational results

**Implementation:**

- keep conversational display text separate from operational decisions;
- use strict structured outputs for any machine-consumed classification, action proposal or proof record;
- validate before acting;
- reject additional fields and invalid enums;
- require source references and uncertainty state for factual synthesis;
- prohibit free text from directly forming privileged tool parameters.

**Acceptance tests:** malformed output rejected, extra property rejected, prompt-injected tool parameter blocked, valid structured object accepted.

### OEB-P1-005 — Safety, moderation and high-stakes review

**Implementation:**

- define a risk classifier and escalation path;
- add input/output safety checks appropriate to the shared-thread use case;
- maintain neutral shared-room instructions;
- support user reporting and incident review;
- require human review before legal, security, IAM, production or irreversible actions;
- record reviewer, source access and decision without exposing sensitive content.

**Acceptance tests:** threats/coercion/surveillance prompts, unsafe transformation, private-intent inference and high-stakes action all follow the required safe route.

### OEB-P1-006 — Idempotency and replay protection for API writes

**Implementation:** require operation IDs on consequential writes, unique persistence, request-hash comparison and deterministic replay response.

**Acceptance tests:** identical replay returns original result; conflicting payload with reused key is rejected; concurrent duplicate creates one effect.

### OEB-P1-007 — Resource, abuse and cost controls

**Implementation:**

- per-principal and per-room request limits;
- global and worker concurrency caps;
- message, history and output limits;
- model token and spend budgets;
- storage retention and maximum room size;
- circuit breakers for provider or dependency failure;
- alerts for abnormal usage.

**Acceptance tests:** boundary values, burst traffic, slow requests, oversized payload, excessive history, cost-budget exhaustion and recovery.

### OEB-P1-008 — Safe external API consumption

**Implementation:**

- maintain an approved connector/API inventory;
- validate response schemas and content types;
- enforce allowlisted hosts and TLS;
- set timeouts and response-size limits;
- treat third-party data as untrusted;
- prevent server-side request forgery and redirect abuse;
- verify connector-side action results through target readback.

**Acceptance tests:** malformed response, oversized response, redirect to unapproved host, stale connector result and false-success response.

## P2 — Supply chain, maintainability and governance

### OEB-P2-001 — Pin GitHub Actions to immutable SHAs

Replace mutable action tags with reviewed full commit SHAs. Retain a comment showing the human-readable release tag. Use Dependabot to propose reviewed updates.

**Acceptance tests:** policy scan rejects non-SHA third-party actions; workflows pass after pinning.

### OEB-P2-002 — Reproducible Python dependency lock

Adopt `pyproject.toml` and a reproducible lock or constraints workflow. Separate runtime, development and test dependencies. Automate reviewed updates.

**Acceptance tests:** clean-environment install is reproducible; dependency resolution drift is detected; supported Python version test passes.

### OEB-P2-003 — Expanded CI quality and security gates

Add:

- formatting/linting;
- static typing;
- coverage threshold;
- dependency vulnerability audit;
- secret scanning;
- SAST/CodeQL or equivalent;
- container/image scan;
- workflow-policy scan;
- generated SBOM and provenance where supported.

Critical security or correctness failures must block merge.

### OEB-P2-004 — Threat model and architecture decisions

Create a threat model covering users, service identities, rooms, evidence, prompts, model calls, tools, Firestore, SQLite, GitHub Actions, Cloud Run and connected services. Record consequential choices as architecture decision records.

### OEB-P2-005 — API inventory and deprecation

Maintain endpoint owner, auth mode, data classification, consumers, rate limits, version and removal date. Deprecate and remove stale routes safely.

### OEB-P2-006 — Runbooks and incident exercises

Create runbooks for:

- credential exposure;
- event-chain failure;
- queue backlog or dead letter;
- provider outage/quota/rate limit;
- Firestore or database failure;
- failed canary/promotion rollback;
- unauthorized access;
- data restoration.

Exercise them with non-production data and preserve proof.

## Definition of done for any item

An item reaches `PROVEN` only when all applicable evidence exists:

1. exact requirement and threat mapped;
2. implementation committed;
3. unit and integration tests pass;
4. adversarial and failure-injection tests pass;
5. security and privacy review passes;
6. CI identifies the immutable commit;
7. canary or target deployment identifies immutable image/revision;
8. authenticated readiness and target readback pass;
9. rollback or recovery is demonstrated;
10. proof packet and residual risks are recorded;
11. a regression case is retained.

Otherwise report the strongest truthful intermediate state, such as `CONTROL_SPECIFIED`, `IMPLEMENTED_NOT_DEPLOYED`, `CI_PROVEN`, or `CANARY_READBACK_PROVEN`.
