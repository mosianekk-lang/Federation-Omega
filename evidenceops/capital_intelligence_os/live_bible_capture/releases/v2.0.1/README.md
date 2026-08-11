# Live Bible Capture Fabric v2.0.1

This release promotes the tested Live Bible v2 package through a fresh branch based on current `main`.

## Verified fruit

- 18 source tests passed.
- 18 clean-extraction tests passed.
- SQLite `quick_check` returned `ok`.
- Installed CLI `init`, `ingest` and `verify` canaries passed.
- The source manifest contains 17 exact file entries.
- Authority remains A1 reversible-internal with zero external effects.

## Distribution

Binary distribution is stored in the governed user Library rather than committed to this source repository.

```text
Release ZIP SHA-256: 3ca119ebb0c86b2b9934f2cb63a5b676b85ef8a121ce9cae064eccd466811942
Source ZIP SHA-256:  7bbaced5481303e236f8b72bef76f9fecee0f5b82ca2eac107587d3375761336
Wheel SHA-256:       586411ce2aafd6967bbd195137ddf7e08f8c92d6c076bf1b3ae08d5754824667
Manifest SHA-256:    71ae0de6321fd628e64b0bdc6a74223c3099ae5af1eb67967a5907a99989fa71
```

## Truth boundary

The browser adapter is implemented but not installed. It is opt-in, targets only messages visible in the user's own ChatGPT tab, and posts to a local loopback receiver. The release does not read cookies or authentication tokens and does not claim hidden, future or universal conversation access.

The external hourly connector automation remains the selected between-turn reconciliation route. Runtime state and provider receipts remain outside the source repository.
