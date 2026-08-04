# Federation Live Bible Capture Fabric v2.0

This release evolves the Local Live Bible from active-turn-only persistence into a source-agnostic capture fabric.

## Implemented capture routes

- **Turn connector** — active and verified in authorised chat turns.
- **Chat export** — deterministic catch-up import with deduplication.
- **Browser-visible adapter** — Chrome/Edge extension captures messages visible in the user's own ChatGPT tab and queues them to a loopback receiver.
- **Provider webhook / schedule contract** — accepts external events only when a real source adapter exists.
- **Offline outbox** — survives receiver downtime and replays idempotently.

## Reliability and safety

- append-only SQLite WAL event store;
- deterministic event IDs and per-conversation hash chains;
- append-order chain verification even when late messages repair sequence gaps;
- source-equivalent duplicate replay detection;
- sequence-gap detection and late-gap repair;
- secret-shaped content redaction before persistence;
- P0-P3 privacy and case-wall metadata;
- loopback-only receiver with a pairing token;
- Markdown, JSONL and current-state projections;
- no cloud upload or external effect by default.

## Exact release

```text
ZIP SHA-256: 7b4fe8e89db7b22db712233a6ce518d04a3b4d9d249934a926522819db869572
Manifest SHA-256: 81f5cdb33e5d2e05fd2cd8193edaffd5bc3530a018e8bc9fd5d301f6f3102af9
Wheel SHA-256: 2939740b27483aaeabe0fba9454a8b46c50be3df95d931b4962a6c747bf19de6
Source tests: 18 passed
Clean extraction tests: 18 passed
Database quick_check: ok
```

## Maturity boundary

The fabric can continuously process future or between-turn events **when a configured source adapter supplies them**. The included browser extension is implemented but cannot install itself into the user's browser. There is no claim of invisible universal access to ChatGPT conversations.
