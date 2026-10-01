# SELF_HOSTING_RD_OBSERVATION_ADAPTER_V1

## Purpose

F306 binds Self-Hosting R&D to the existing CFBE prospective observation and passive collector machinery. It does not create another watcher, scheduler, evidence database, benchmark engine, or value court.

Two ten-slot cohorts are generated at the current source epoch, giving twenty prospective slots. This preserves the admitted CFBE ten-slot cohort contract while supporting the Self-Hosting R&D matched-evaluation floor and the later twenty-real-pair promotion floor.

## Evidence identity

A collector pair has one common observation/source epoch. The adapter additionally proof-binds a separate `arm_source_head_sha` for the incumbent and challenger inside each trusted raw observation. This lets F305 evaluate true source-specific arms without weakening the passive collector's currentness contract.

Each real observation also carries exact task/input/environment identity and measured engineering metrics.

## Truth boundary

The adapter does not measure or infer metrics.

Synthetic, shadow and replayed missions/observations are rejected.

A source adapter is not a deployed collector. An empty cohort is not evidence. A pair-ready collector record is not matched-evaluation proof. Matched evaluation is not owner-value proof, and owner-value proof is not independent Judge approval.

The runtime binding should reuse existing governed mission/observation surfaces and trusted evidence receipts; source admission alone must not be relabeled as prospective operational evidence.
