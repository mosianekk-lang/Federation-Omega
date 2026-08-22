# Frontier knowledgebase repository

This directory is append-only at the snapshot and delta layers.

- `benchmark/index.json` points to the current immutable benchmark snapshot.
- `benchmark/snapshots/` stores content-addressed reports.
- `benchmark/deltas/` is created after the second material benchmark state.
- `benchmark/refresh-journal.ndjson` records material changes only.
- `source-observations/` is created by the network source watcher.

No-change refreshes intentionally write nothing. Source bodies are not copied; the watcher keeps normalized semantic digests and response metadata. Score promotion always requires semantic review, tests and Formation governance.
