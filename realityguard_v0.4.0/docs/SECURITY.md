# Security and threat model

Threats addressed: false completion, state inflation, partial-scope totality, stale proof, self-sealing verification, false ownership, capability/authority collapse, prompt-as-runtime claims, UI/semantic mismatch, capability dilution, duplicate-system bloat and avoidable user burden.

Controls: strict enums and input validation; minimum evidence grades per lifecycle state; current/passed evidence checks; independent or semantic observation for runtime states; owner-only acceptance; deterministic correlation and decision IDs; secret redaction; fail-closed verdicts; authority/cost/effect filters; canonical manifest-hash binding; explicit supersession; semantic capability deduplication; exact gap scoping; lifecycle/source-gap separation; atomic learning publication; and promotion-state ceilings.

Out of scope in this build: browser interception, ChatGPT DOM modification, provider authentication, cloud deployment, automatic transcript ingestion and autonomous background learning. No credentials are required or stored. The Federation manifest is source provenance, not a credential, import or live service connection.
