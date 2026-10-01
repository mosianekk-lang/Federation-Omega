# FUSE Sol 6.2 Browser Carrier Companion

This is a FUSE-owned, detachable browser carrier observer for the SOL 6.2 runtime.

## Boundary

It does **not** inject a runtime into ChatGPT, bypass ChatGPT permissions, automate Retry, evade policy, or treat the ChatGPT conversation as canonical state. It only observes carrier liveness and reports route-local UI failure to an authenticated SOL 6.2 runtime.

A failed ChatGPT conversation is therefore handled as:

```
CHATGPT_CONVERSATION_LOAD_FAILED
  -> mark carrier FAILED
  -> preserve mission identity/state
  -> elect healthy alternate carrier
  -> if effect may be in-flight: READBACK FIRST
  -> hydrate same mission on replacement
```

The opaque FUSE bearer token belongs in `chrome.storage.session`, not source, page DOM, URL, or persistent local storage.

Default development runtime is `http://127.0.0.1:8762`. Production packaging should replace host permissions with the exact FUSE runtime origin.

Truth boundary: extension source != installed extension != authenticated runtime binding != live browser failover verified.


## New-chat tab resilience

Some ChatGPT builds render **New chat** as an application control instead of a normal anchor. Chromium/Edge then has no link target, so its built-in context menu cannot offer **Open link in new tab**.

The companion treats this as a route-local browser capability gap rather than mission failure:

- capture-phase semantic target scoring uses accessible label, title, visible text, test-id, role and safe root-href signals instead of a single brittle selector;
- a persistent browser context-menu action, **FUSE — Open New Chat in New Tab**, is available on ChatGPT pages;
- Ctrl/Cmd-click and middle-click gain new-tab semantics when the target is a non-link New Chat control;
- if ChatGPT exposes a real anchor later, modified-click interception self-disables and native browser behavior wins;
- candidate URLs are constrained to HTTPS `chatgpt.com` and conversation/share URLs are collapsed to the new-chat root;
- duplicate openings inside a short idempotency window are suppressed;
- this capability opens a detachable client only; it grants no FUSE mission, provider, source, or effect authority.

Truth boundary: source implementation != installed extension != observed context-menu item != successful tab creation != FUSE mission hydration.
