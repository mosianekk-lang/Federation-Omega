# Capital Intelligence OS — Architecture v0.3

## Evidence/data flow

`PUBLIC MARKET PROVIDER / EVIDENCEOPS TRADING RESEARCH → PublicMarketEvidenceAdapter → MarketTruthGate → MarketTwin / Market Intelligence Service → ProofGraph / M&A Analysis`

There is **no reverse private-M&A-to-trading path**.

Private deal data, clean-team material, potential MNPI, restricted, privileged and unknown information remain quarantined from market/trading pathways. Restricted issuers/securities deny market-facing actions even if the immediate observation is public.

Durable core flow remains:
`EVENT → TENANT/DOMAIN CHECK → TRANSACTION → PROOFGRAPH → CONTRADICTION/IMPACT → DETERMINISTIC ENGINES → ATTENTION → RESTRICTED-LIST/AUTHORITY GUARD → SAFE A0/A1 INTERNAL ACTION OR HUMAN GATE → HASH-LINKED LEARNING → IDEMPOTENT RECEIPT`.

The public repository is the source/admission plane, not the commercial execution plane. Provider runtime deployment is a separate maturity gate.
