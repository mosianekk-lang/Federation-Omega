# SOVARA Creative OpenRouter policy adapter v1

This source-only adapter prepares an OpenRouter request contract and evaluates a
provider response receipt. It performs no network call, credential lookup,
deployment, publishing action, provider mutation, or production promotion.

## Safety and authority boundary

- Lawful mature/adult-oriented work requires verified adults and consent.
- Ambiguous age, minors, coercion, non-consensual material, hidden-camera
  exploitation, and non-consensual real-person sexual impersonation fail closed.
- `SECRET`, `PRIVATE_ASSET`, and `SENSITIVE_PERFORMER` data do not enter the
  initial external OpenRouter lane. Those classes stay sovereign or
  non-generative.
- OpenRouter availability never establishes a downstream model/provider's
  content eligibility. A current, expiring policy snapshot is mandatory.
- The adapter never obfuscates prompts, retries a policy denial through another
  provider, or treats a gateway as permission to bypass model/provider rules.
- The adapter carries only the non-secret credential reference
  `env:OPENROUTER_API_KEY`; a live secret and spend authority remain separate
  runtime gates.

## Request invariants

Every ready plan uses an explicit downstream provider allowlist and sets:

- `allow_fallbacks=false`
- `require_parameters=true`
- `data_collection=deny`
- `zdr=true`
- optional per-million-token `max_price` ceilings
- strict JSON Schema output when the selected endpoint's current support is
  independently verified
- `X-OpenRouter-Metadata: enabled` as a required non-secret header

The planner labels its result `READY_SOURCE_ONLY`; this is not provider
admission or execution authority.

## Receipt invariants

A 2xx response is insufficient. Admission requires separate readback of:

1. OpenRouter generation ID;
2. exactly one selected downstream provider display label from router metadata;
3. exact top-level and selected-endpoint model readback;
4. prompt and completion token usage;
5. actual reported cost;
6. an expected semantic marker; and
7. a SHA-256 output fingerprint.

Raw generated output is not retained in the receipt. Missing, fallback/retry,
or unexpected provider/model metadata; malformed, negative, or non-finite
usage/cost; a cost-cap excess; or semantic mismatch remains a held state.

## Current documentation basis

- [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter API overview](https://openrouter.ai/docs/api_reference/overview)
- [OpenRouter provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging)
- [OpenRouter zero data retention](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging)
- [OpenRouter router metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [OpenAI safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices)
- [OpenAI moderation guide](https://developers.openai.com/api/docs/guides/moderation)

## Next proof gate

After exact-head source CI, a live canary still requires a current credential
handle, finite cost envelope, task/model/provider eligibility snapshot, and one
public-synthetic semantic request. That provider effect is deliberately outside
this adapter and must produce its own immutable receipt.
