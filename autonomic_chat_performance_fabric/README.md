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
node autonomic_chat_performance_fabric/test_native_edge_chatgpt_diagnostic.js
node autonomic_chat_performance_fabric/edge_extension/test_edge_extension.js
node autonomic_chat_performance_fabric/edge_extension/permission_audit.js
node autonomic_chat_performance_fabric/benchmark_gate.js
node autonomic_chat_performance_fabric/benchmark.js
node autonomic_chat_performance_fabric/test_benchmark_v2.js
node autonomic_chat_performance_fabric/benchmark_v2.js
```

The deterministic benchmark is the CI admission gate. Wall-clock timing is an
informational synthetic receipt because shared runners are noisy and are not a
substitute for same-workload browser evidence. The v2 receipt uses balanced
matched samples and a paired-bootstrap 95% interval, binds the sentinel source
hash, and emits aggregate timing only. Its timing result remains informational;
only semantic, privacy, rollback, and receipt-contract assertions block CI.

## Browser canary

`browser_canary_config.json` is deliberately disabled. It limits observation to
one chat and 15 minutes, captures aggregate metrics without message text or raw
DOM persistence, and requires a separate Formation permit plus explicit operator
activation. `performance_sentinel.js` emits no message text, per-message IDs or
hashes; `aggregate_browser_probe.js` omits URLs, entry names and attribution and
caps long-task samples at 256. Rollback disconnects observation and clears all
in-memory state. This branch does not activate the canary.

`native_edge_chatgpt_diagnostic.js` is an injection-neutral adapter for an
authorized Microsoft Edge hook. It aggregates reload, hydration, lifecycle,
reconnect, memory-pressure and long-task measurements without reading message
content or returning raw URLs, entry names, attribution or memory byte values.
It fails closed unless the disabled configuration is explicitly enabled and
both Formation-permit and operator-activation evidence are supplied. No Edge
extension, host permission or native-messaging deployment is included here;
runtime state therefore remains `ADAPTER_REQUIRED`.

The `edge_extension` source builds an unsigned, unpacked Manifest V3 package
around the adapter. It has no automatic content script or mandatory host
access; managed storage is its only mandatory permission, while scripting and
the exact ChatGPT origin remain optional. Its enterprise deployment contract is
inactive and contains no identity, update URL, registry, MDM or force-install
mutation. CI audits these invariants and builds a hash-bound source receipt.

`route_mode_contract.js` keeps configured route mode (`ACTIVE` or `PASSIVE`)
separate from derived health (`HEALTHY`, `DEGRADED` or `OPEN`) and rejects enum
cross-contamination before deterministic route selection.

## Deployment gate

The package remains shadow-only until same-workload browser benchmarks, failure tests,
rollback, provider readback, repeated real-chat success and soak prove superiority.

## Rollback

Do not merge or activate the branch. Abandoning the isolated branch restores the
pre-build state because current `main` and the live browser remain unchanged.
