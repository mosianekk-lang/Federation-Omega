# FUSE Astra+ Signal & Temporal Intelligence v0.1

This package adds **authorized signal intelligence and temporal semantics** to the Astra+ cognitive substrate. It does not create a new event bus, scheduler, Mission Bus, workflow engine or surveillance plane.

## Reuse boundary

Existing Federation/FKPF infrastructure remains canonical for mission ordering, knowledge deltas, watermarks, replay, FDOF/Mission Bus state, durable workflow and proof. This package adds semantic interpretation above those mechanisms:

- distinguish event time, observation time and processing/current time;
- model late/out-of-order/future-skewed events explicitly;
- track sequence gaps separately from event-time lateness;
- provide hybrid logical timestamps for causal ordering under imperfect clocks;
- preserve bitemporal truth: what was valid then vs what was known then;
- fuse independent signals without counting mirrors/reposts as independent corroboration;
- rank salience from severity, confidence, freshness, novelty and source diversity;
- distinguish explicit causation from correlation or temporal proximity;
- support deterministic change detection, deadline/expiry/staleness and event-time windows.

## Signal sources

The intended inputs are owner-authorized telemetry, traces, metrics, logs, events, messages, provider readbacks, system state and lawful public/open-source observations. This layer does not authorize covert interception, credential collection, or bypass of communications/privacy controls.

## Time model

FUSE treats time as typed data rather than one wall clock:

- `event_time`: when the occurrence happened;
- `observed_time`: when a source observed/reported it;
- `processing_time`: when FUSE processes it;
- `valid_time`: when a fact is true in the modeled world;
- `transaction_time`: when FUSE knew/recorded the fact;
- `deadline/expiry/freshness`: action and evidence time constraints;
- hybrid logical time: causal ordering aid when physical clocks disagree.

Watermarks are progress indicators, not assertions that late data is impossible. Late evidence is classified and governed rather than silently discarded.

## Canonical semantic capability targets

`SIGNAL.INGEST`, `SIGNAL.FUSION`, `SIGNAL.SALIENCE`, `SIGNAL.CORRELATION`, `SIGNAL.CHANGE`, `TIME.EVENT_MODEL`, `TIME.WATERMARK`, `TIME.HLC`, `TIME.BITEMPORAL`, `TIME.WINDOW`, `TIME.DEADLINE`, `TIME.FRESHNESS`.

## Proof boundary

The local v0.1 slice has deterministic unit coverage for source-independence/echo resistance, multi-source confidence, causation-vs-correlation, change detection, watermark/lateness, sequence gaps, future clock skew, hybrid logical clocks, bitemporal reconstruction, event-time windows and deadline/expiry/staleness separation. It does not prove production Flink/Temporal/NATS deployment or live provider signal ingestion.