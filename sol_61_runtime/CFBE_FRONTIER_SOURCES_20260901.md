# CFBE SOL 6.1 Frontier Source Register — 2026-09-01

Evidence class: PUBLIC_OFFICIAL_DOCUMENTATION. This file records benchmark patterns only; public product claims do not self-certify SOL implementation or superiority.

- Temporal: crash-proof durable execution and resume-after-failure workflow model.
- AWS Durable Execution SDK: explicit at-least-once vs at-most-once step semantics, stable idempotency tokens, interruption handling, conditional/transactional writes.
- Kubernetes: lease-based coordination, leader election and resource-version/optimistic-concurrency patterns.
- OpenAI Agents SDK: minimal agent primitives, handoffs, input/output/tool guardrails, sessions, sandbox agents and detailed agent/tool/handoff/guardrail tracing.
- Google Cloud Workflows: parallel branches for independent blocking work and durable workflow orchestration.
- Azure Durable Functions / Durable Task: deterministic orchestration and durable state/replay patterns.
- AWS Bedrock AgentCore: governed runtime gateway, workload identity, policy/guardrails/interceptors and OpenTelemetry-compatible agent observability.
- OpenTelemetry: standardized semantic conventions for spans, metrics, logs and events.
- SPIFFE/SPIRE: workload identity and short-lived workload credentials/SVIDs.
- SLSA 1.2: verifiable source/build provenance and expectation-based verification.
- Sigstore: keyless OIDC-bound signing, short-lived certificates and transparency-log verification.

CFBE harvest law: REUSE -> EXTEND -> COMPOSE -> NEW LAST. Capabilities are mapped to existing SOL control planes and proof gates; vendor authority or maturity never transfers by analogy.
