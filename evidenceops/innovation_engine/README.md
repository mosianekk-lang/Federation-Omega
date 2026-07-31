# EvidenceOps Innovation Engine

Persistent, proof-gated registry for EvidenceOps research, prototypes, deployments, live monitoring, maintenance and retirement.

## Operational rule

New ideas create or update lanes; they do not silently terminate active work. Every transition records evidence, a timestamp and a chained receipt hash.

## Current maturity

`PROTOTYPE_RUNTIME` — persistent SQLite registry and deterministic transition gates are implemented on the `ipep-platform-foundation` branch. Production promotion still requires live runtime deployment, durable backup and operational monitoring.

## Core files

- `registry.py` — persistent innovation/lane registry and proof-gated transitions.
- `live_lane_registry.json` — current reconstructed EvidenceOps lanes.
- `tests/test_innovation_engine_registry.py` — deterministic transition and receipt tests.

## Proof gates

- `PILOT_APPROVED` requires a hypothesis, metrics, bounded test evidence and rollback plan.
- `DEPLOYMENT_APPROVED` requires pilot evidence, privacy/security review, maintenance owner and tested rollback.
- `LIVE_FULL` requires passing limited-live metrics, active monitoring and no unresolved critical defect.

A record in the registry is evidence of state recording, not by itself proof that external execution occurred.
