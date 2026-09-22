# GitHub Surface Omega v2 — Security Posture

The candidate deliberately treats repository intelligence and execution authority as separate concerns.

A GitHub agent may inspect and recommend without becoming a writer. An OIDC-bearing workflow must be explicitly registered and serialized. Pull-request-target execution is zero-trust by default. Third-party Actions on changed workflows must be immutable commit-SHA references. Provider `main` prevention remains a separate GitHub ruleset gate. Release provenance remains a separate real-artifact attestation gate.

The resulting design follows fail-closed admission while preserving current source/runtime/value proof separation.
