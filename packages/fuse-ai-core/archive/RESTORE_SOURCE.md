# FUSE-AI Core v0.1 — exact source archive

This branch preserves the clean, proven FUSE-AI Core v0.1 source archive as four ordered Base64 parts:

1. `FUSE-AI-Core-v0.1-source.part01.b64`
2. `FUSE-AI-Core-v0.1-source.part02.b64`
3. `FUSE-AI-Core-v0.1-source.part03.b64`
4. `FUSE-AI-Core-v0.1-source.part04.b64`

Concatenate them in lexical order, Base64-decode the result, and write the bytes as `FUSE-AI-Core-v0.1-clean-source.zip`.

Expected SHA-256:

`8cd5e0427a6cf9a0f31b67c952970bcbfa279c82996896a57b503e7954138028`

The archive contains 28 source/test/documentation/launcher files and excludes runtime state, database files, token files, build directories, caches, and the wheel artifact.

Proof state at capture:

- Unit/integration court: **16/16 PASS**
- Authenticated loopback daemon smoke: **PASS**
- Offline chat smoke through `fuse.deterministic`: **PASS**
- Modisa exact-request, one-use lease and tamper/replay tests: **PASS**
- OpenAI-compatible provider contract with runtime-only secret injection: **PASS**
- `main` is intentionally untouched; this is an isolated formation branch.

The built-in deterministic provider is a proof engine, not a frontier language model. The next build layer is FUSE-AI v0.2 local-model/runtime intelligence plus streaming and semantic memory.