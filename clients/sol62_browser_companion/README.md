# FUSE Sol 6.2 Browser Carrier Companion

This is a FUSE-owned, detachable browser carrier and scoped browser-control client for the SOL 6.2 runtime.

## Boundary

It does **not** inject a runtime into ChatGPT, bypass ChatGPT permissions, automate provider Retry, evade policy, or treat the ChatGPT conversation as canonical state. It observes carrier liveness and can execute typed, origin-bounded browser commands from an authenticated SOL 6.2 runtime. Website-state commands require a separately consumed action-bound authority lease before execution.

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


## Typed browser control

The companion can execute a bounded command vocabulary received from the local SOL 6.2 Browser Control Plane:

- read/list ChatGPT tabs;
- create/open/activate/close/reload ChatGPT tabs;
- browser history back/forward;
- navigate only to HTTPS \`chatgpt.com\`;
- produce accessibility/DOM semantic snapshots;
- focus or scroll semantic targets;
- click or fill semantic targets only after runtime authority preflight.

The extension does not accept arbitrary JavaScript, selectors, eval strings, or cross-origin navigation commands. Semantic targets are resolved from stable identifiers, role, accessible name, text, href and ambiguity thresholds.

A mutating command is not considered verified merely because a Chrome API call returned. The command must produce semantic readback, and website-state effects require exact FDOF/SOL authority consumption before the extension receives \`authority_bound=true\`.

## Browser-control truth boundary

\`\`\`
CONTROL_SOURCE
!= EXTENSION_INSTALLED
!= AUTHENTICATED_RUNTIME_BINDING
!= COMMAND_LEASED
!= ACTION_AUTHORIZED
!= ACTION_OBSERVED
!= SEMANTIC_READBACK_VERIFIED
!= OWNER_VALUE_VERIFIED
\`\`\`

ChatGPT remains a replaceable browser/provider surface. Mission identity, authority, effect truth and durable state remain outside the page.
