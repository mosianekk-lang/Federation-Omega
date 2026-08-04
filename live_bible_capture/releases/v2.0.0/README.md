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
- sequence-gap detection and late-gap repair;
- secret-shaped content redaction before persistence;
- P0-P3 privacy and case-wall metadata;
- loopback-only receiver with a pairing token;
- Markdown, JSONL and current-state projections;
- no cloud upload or external effect by default.

## Exact release

```text
ZIP SHA-256: a9690c24309b3b6ef463e1dea733833e35bd26f22547d29a8060e440910265c3
Manifest SHA-256: 681ecd6709e46f8eb420dd9dedabab001fb96d6cb5e79ce14fb615955957f7ab
Wheel SHA-256: 4bf70de9b0ac5e2e8ac5f39b563fca55a263f9f1b2c921496a2a2da3064a7e07
Source tests: 17 passed
Clean extraction tests: 17 passed
Database quick_check: ok
```

## Maturity boundary

The fabric can continuously process future or between-turn events **when a configured source adapter supplies them**. The included browser extension is implemented but cannot install itself into the user's browser. There is no claim of invisible universal access to ChatGPT conversations.
