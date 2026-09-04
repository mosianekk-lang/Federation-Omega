# Formation Specification

- Mission: `CFBE-SEB-REFERENCE-BUILD-20260904`
- Owner: Kim Kagiso Mosiane
- Objective: provide a local, reversible, provider-neutral execution boundary.
- Authority: A2 local build and qualification only.
- External effects: disabled.
- Credentials: prohibited from source, fixtures, logs and artifacts.
- Cost: zero new recurring cost.
- Stop switch: process termination, mission cancellation, policy denial or semantic quarantine.
- Promotion gate: representative provider-native canaries, zero unauthorized or duplicate effects, rollback test and exact readback.

Task lifecycle: `CREATED → QUEUED → PROCESSING → COMPLETED/FAILED`, with `CANCELLED`, `RETRIED`, `DEAD_LETTER`, `ROLLED_BACK` and `QUARANTINED` available as explicit states.

