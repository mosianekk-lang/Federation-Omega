# FUSE Sovereign Capability Platform v0.4 — FCOA Bridge

v0.4 binds the **existing FCOA-Ω Creative Operator Agent** (`WP-FCOA-BOOTSTRAP-001`, passport `ECP-FCOA-OMEGA-V1-001`) to the Sovereign Platform without creating a second agent/controller.

## What FCOA gains

- verified FUSE currentness via `LLMUpdateBridge`
- live capability/executor discovery from `SovereignEngine`
- provider-neutral LLM cognition through `LLMGateway`
- task execution through the same safety/authority/router/audit plane as every other FUSE worker
- local/private preference inherited from the platform router
- no implicit authority inheritance from LLM access

## LLM binding

No model is fabricated or silently assumed. Bind a genuine OpenAI-compatible/local endpoint using environment variables:

```text
FUSE_LLM_BASE_URL=http://127.0.0.1:1234
FUSE_LLM_MODEL=<actual model id>
FUSE_LLM_PROVIDER_ID=<optional provider id>
FUSE_LLM_API_TOKEN=<optional host secret; never exposed to FCOA context>
```

FCOA sees model output, not the credential material used by the host.

## CLI

```text
FUSE-Sovereign-Platform.exe --self-test
FUSE-Sovereign-Platform.exe --fetch-updates
FUSE-Sovereign-Platform.exe --fcoa-status
FUSE-Sovereign-Platform.exe --fcoa-think "Develop a poster concept"
```

Without a genuine model binding, `--fcoa-think` fails closed with `NO_QUALIFIED_LLM_PROVIDER`.

## Authority boundary

Connectivity and model output are cognition/capability inputs only. FCOA cannot inherit source, IAM, publication, external-write, credential, lease, or spending authority merely by reaching the platform or LLM.
