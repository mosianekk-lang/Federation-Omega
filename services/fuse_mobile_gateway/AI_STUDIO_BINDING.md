# Google AI Studio binding for FUSE Mobile

Google AI Studio is used at the Federation server layer, not from the mobile client.

Current admitted control route:

- `.github/workflows/sovara-ai-studio-semantic-canary.yml`
- `governance/sovara_ai_studio_semantic_canary_request_v1.json`
- runtime-injected `GEMINI_API_KEY`
- provider-native model discovery before `generateContent`
- exact zero-case-data semantic nonce
- redacted provider receipt.

The FUSE Mobile capability manifest may advertise this route as `CONFIGURED`, but it becomes routing-eligible only after a fresh semantic receipt supports a proof-bearing health state. A failed or stale AI Studio route must fall back through FIO/SOVARA without failing the whole mobile mission when another eligible provider exists.
