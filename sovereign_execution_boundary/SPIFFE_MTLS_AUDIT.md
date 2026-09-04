# SPIFFE/SPIRE mTLS gap audit

The prior `WorkloadIdentity.validate()` accepted every string beginning with a trust-domain prefix. It did not authenticate a certificate, validate a trust bundle, prove private-key possession, enforce the X.509-SVID URI SAN shape, or authorize an exact workload. A same-domain rogue path therefore passed.

`seb.spiffe_mtls` now builds a TLS 1.2+ context from an X.509-SVID, key and bundle materialized from a SPIFFE Workload API. TLS requires a CA-valid client certificate. The request boundary requires exactly one canonical URI-SAN SPIFFE ID and compares it to an explicit exact allowlist. Missing, malformed, multiple, foreign and same-domain rogue identities fail closed.

`proofs/prove_spiffe_mtls.py` exercises a real TLS handshake. Both clients chain to the same ephemeral CA; the intended SVID receives 204 and the rogue receives 403.

Production still needs hosted SPIRE registration (or equivalent Workload API), rotation-capable materialization such as `spiffe-helper`, socket/file permissions and provider-native readback. Rotation currently requires process restart. This is `IMPLEMENTED_HOST_PROOF`, not `DEPLOYED`.
