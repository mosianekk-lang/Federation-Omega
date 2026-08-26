# SOVARA Provider Execution Fabric v1

SOVARA provider execution is split into isolated cells. Each cell owns only its provider-specific credential resolution, metadata preflight, bounded semantic canary, provider readback, circuit state and rollback contract. No cell inherits another provider's credentials or authority.

The first concrete cell is OpenRouter on an owner-private, non-public Google Apps Script target. Its private executable source is hash-bound by the governance manifest; private project IDs and credential locators remain outside public source.

The OpenRouter cell deliberately removes legacy CloudOps and the historical Apps Script API consumer from the provider critical path. It has no public web endpoint, no Cloud Run dependency and no Google Cloud administrator dependency. Provider metadata must pass before any paid semantic call; exact nonce readback, generation identity, usage, latency and cost are required before aggregator admission.

LiteLLM v2.2 consumes cells progressively after cell-specific semantic proof. A broken Google/Gemini route therefore cannot immobilize a verified OpenRouter cell, and an OpenRouter failure cannot block direct OpenAI, local Ollama or other independent lanes.

Promotion order for OpenRouter: private source install and exact readback -> exactly one trigger -> provider metadata -> usable-limit admission -> exact-nonce GPT-5.6 Sol semantic readback -> generation/usage/cost readback -> LiteLLM cell admission -> forced fallback/recovery -> rollback readback.

Source or CI success never substitutes for provider execution proof.
