# Sol + EvidenceOps Autonomous Proof-Carrying Runtime v7.1.0

This directory carries a chunked, base64-encoded copy of the exact verified release archive. The pull-request workflow reconstructs the ZIP, verifies archive, manifest and wheel hashes, executes the complete source test suite, performs clean-package acceptance, runs non-default EvidenceOps and paper-trading adopter canaries, starts the installed HTTP service, reads back health and programme state, and uploads a provider-hosted proof package.

The hosted proof is scoped. It does not establish a long-running Temporal/NATS/OPA/PostgreSQL control plane, a legal filing, external communication authority, provider account state, live exchange execution or sustained real-world value.
