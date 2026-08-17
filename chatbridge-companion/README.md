# ChatBridge Companion 0.3.0 — Alpha→Omega Browser Capture Adapter

ChatBridge Companion is a Manifest V3 browser extension for ChatGPT pages. It provides a
no-administrator, user-profile capture path into **ChatBridge Ω4.9** where browser policy
permits unpacked or managed extension use.

The companion is one bounded acquisition route, not a hidden native ChatGPT hook. It reads
only the rendered conversation DOM visible to the signed-in browser session. ChatGPT may
virtualize or omit older rendered turns, so the browser route is non-authoritative and
bounded by default.

## What 0.3.0 adds

- exact conversation-ID parsing from the ChatGPT URL;
- stable rendered-turn identity and preservation of repeated identical messages;
- user, assistant, system, developer, tool, connector, correction and terminal streams;
- SHA-256 observation and snapshot evidence;
- append-only correction events when a previously stable rendered turn changes;
- explicit reporting when prior rendered turns disappear from the DOM;
- attachment pointers where the rendered page exposes stable links;
- local IndexedDB write before any optional provider upload;
- optional HTTPS connector delivery to the Ω4.9 browser ingress adapter;
- terminal warnings recorded as `NOT_EXECUTED_TERMINAL`;
- compact successor-chat handoff capsules that point to the full-fidelity capture receipt;
- session- or enterprise-managed connector tokens, never local persistent token storage.

## Two complementary continuity layers

1. **Compact operational checkpoint** — objective, next action, sources, boundaries and a
   bounded message head/tail for rapid successor-chat resumption.
2. **Alpha→Omega / FFCL event lineage** — every rendered event delivered to the connector,
   with exact identity, streams, hashes, correction history and provider receipt.

Neither substitutes for the other.

## Local-only mode

`autoUpload` is off by default. Captures are written to extension-owned IndexedDB and the
latest bounded summary is stored in extension local storage. This is durable within the
browser profile but is not independently recoverable if the profile is deleted, reset or
blocked by enterprise policy.

## Connector mode

When the user explicitly enables upload and grants the exact connector origin, the service
worker sends a JSON envelope to:

```text
POST /v1/chatbridge/alpha-omega/capture
```

The corresponding Python ingress is:

```python
from bubbles.chatbridge_omega4.browser_companion_adapter import (
    ingest_browser_companion_capture,
)

result = ingest_browser_companion_capture(runtime, request_json)
```

The adapter verifies the browser envelope, registers a `RENDERED_DOM` capture path, submits
observations to ChatBridge Ω4.9 and returns a receipt without echoing raw transcript content.

## Security and privacy

- Permissions are limited to `storage`, `tabs`, ChatGPT hosts and an explicitly requested
  optional connector origin.
- No `nativeMessaging`, `debugger`, `management` or blocking web-request permission.
- Connector tokens live only in browser session storage or enterprise managed storage.
- Provider upload uses HTTPS except for localhost development.
- Full rendered transcript content remains governed local data and must not be copied into
  global Federation learning tables.
- A valid hash proves record integrity, not factual truth.

## Installation truth boundary

Source and tests do not prove that the extension is installed, enabled, policy-allowed,
bound to a signed-in ChatGPT session, intercepting a live terminal warning, or delivering
provider receipts. Those states require separate browser/provider readback.

Current maturity labels must remain separate:

```text
SOURCE_BUILT
DETERMINISTIC_TESTED
GOVERNED_MERGED
BROWSER_INSTALLED
SIGNED_IN_SESSION_BOUND
LIVE_CAPTURE_OBSERVED
PROVIDER_RECEIPT_READ_BACK
SUCCESSOR_RESTORE_ACCEPTED
```

Do not skip states.

## Tests

```bash
npm check
```

The suite checks rendered capture, exact identity, duplicate preservation, correction
append semantics, terminal execution boundaries, local-before-provider durability,
permission minimisation and read-only enterprise readiness assessment.
