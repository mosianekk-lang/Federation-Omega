# EvidenceOps AI ICT durable runtime overlay v2.5

This non-secret production overlay closes a missing durability and approval boundary in the model-backed runtime.

It adds:

- encrypted-at-rest persistence for serialized OpenAI Agents SDK `RunState` data;
- explicit exclusion of the tracing API key from serialized state;
- run-scoped model and tracing credentials without process-global environment mutation;
- SDK-correct tracing configuration as a per-run mapping;
- an explicit SDK-generated trace ID carried into each receipt;
- asynchronous `RunState.from_json` restoration with the required initial agent and strict context validation;
- pause, persisted approval decision, and resume contracts for sensitive tool calls;
- exact-output live canary validation;
- trace, response, token-usage, interruption, and state-version receipt fields;
- PostgreSQL migration and a local SQLite verification implementation;
- an independent GitHub Actions gate that installs the exact `openai-agents==0.19.2` release and verifies its pause/resume and tracing API contract without using a credential.

Production remains fail-closed until a managed KMS-backed `StateProtector`, an authorised OpenAI credential, private PostgreSQL, and canonical write/readback are bound.

Boundary owner: `WORKFORCE`  
Boundary state: `ACTIVE_REPAIR`
