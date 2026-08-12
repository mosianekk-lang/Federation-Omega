# OpenAI provider readback contract

This contract closes the deterministic engineering gap between a CASEFORGE OpenAI blind execution receipt and an independently re-read provider response/model resource.

## Provider execution is not provider verification

A successful tested-agent call remains `PROVIDER_EXECUTED_UNREADBACK` until a separate `ProviderReadbackVerifier` confirms the response identity/model/status, verifies the explicitly requested response configuration exposed by provider readback, and produces a provider-visible model-resource identity.

`OpenAIStoredResponseReadbackVerifier` performs the bounded provider-native path for public/synthetic canaries:

1. retrieve the provider-stored Response by response ID;
2. verify response ID, provider-returned model and status against the original execution receipt;
3. verify each explicitly requested readback-visible configuration field, including `store` and any admitted `max_output_tokens`, `temperature`, `top_p`, `truncation`, `reasoning` or `text` subset;
4. retrieve the provider model resource by returned model ID;
5. require matching model-resource ID plus provider `created` and `owned_by` metadata;
6. bind the request-configuration SHA-256, model-resource metadata and response identity into a non-secret provider readback receipt;
7. never copy credentials into source, output or receipts.

The model-resource identity is a provider-native model/version reference. It is not represented as a model-weights hash or as a stronger identity than the provider exposes.

## Privacy gate

Stored-response verification is allowed only when the blind pack explicitly declares `provider_storage_classification` as `PUBLIC_SYNTHETIC` or `PUBLIC_SOURCE_DERIVED_SYNTHETIC` and `external_effect` is false. Private/confidential evidence is not eligible for this stored-response route and requires a different provider-native proof mechanism.

`CF-UTILITY-ZA-001` is explicitly marked `PUBLIC_SYNTHETIC` for this bounded canary route.

## Callable canary

`openai_blind_canary.py --provider-readback` enables this provider-readback mode. It sets provider storage only for the bounded public/synthetic canary and fails closed before invocation if the blind pack does not satisfy the storage-classification gate. Hidden scoring/control material remains outside this CLI and must be evaluated separately.

## Maturity boundary

This source/test contract does not prove an OpenAI API call occurred. Provider execution, provider response readback and model-resource/configuration readback still require an already-authorised runtime and non-secret credential binding. Hidden scoring and materially independent replication remain separate maturity gates.
