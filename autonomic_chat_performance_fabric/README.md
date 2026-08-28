# Federation Autonomic Chat Performance Fabric v1

Shadow-mode performance foundation for ChatGPT and future conversational surfaces.

## Guarantees

- delta-only capture; no normal-path full transcript replay
- content-addressed, append-only event chains
- authority, privacy, health and zero-cost route gates
- bounded context compilation
- streaming deferral, payload/time budgets and circuit breaking
- no live browser mutation or deployment in this release

## Test

```bash
python -m unittest autonomic_chat_performance_fabric.test_fabric -v
node autonomic_chat_performance_fabric/test_sentinel.js
```

## Deployment gate

The package remains shadow-only until same-workload browser benchmarks, failure tests,
rollback, provider readback, repeated real-chat success and soak prove superiority.

## Rollback

Do not merge or activate the branch. Abandoning the isolated branch restores the
pre-build state because current `main` and the live browser remain unchanged.
