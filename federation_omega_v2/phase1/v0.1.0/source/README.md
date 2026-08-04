# Federation Omega v2.0 Core — Phase 1

This bounded Phase-1 slice implements:

1. an append-only, hash-chained SQLite federation event store;
2. deterministic current-state projections;
3. a fail-closed intent-to-mission compiler;
4. a canonical mission/entity query API;
5. restart-safe, idempotent command-line operations.

Authority is A1 reversible-internal. The package does not send messages, mutate
credentials, file legal material, place financial orders, or create external
provider effects.

## Commands

```bash
federation-omega-v2 init --db state.sqlite
federation-omega-v2 append --db state.sqlite --event event.json
federation-omega-v2 compile --objective "Build a verified internal bundle"
federation-omega-v2 query --db state.sqlite --entity SYS-FEDERATION-OMEGA
federation-omega-v2 verify --db state.sqlite
```
