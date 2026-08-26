# Formation specification

- Mission: `CFRE-PRIVATE-RUNTIME-RESOLUTION-20260825`
- Identity preserved: `federation-omega-operator`
- Authority ceiling: existing Google IAM only; no trust transfer
- Mutation path: authenticated operator revision; zero-cost `READ_GEMINI_VERTEX_CAPABILITY` first; exact-nonce `VERIFY_GEMINI_VERTEX_SEMANTIC` only after its environment and approval gates are open
- Safety: exact target/hashes, private service, immutable source object, bounded build polling, provider-native readback, rollback revision capture
- Stop conditions: authentication unavailable, hash mismatch, target drift, build failure, service readback mismatch, or secret disclosure
- Current maturity: source-restored implementation candidate until provider deployment, Vertex capability readback and exact-nonce semantic readback
