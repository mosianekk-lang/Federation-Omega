# OpenAI provider readback contract

This contract closes the deterministic engineering gap between a CASEFORGE OpenAI blind execution receipt and an independently re-read provider response/model resource.

## Provider execution is not provider verification

A successful tested-agent call remains `PROVIDER_EXECUTED_UNREADBACK` until a separate `ProviderReadbackVerifier` confirms the response identity/model/status and produces a verified provider-visible model-resource identity.

`OpenAIStoredResponseReadbackVerifier` performs the bounded provider-native path for public/synthetic canaries:

1. retrieve the stored Response by response ID;
2. verify response ID, provider-returned model and status against the original execution receipt;
3. retrieve the provider model resource by returned model ID;
4. require matching model-resource ID plus non-empty provider `created` and `owned_by` metadata;
5. bind those fields into a non-secret model-resource version string and provider readback reference;
6. return only the metadata receipt; never copy credentials into source or receipts.

## Privacy gate

Stored-response verification is allowed only when the blind pack explicitly declares `provider_storage_classification` as `PUBLIC_SYNTHETIC` or `PUBLIC_SOURCE_DERIVED_SYNTHETIC` and `external_effect` is false. Private/confidential evidence is not eligible for this stored-response route and requires a different provider-native proof mechanism.

`CF-UTILITY-ZA-001` is explicitly marked `PUBLIC_SYNTHETIC` for this bounded canary route.

## Maturity boundary

This source/test contract does not prove an OpenAI API call occurred. Provider execution, provider response readback and model-resource readback require an already-authorised runtime and non-secret credential binding. Hidden scoring remains separate from the tested-agent/provider context, and independent replication remains a later gate.
