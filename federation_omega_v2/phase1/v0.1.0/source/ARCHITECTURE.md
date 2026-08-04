# Architecture

```text
OWNER INTENT
  -> DETERMINISTIC INTENT COMPILER
  -> MISSION CONTRACT
  -> AUTHORITY / PROOF / ROLLBACK GATES
  -> APPEND-ONLY EVENT STORE
  -> CURRENT-STATE PROJECTIONS
  -> CANONICAL QUERY API
  -> DOMAIN ADAPTERS
```

The event log is authoritative. Current state is derived and may be rebuilt.
Every event belongs to one entity and extends that entity's SHA-256 hash chain.
Duplicate event IDs are idempotent only when the complete event body matches;
conflicting reuse fails closed.

The compiler produces a deterministic mission ID from normalized intent, success
criteria, authority, deadline, budget, constraints and source requirements.
It never expands authority beyond the supplied ceiling.
