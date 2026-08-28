# SOVARA Sovereign Intelligence Court v2 deployment

This package turns the SOVARA external code evaluator into a persistent MCP service. ChatGPT is a client terminal; mission state lives in the service runtime.

## Required runtime configuration

- `OPENROUTER_API_KEY`: optional external-provider credential. If absent, the court records a provider-unavailable boundary and continues any attached sovereign/local/deterministic lanes.
- `SOVARA_STATE_DIR`: durable writable mission-state directory. Production deployments should mount persistent storage rather than relying on container-local ephemeral disk.

## Production contract

- expose the MCP Streamable HTTP endpoint over HTTPS;
- persist `SOVARA_STATE_DIR` outside an individual container instance;
- do not place provider credentials in images, source, prompts, mission snapshots, or receipts;
- treat GitHub Actions as CI/admission/canary infrastructure, not the production runtime;
- never promote external model output directly into canonical source;
- preserve provider/platform boundary events and continue unrelated safe lanes.

## Container build

```bash
docker build -f deployment/sovara-sovereign-intelligence-court/Dockerfile -t sovara-sovereign-intelligence-court:2.0.0 .
```

The final ChatGPT-facing tool name is `sovara_external_model_review`.
