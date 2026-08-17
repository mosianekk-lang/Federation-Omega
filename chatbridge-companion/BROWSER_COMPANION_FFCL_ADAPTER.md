# Browser Companion → ChatBridge Ω4.9 Ingress

The browser emits `CHATBRIDGE-ALPHA-OMEGA-BROWSER-CAPTURE-1` envelopes. The Python ingress
performs the following bounded sequence:

```text
SCHEMA / SIZE / SECRET-FIELD CHECK
→ EXACT CONVERSATION + NAMESPACE + PATH IDENTITY
→ OBSERVATION PAYLOAD-HASH VERIFICATION
→ TERMINAL INTENT / EXECUTION CHECK
→ RENDERED_DOM PATH NORMALISATION
→ PATH REGISTRATION
→ MULTI-STREAM CAPTURE
→ RECONCILIATION
→ OPTIONAL TEST-ONLY STREAM EXPECTATION / SEAL
→ ASSESSMENT
→ REDACTED PROVIDER RECEIPT
```

Production rendered-DOM paths are always non-authoritative and capped as bounded evidence.
A browser checkbox cannot independently promote the route to native source completeness.
The adapter accepts that assertion only when deliberately created with
`allow_test_source_complete_claim=True` in a controlled canary.

The adapter does not implement HTTP authentication. The hosting App/API/MCP boundary must
authenticate the caller and pass only the parsed JSON body to the ingress function.
