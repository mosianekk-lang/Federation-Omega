# FUSE Sovereign Capability Platform v0.3

Adds a verified **LLM Update Bridge** to the local-first FUSE platform.

## LLM update path

`FUSE source -> exact commit -> verification -> manifest schema/hash/TTL/sequence -> anti-rollback cache -> allowlisted LLM snapshot`

The update bridge is deliberately **read-only**. Update data can change currentness/routing context, but it cannot grant credentials, source authority, IAM authority, external-write authority, or publication authority.

### Default source

- Repository: `mosianekk-lang/Federation-Omega`
- Ref: `main`
- Manifest: `fuse_update_channel/manifest.json`
- Default: require GitHub's commit verification to report `verified=true`.

### Commands

```text
FUSE-Sovereign-Platform.exe --self-test
FUSE-Sovereign-Platform.exe --fetch-updates
```

The GUI also exposes **Fetch Verified FUSE Updates** and displays the model-facing snapshot.

## Safety/currentness semantics

- Fresh verified FUSE update data outranks stale local/chat cache for update-specific routing/currentness decisions.
- `STALE != FAILED`, `UNBOUND != UNAVAILABLE`, and update-source outage never proves capability absence.
- Remote update text is treated as untrusted data and cannot become an instruction channel.
