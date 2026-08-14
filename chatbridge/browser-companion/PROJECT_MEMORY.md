# Project memory

## Controlling context

- Canonical universal registry: `CHATBRIDGE — UNIVERSAL — REGISTRY.md`.
- Canonical experience adapter at discovery: `CHATBRIDGE — chatgpt-experience — CURRENT.md`, revision 48 / Library version 47.
- Existing Federation Omega recovery engine: `evidenceops/build_system/chat_failure_resilience.py`.

## Decision

OpenAI plugin/MCP UI is sandboxed inside a component iframe and cannot replace the host warning. The immediate route is a Manifest V3 browser companion plus canonical ChatBridge capsules. The native action remains a fallback.

## Verification state

- JavaScript syntax checks: 4/4 passed.
- Deterministic Node tests: 5/5 passed.
- Manifest and build-contract JSON validation: passed.
- MODISA contract validation: passed.
- Secret/network primitive scan: no matches.
- Supplied screenshot: exact warning and route pattern verified.

## Next proof gate

A signed-in Chrome/Edge canary must prove the current ChatGPT DOM selectors, route preservation, composer insertion, automatic send behavior, and one-time transfer consumption. Until then: `IMPLEMENTED_NOT_DEPLOYED`.
