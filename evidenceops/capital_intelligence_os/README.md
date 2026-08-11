# EvidenceOps Capital Intelligence OS — v1.0.0-rc3 Provider Canary Ready

`rc3` adds a harmless A1 provider canary on top of the merged MVP candidate and production qualification gate.

The canary is intended to run only inside an authorised private runtime. It validates exact source identity, the already-merged rc2 release verifier, persistent database health, event persistence after reopen, stable tenant-state digest, learning-chain integrity, and the continuing denial of live orders and private-M&A→public-market export.

Focused canary harness: **5/5 PASS**.

The canary receipt is digestible and non-secret. Runtime receipts must be stored in an immutable private evidence plane or provider artifact—not committed into public canonical source.

A canary pass is **not** full production verification. Enterprise IdP/MFA, encryption/KMS, malware/DLP, production VDR controls, market-data entitlement, observability, vulnerability/pentest and DR still require provider-native evidence through the rc2 production gate.

Current connected state: `PROVIDER_CANARY_READY`; no authorised private runtime is connected, so no provider canary execution is claimed.
