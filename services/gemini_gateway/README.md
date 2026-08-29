# SOVARA Gemini Gateway

Private Cloud Run gateway for provider-native Gemini execution through Google Vertex AI using the Cloud Run runtime service account via Application Default Credentials (ADC).

## Canonical identity

The canonical project is `sov-hybrid-suite` (`257649435135`). The canonical runtime identity for this deployment line is:

`superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`

The gateway does not accept API keys or service-account keys. Runtime OAuth credentials are obtained only from the Cloud Run metadata server and the service fails closed if `EXPECTED_RUNTIME_SERVICE_ACCOUNT` does not match the metadata identity.

## Deployment contract

The bounded private canary path is:

1. authenticate the already-trusted GitHub workflow through repository-scoped WIF;
2. independently verify `FEDOMEGA-GEMINI-ADC-VERIFIED`;
3. build the gateway container from the exact admitted source SHA;
4. push it to the existing `federation-omega` Artifact Registry repository;
5. resolve and preserve the immutable image digest;
6. deploy a private Cloud Run revision as `superior-logic-runtime` with `--no-traffic`;
7. read back the exact revision, service identity and image digest;
8. invoke `/health` and `/ready` using an identity token;
9. invoke `/v1/handshake` with a run-bound semantic nonce and require a real Vertex `responseId`, model identity, usage metadata and exact nonce response;
10. emit a redacted provider receipt;
11. leave production traffic at 0% unless a separate promotion action is explicitly admitted.

## Truth boundary

Source/CI success is not provider proof. A Cloud Run deployment command is not completion. `FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED` requires provider-native deployment readback plus a live semantic Gemini handshake from the deployed private revision. Production serving is a separate state and is never inherited from canary success.
