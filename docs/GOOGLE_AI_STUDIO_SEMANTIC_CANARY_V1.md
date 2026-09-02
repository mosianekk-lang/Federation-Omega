# Google AI Studio Semantic Canary v1

This canary exists to close exactly one proof gap: whether the Federation's existing `gemini-api-key` can perform a live, exact semantic readback against the Gemini Developer API.

It is owner-triggered, one-shot, keyless-WIF hosted, non-mutating, and artifact-only. The API key may exist transiently in runner memory but is never written to repository source, logs, summaries, artifacts, or receipts. A successful run requires model discovery and `generateContent` to return a nonce exactly; anything weaker remains provider-gated.

This proof does not grant general Google Cloud mutation authority, change IAM, enable APIs, create infrastructure, modify traffic, establish unlimited inference capacity, establish cost guarantees, or prove owner value.
