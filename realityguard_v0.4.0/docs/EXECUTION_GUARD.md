# Side-effect execution guard

ExecutionGuard is the additive v0.5 protection path for Federation-controlled tool calls. It runs at three boundaries:

1. preflight_tool_call before dispatch;
2. observe_dispatch after the provider returns;
3. guard_claim_release before a status such as DRAFT, SENT, FILED, or SERVED reaches the user.

The preflight fails closed on missing consumed Formation authority, absent idempotency, unsupported inline binary payloads, ambiguous recipients, routes without an exact semantic canary/readback path, and unchanged failed retries. Transport success and provider receipts remain weaker than independent semantic readback. A claim is released only when that exact state appears in verified_states.

The module is host-neutral and dependency-free. Importing or invoking it proves only a local/source guard invocation. It does not prove installation in native ChatGPT, interception of built-in connectors, provider deployment, or target runtime binding. Every unverified host remains ADAPTER_REQUIRED.

Run the original incident and repaired-route fixtures:

    PYTHONPATH=src python -m realityguard.cli execution-preflight --input examples/gmail_attachment_failure_execution_guard.json
    PYTHONPATH=src python -m realityguard.cli execution-preflight --input examples/gmail_attachment_repaired_execution_guard.json

The blocked route exits 7; an admitted read or dispatch exits 0.

