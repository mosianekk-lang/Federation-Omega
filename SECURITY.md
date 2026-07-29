# Security Policy

## Supported security scope

Security reports may concern the Superior Logic Runtime, ECASP, live-thread services, deployment workflows, Firestore integration, OpenAI-backed paths, Apps Script assets, authentication, authorization, data exposure, audit integrity, supply-chain configuration or secrets handling.

A branch, commit, test, workflow run or architecture document is not proof that a vulnerability is deployed. Reports should identify the affected repository path and, where known, the immutable commit, image digest, service revision or endpoint.

## Reporting a vulnerability

Use GitHub **Private Vulnerability Reporting** for this repository when it is available. Do not place sensitive findings, credentials, private URLs, personal information, legal evidence or exploit details in a public issue, pull request, discussion or commit.

A useful report contains:

- affected component and exact path;
- commit, tag, image digest or revision where known;
- preconditions and required privileges;
- reproducible steps using non-sensitive test data;
- expected and actual behavior;
- impact and affected data or authority boundary;
- logs or traces with secrets and personal data removed;
- suggested mitigation, if known.

Do not access, alter, destroy or disclose data beyond the minimum necessary to demonstrate the issue. Do not perform denial-of-service, persistence, privilege escalation against live systems, social engineering, credential stuffing or testing against third-party accounts without explicit authorization.

## Credential and secret handling

Never include an API key, token, password, private key, cookie, authorization header, recovery code or secret-bearing screenshot in:

- source code or Git history;
- issues, pull requests or review comments;
- prompts, chat transcripts or generated examples;
- logs, traces, ledgers or analytics;
- Gmail, Drive or public documents;
- test fixtures or CI artifacts.

Potential credential-bearing archive objects are handled as **metadata-only security-remediation records**. Their content must not be read, quoted, OCR-processed, transferred, indexed into case evidence or reused in a runtime.

When exposure is suspected:

1. stop using the credential;
2. identify the provider, organization/project and affected workload without printing the secret;
3. revoke or rotate through the provider-native control plane;
4. update only an approved secret store or ignored local environment file;
5. invalidate dependent sessions or tokens where applicable;
6. inspect access and usage logs for misuse;
7. test the replacement through a bounded smoke path;
8. preserve a non-secret receipt containing provider, key identifier or fingerprint, action, timestamp and result;
9. scan repository history, CI artifacts, logs and connected storage for further exposure;
10. add a regression control preventing recurrence.

A suspected secret remains `ROTATION_UNVERIFIED` until provider-native readback proves revocation or rotation.

## Security design requirements

All consequential interfaces must enforce:

- authenticated principals and service identities;
- object-level and function-level authorization;
- least privilege;
- strict request schemas and unknown-field rejection;
- idempotency or replay protection;
- bounded payload, rate, concurrency, token, cost and storage use;
- safe third-party API consumption and response validation;
- sensitive-data suppression in logs and traces;
- transactional state and audit integrity;
- explicit approval for privileged or irreversible actions;
- post-action target readback and rollback or compensation.

Public access is prohibited unless it is an explicit, reviewed product requirement. A hidden or unguessable URL is not authorization.

## AI-specific security requirements

OpenAI-backed or other model-backed paths must:

- keep model output separate from validated operational objects;
- use strict structured outputs for machine-consumed results;
- apply tool-level input and output guardrails;
- red-team prompt injection, instruction conflict and unsafe tool use;
- use representative trace-linked evaluations;
- require human review for high-stakes legal, security, IAM, production and irreversible actions;
- suppress sensitive model and tool payloads from tracing by default;
- classify transport, authentication, quota, rate-limit, model-access and content failures separately;
- avoid treating model confidence, fluent prose, role names or multi-agent consensus as evidence.

## Response and remediation states

Security work uses the following states:

- `REPORTED`
- `TRIAGED`
- `REPRODUCED`
- `CONTAINED`
- `FIX_IN_REVIEW`
- `FIX_MERGED`
- `CANARY_READBACK_PROVEN`
- `PRODUCTION_REMEDIATION_READBACK_PROVEN`
- `CLOSED_WITH_REGRESSION_TEST`

`FIX_MERGED` does not mean a live deployment is remediated. Closure requires the applicable target-system readback and a regression test.

## Safe-harbor intent

Good-faith research that follows this policy, minimizes impact and reports privately will be treated as authorized security research for this project to the extent the repository owner has authority to grant it. This statement does not authorize testing of third-party systems, accounts, data or infrastructure.
