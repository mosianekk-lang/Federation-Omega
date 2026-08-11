# Phase 3 architecture

```text
REGISTERED MATTER NODE
  -> CONTROL-METADATA SNAPSHOT
  -> CASE-WALL VALIDATION
  -> SOURCE-IDENTITY IMPORT
  -> MODISA AUTHORITY / PREVENTION GATE
  -> SOL 6.1 HASH-CHAINED STAGES
  -> EVIDENCEOPS CONTROL COMPARISON
  -> CONFLICT QUARANTINE
  -> OWNER REVIEW BRIEF
  -> RESTART / IDEMPOTENCY / ROLLBACK PROOF
```

The adapter is deliberately read-only with respect to real evidence. It imports control metadata and references only. Existing EvidenceOps findings remain authoritative until a separately verified source-level process changes them. Any overclaim, route contamination or readiness mismatch is quarantined instead of silently promoted.
