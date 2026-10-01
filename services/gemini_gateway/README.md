# SOVARA Gemini Gateway

Private Cloud Run gateway for provider-native Gemini execution through Google Vertex AI using the Cloud Run runtime service account via Application Default Credentials (ADC).

## Canonical identity

The canonical project is `sov-hybrid-suite` (`257649435135`). The canonical runtime identity for this deployment line is:

`superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`

The gateway does not accept API keys or service-account keys. Runtime OAuth credentials are obtained only from the Cloud Run metadata server and the service fails closed if `EXPECTED_RUNTIME_SERVICE_ACCOUNT` does not match the metadata identity.

## Private canary contract

The bounded private canary path is:

1. authenticate the already-trusted GitHub workflow through repository-scoped WIF;
2. independently verify `FEDOMEGA-GEMINI-ADC-VERIFIED`;
3. build the gateway container from the exact admitted source SHA;
4. push it to the existing `federation-omega` Artifact Registry repository;
5. resolve and preserve the immutable image digest;
6. deploy a private Cloud Run revision as `superior-logic-runtime` with `--no-traffic` and a revision tag;
7. read back the exact revision, runtime identity, image digest and traffic allocation;
8. invoke the tagged revision with an authenticated identity token;
9. require `/health` and `/ready` identity readback;
10. require the V1 nonce-bound `/v1/handshake` over `gemini-2.5-flash` as rollback proof;
11. require the V2 stateless `/v2/interactions-handshake` over `gemini-3.8-flash`, with `store=false`, a completed interaction ID/status, usage metadata and exact semantic nonce;
12. emit one redacted receipt binding both provider proofs to the same immutable zero-traffic revision;
13. leave production traffic at 0% unless a separate promotion action is explicitly admitted.

Cloud Run revision tags allow direct testing of a revision that has no production traffic allocation. The deployment executor must still verify the provider's actual traffic state after deployment; command flags alone are not treated as proof.

## Truth boundary

Source/CI success is not provider proof. A successful `gcloud run deploy` command is not completion. `FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED` requires provider-native deployment readback plus both V1 generateContent rollback proof and V2 Gemini 3.8 Interactions semantic proof from the same deployed private revision. Interactions proof is stateless and does not grant Live, Search, Deep Research, File Search, MCP, external-effect, champion, owner-value or production-serving maturity.
