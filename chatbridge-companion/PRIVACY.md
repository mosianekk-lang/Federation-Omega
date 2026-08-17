# ChatBridge Companion Privacy Contract

## Data accessed

The extension reads conversation text, visible role metadata, visible message identifiers,
visible attachment links, page title, URL and visible terminal warnings from supported
ChatGPT pages.

It does not claim access to hidden model reasoning, deleted messages, provider-internal
telemetry, other browser origins or conversations that are not rendered in the active page.

## Storage

- Full capture envelopes are written to extension-owned IndexedDB.
- The latest compact handoff capsule is held in browser session storage.
- A transcript-free or bounded operational summary may be held in extension local storage.
- Connector credentials are held only in session storage or enterprise managed storage.

## Optional transmission

Provider transmission is disabled by default. When explicitly enabled, the user grants the
specific connector origin and the extension sends capture envelopes to the configured
ChatBridge endpoint. The connector must return a machine-readable receipt.

## Matter walls

Legal, medical, employment, family, financial and other restricted conversation content
must stay within the applicable governed matter boundary. Global operational learning may
receive only de-identified patterns, metrics, hashes and evidence pointers.

## Completeness boundary

Rendered DOM capture may be incomplete because the product can virtualize or unload older
turns. The browser path is therefore bounded unless a test-only completeness assertion is
explicitly enabled and separately accepted by a controlled adapter. Production exactness
requires stronger independent path and stream proof.
