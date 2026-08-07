# Capital Intelligence OS — Architecture v0.4

`LOOPBACK HTTP → AUTH/TENANT CONTEXT → DEFAULT-DENY ROUTE POLICY → DURABLE AUTOPILOT → PROOFGRAPH / MARKET / M&A ENGINES → HASH-CHAINED AUDIT → IDEMPOTENT RECEIPT`

Only A0/A1 internal event ingestion and verification surfaces are exposed in the local canary. Consequential route families do not exist in the API surface.

SQLite remains the reference transactional adapter. v0.4 proves atomic writes, request-bound idempotency, restart/replay, backup `quick_check`, and restoration of tenant state digest. Production storage must separately prove HA, encryption, migrations, retention and DR.

Market flow remains one way: PUBLIC market source → adapter → MarketTruthGate → analysis. There is no private-M&A-to-trading path.

The local runtime binds only to loopback and uses an ephemeral in-process bearer secret; that is appropriate for qualification, not a production authentication claim.
