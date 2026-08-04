# Federation Live Bible Capture Fabric v2.0

A source-agnostic, event-sourced, privacy-aware capture layer for Federation Omega's Local and Master Bibles.

## What this changes

The original Local Bible could capture material work during an authorised assistant turn. v2.0 preserves that route and adds the machinery needed to handle additional source modes:

1. **Turn-driven connector capture** — active now in authorised chats.
2. **Chat-export catch-up** — imports structured exports and deduplicates them.
3. **Browser-visible capture** — optional Chrome/Edge extension observes messages visible in the user's own ChatGPT tab and queues them to a loopback receiver.
4. **Provider webhook or scheduled reconciliation** — source adapters can submit events when a real provider feed exists.
5. **Offline outbox replay** — events survive receiver downtime and are replayed idempotently.

## Truth boundary

This software cannot manufacture access to a conversation source. It captures only events supplied by a configured adapter. The browser extension is opt-in, captures visible DOM messages only, sends only to `127.0.0.1`, and never reads cookies or authentication tokens. No cloud upload is enabled by default.

## Guarantees

- deterministic event IDs and idempotent replay;
- per-conversation hash chains;
- SQLite WAL persistence and `quick_check`;
- missing-sequence detection and late-gap resolution;
- append-only receipts and dead letters;
- secret-shaped content redaction before persistence;
- P0–P3 privacy tiers and case-wall metadata;
- loopback-only HTTP receiver with pairing token;
- JSONL, Markdown and current-state projections;
- explicit separation between local capture and selective Master promotion.

## Quick start

```bash
cd systems/live-bible-capture-fabric
python -m pip install -e .
live-bible-fabric init
live-bible-fabric pairing-code --show
live-bible-fabric serve
```

Then load `browser_extension/` as an unpacked extension in Chrome or Edge, paste the local pairing token, and enable capture. Browser installation and pairing are one-time client-controlled actions; the server and capture pipeline cannot install themselves into the browser.

## Import a chat export

```bash
live-bible-fabric import-export /path/to/chat.json --source-id chat-export-20260804
```

## Process an offline outbox

```bash
live-bible-fabric process-outbox /path/to/outbox
```

## Verify a conversation

```bash
live-bible-fabric verify CONVERSATION_ID
```

## Maturity states

- `TURN_CAPTURE_OPERATIONAL_VERIFIED` — active-turn connector writes and readback.
- `LOCAL_RECEIVER_TESTED` — loopback receiver and browser adapter tests pass.
- `CLIENT_ADAPTER_READY_NOT_INSTALLED` — extension package exists but is not installed in a browser.
- `PROVIDER_BACKGROUND_CAPTURE_HELD_SOURCE_ADAPTER` — no claim of invisible ChatGPT access without an actual source feed.

## Security

The receiver binds only to loopback. Pairing tokens are generated locally with mode `0600`. Raw provider credentials must never be placed in events. Secret-shaped strings are redacted and the event is flagged as quarantined.
