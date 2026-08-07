# Capital Intelligence OS — Architecture v0.1

## Data/control flow

`SOURCE EVENT → CLASSIFY → PROOFGRAPH → CONTRADICTION/IMPACT → DETERMINISTIC ENGINES → ATTENTION COMPRESSION → AUTHORITY GUARD → SAFE INTERNAL ACTION OR HUMAN GATE → LEARNING LEDGER`

## Domain walls

- PUBLIC_MARKETS may supply PUBLIC evidence to PRIVATE_MNA analysis.
- PRIVATE_MNA information classified CONFIDENTIAL, CLEAN_TEAM, POTENTIALLY_MNPI, RESTRICTED, PRIVILEGED or UNKNOWN cannot feed a PUBLIC_MARKETS/trading pathway.
- No component inherits authority from another component.
- The default operating ceiling is A1 internal.

## Planned adapters

- Existing EvidenceOps Provenance Passport for canonical record/Merkle proofs.
- Existing EvidenceOps Algorithm Foundry for governed algorithm candidate generation/evolution.
- Existing Secure Capability Box for provider secret-reference and token boundaries.
- Existing heartbeat/learning fabrics for external append-only runtime telemetry.
- Existing trading/Market Truth subsystem as PUBLIC-only market evidence provider.

## Scale path

The in-memory stores are explicit ports, not the intended commercial persistence layer. Production adapters should use an event store plus a transactional database and graph/search projections, with tenant isolation, immutable audit, schema migration and disaster recovery. Those runtime choices require provider-specific proof before they can be called deployed.
