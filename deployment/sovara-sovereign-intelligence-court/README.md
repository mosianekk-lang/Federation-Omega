# SOVARA Sovereign Intelligence Court v2 deployment

This directory packages the chat-native court as a persistent MCP service.

## Runtime contract

The production service exposes MCP Streamable HTTP at `/mcp`. ChatGPT is a client terminal; mission state is stored outside the chat.

Use `SOVARA_STATE_BACKEND=gcs` with a private durable bucket for production. `file` mode exists for local development and CI only unless the filesystem is independently proven durable across runtime replacement.

Runtime configuration:

- `SOVARA_STATE_BACKEND=gcs`
- `SOVARA_STATE_BUCKET=<private bucket>`
- `SOVARA_STATE_PREFIX=sovara/sic-v2`
- `OPENROUTER_API_KEY` supplied only through the runtime secret boundary
- `PORT` supplied by the hosting platform

The GCS store uses object-generation preconditions so concurrent checkpoint writers fail closed instead of silently overwriting state. Provider credentials are resolved from runtime identity/secret surfaces and are never stored in mission records.

## Build

```bash
docker build -f deployment/sovara-sovereign-intelligence-court/Dockerfile -t sovara-sic-v2 .
```

## Truth boundary

A container image is not a deployment. A deployment is not ChatGPT connectivity. ChatGPT connectivity is not OpenRouter proof. Each state advances only after provider/client readback.

GitHub Actions remains CI/admission/canary infrastructure. It is not the primary SOVARA runtime.
