# Live Bible Capture Fabric v2.0 Architecture

```text
CURRENT CHAT TURN ───────────────┐
CHAT EXPORT ─────────────────────┤
BROWSER VISIBLE-DOM ADAPTER ─────┤
PROVIDER WEBHOOK / SCHEDULE ─────┤
OFFLINE OUTBOX ──────────────────┘
                ↓
SOURCE ADAPTER CONTRACT
                ↓
VALIDATION · PRIVACY · SECRET REDACTION
                ↓
DETERMINISTIC ID · IDEMPOTENCY · SEQUENCE/GAP CONTROL
                ↓
APPEND-ONLY SQLITE EVENT STORE + HASH CHAIN
                ↓
LOCAL NARRATIVE · JSONL LEDGER · CURRENT STATE
                ↓
SELECTIVE P2-SAFE DELTA
                ↓
CORPUS REGISTRY · MASTER POINTER · MERGE RECEIPT
```

## Handling future and between-turn work

The fabric separates four concepts that were previously easy to conflate:

- **Future-turn capture:** the assistant appends the turn during the response in which it is processed.
- **Between-turn provider capture:** an external worker can capture events only from a real provider source such as a webhook, Drive folder, GitHub event or browser adapter.
- **Browser capture:** an installed extension can observe visible messages in the user's browser and queue them while the assistant is not responding.
- **Invisible universal capture:** prohibited as a claim unless an independently verified source API supplies the messages.

## Recovery

The browser extension keeps an offline queue. The receiver is idempotent. The event store identifies gaps, accepts late messages, preserves out-of-order status, and regenerates all projections from the event ledger.
