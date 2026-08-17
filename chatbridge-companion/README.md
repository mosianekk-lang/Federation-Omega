# ChatBridge Companion Ω4.9

Manifest V3 browser adapter for ChatGPT. It supplies the browser-rendered acquisition path to ChatBridge Ω4.9's Alpha→Omega multi-path/multi-stream conversation assurance.

## What it does

- binds the exact `/c/<conversation-id>` to an exact namespace hint;
- captures every rendered user/assistant message in DOM order;
- preserves message revisions append-only instead of silently overwriting them;
- records attachment/file pointers and whether they are required for context;
- stores a SHA-256 content hash, previous-event hash and event hash for every appended observation;
- maintains first/last rendered-message watermarks and explicit missing ranges;
- marks the source honestly as `RENDERED_DOM_ONLY_NOT_HIDDEN_NATIVE_EVENTS`;
- checkpoints on DOM changes, a timed write-ahead interval, tab hiding and the visible maximum-length warning;
- exports the governed local ledger as JSON with **Alt+Shift+E**;
- creates ordered successor replay packets and can deliver them automatically to a new ChatGPT chat;
- keeps terminal-visible intent separate from verified execution.

## Restore classification

A gap-free, hash-valid rendered transcript is `EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE`. It is not promoted to `EXACT_MULTIPATH_MULTISTREAM_RESTORE` until an independent provider/export/archive path corroborates the events and required streams. Missing sequences or required artifacts produce `BOUNDED_MULTIPATH_MULTISTREAM_RESTORE`.

## Local controls

- **Alt+Shift+B** — immediate write-ahead checkpoint.
- **Alt+Shift+E** — export the current conversation ledger.
- On the maximum-length banner, choose **Start successor via ChatBridge Ω4.9**.

The extension uses only:

- `storage` and `unlimitedStorage` for governed extension-local ledgers;
- `downloads` for an explicit user-requested JSON export; and
- `https://chatgpt.com/*` host access.

No remote telemetry endpoint is included. No secret, password or API key is collected.

## Development

```bash
cd chatbridge-companion
npm run check
```

Load the directory as an unpacked extension only where browser policy permits. Source readiness does not prove installation, signed-in session binding or provider-wide operation. Those states require a browser-native canary and readback.

## Proof boundary

The adapter captures the rendered browser surface it can observe. It cannot retroactively create old messages, read hidden model reasoning, guarantee visibility of hidden system/provider events, or prove the factual truth of statements inside the transcript. Record integrity, transcript completeness and substantive truth remain separate.
