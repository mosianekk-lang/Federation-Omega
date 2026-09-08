# Security notes

- Treat the mobile client as untrusted.
- Never put provider keys, Cloud Run control tokens, service-account keys, KDV credentials or signing secrets in mobile source or `EXPO_PUBLIC_*` variables.
- `/v1/session` is unusable until a real identity verifier and server-side session signer are bound.
- `CONFIGURED` provider state is descriptive only and cannot make a provider routing-eligible.
- Consequential effects are held before the injected Federation executor is called.
- The gateway does not proxy the privileged `federation-omega-operator /execute` endpoint.
- Provider and source payload eligibility must consider data classification in addition to runtime health.
