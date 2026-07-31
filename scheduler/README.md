# EvidenceOps External Scheduler

This directory is the external scheduling control plane for EvidenceOps work.

## Boundary

- GitHub schedules and tracks work.
- Google Cloud, Apps Script, local sovereign runners, and provider adapters perform authorised execution.
- ChatGPT is a reporting and design surface, not the primary scheduler.
- No credentials, source evidence, private transcripts, personal data, or case-specific confidential content may be stored here.

## Cadence

- Hourly: lane dependency and blocker watch
- Every 6 hours: Kimmie Seed maturity and nutrient assessment
- Daily at 08:00 Africa/Johannesburg: innovation scan and prioritisation
- Daily at 22:00 Africa/Johannesburg: continuity checkpoint and manifest verification
- Monday at 07:00 Africa/Johannesburg: connector conformance and maintenance review

Scheduled workflows run in UTC and translate the above South African times accordingly.

## Proof states

The scheduler may mark work only as PLANNED, READY, BLOCKED, DISPATCHED, VERIFIED, or COMPLETE. `DISPATCHED` is not execution proof. Completion requires a readback or proof receipt from the actual execution environment.
