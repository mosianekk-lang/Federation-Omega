# Contributing to Federation Omega

All changes follow the proof-driven workflow in `docs/OPERATING_EXCELLENCE_BASELINE.md` and the acceptance criteria in `docs/IMPLEMENTATION_BACKLOG.md`.

## 1. Classify the change

Before editing, identify:

- requested outcome;
- affected component, data and environment;
- change class: documentation, internal reversible, external consequential, security, credential/IAM, data migration or production;
- required authority and reviewer;
- failure and rollback path;
- evidence needed for the strongest permitted completion claim.

Do not combine unrelated high-risk changes in one pull request.

## 2. Inspect before changing

Read the current default-branch versions of:

- `README.md`;
- relevant source and tests;
- `SECURITY.md`;
- applicable workflow and deployment files;
- current provider documentation for any external API or platform behavior;
- open pull requests or incidents affecting the same path.

Historical prompts, emails and architecture notes may guide discovery but do not override current source or provider documentation.

## 3. Branch and commit discipline

- create a focused branch from the current default branch;
- use small, reviewable commits;
- never rewrite shared history to conceal faults;
- do not commit secrets, private evidence, generated credentials or sensitive traces;
- preserve provenance when transforming or migrating data;
- include migrations and rollback logic with state changes.

## 4. Implementation rules

### APIs and tools

- use typed request and response schemas;
- reject unknown fields for consequential actions;
- authenticate and authorize by principal, function and object;
- require idempotency for replayable writes;
- set payload, timeout, rate and concurrency bounds;
- validate third-party responses;
- read back the target after side effects;
- classify errors rather than swallowing broad exceptions.

### State and audit

- state mutation and proof event must be atomic or use a durable outbox;
- include operation and correlation identifiers;
- preserve immutable ordering and replay safety;
- distinguish queued, started, completed, failed, dead-lettered and verified states;
- never treat a ledger entry as proof that an external action occurred.

### OpenAI-backed paths

- follow the current official OpenAI documentation;
- start with one agent/controller and add specialists only for a measured need;
- use strict structured outputs for machine-consumed results;
- keep display text separate from operational objects;
- apply tool-level guardrails and explicit approvals;
- use bounded timeouts and typed retry handling;
- attach trace/group/operation metadata while suppressing sensitive payloads;
- maintain real-path evaluations and regression cases;
- obtain human review for high-stakes legal, security, IAM, production or irreversible use.

## 5. Testing requirements

Every behavioral change needs tests for the real path and the material failure path.

At minimum consider:

- happy path;
- invalid and adversarial input;
- unauthorized access;
- duplicate/replay behavior;
- concurrency;
- timeout and provider failure;
- partial write and restart;
- stale state and contradiction;
- rollback;
- restricted-data handling;
- false-completion language;
- regression from the incident that motivated the change.

Tests must isolate state, avoid live secrets and fail with a non-zero exit code.

## 6. Pull request requirements

A pull request description must state:

- exact problem and user-visible outcome;
- files and interfaces changed;
- threat/risk addressed;
- tests run and results;
- migrations and rollback;
- security/privacy impact;
- remaining gaps;
- truthful maturity state;
- evidence needed before deployment or production claims.

Use a draft pull request while material gates remain open.

## 7. Review requirements

Reviewers must inspect source and tests, not only the summary.

Request specialist review for:

- security, authentication, authorization or secrets;
- database transactions and migrations;
- external legal or evidentiary workflows;
- OpenAI tool execution and high-stakes model outputs;
- GitHub Actions, IAM, WIF or production deployment;
- irreversible data or capability exclusion.

A reviewer must not approve a production or legal action based solely on model-generated prose.

## 8. Merge and deployment states

Use exact states:

- `BRANCH_CREATED`
- `IMPLEMENTED_NOT_REVIEWED`
- `PR_OPEN`
- `CI_PROVEN`
- `MERGED_TO_MAIN`
- `IMAGE_PUBLISHED`
- `CANARY_READBACK_PROVEN`
- `PRODUCTION_DEPLOYMENT_READBACK_PROVEN`
- `CLOSED_WITH_REGRESSION_TEST`

Do not collapse these into “done”, “live” or “complete”.

## 9. Production promotion

Production promotion requires:

- immutable commit and image digest;
- passing quality and security gates;
- explicit approval;
- least-privilege authenticated deployment;
- zero-traffic canary;
- authenticated readiness and integrity readback;
- rollback target and tested rollback action;
- post-promotion target readback;
- proof packet with residual risk.

## 10. Incident learning

Every material failure becomes:

- a fault record;
- a banned or constrained route when appropriate;
- a root-cause note;
- a regression test;
- a repaired control or runbook;
- a readback proving the repair.

Do not close an incident because the wording was corrected. Close it only after the causal control is repaired and verified.
