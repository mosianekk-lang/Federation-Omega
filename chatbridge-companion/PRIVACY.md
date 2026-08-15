# Privacy and security

- Scope: `https://chatgpt.com/*` only.
- Network: no external fetches and no API key.
- Full transcript capsule: browser session storage only.
- Durable local data: capsule ID, timestamps, route, title, and metrics only; no transcript.
- Transfer: bound to the newly created successor tab and consumed once.
- Authority: the extension cannot access inaccessible chats, connectors, Library, Drive, Gmail, or hidden model state.
- Failure behavior: it preserves ChatGPT's native Start new chat action and reports a local error without deleting the source chat.
- Windows readiness assessor: reads browser executable locations, this manifest and Edge/Chrome policy registry values only. It does not read chat content, credentials or browsing history; it changes no registry or browser setting.
