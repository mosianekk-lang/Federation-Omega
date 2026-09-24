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
