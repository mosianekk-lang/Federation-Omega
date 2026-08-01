# EvidenceOps Public Repository Boundary

This repository is public. It may contain reusable, non-sensitive architecture, source code, schemas, tests, documentation and redacted proof metadata.

It must not contain:

- live Google Drive, Docs, Sheets, Slides, Gmail or folder identifiers;
- private canonical-backend identifiers;
- raw execution receipts that reveal private targets;
- email message IDs;
- API keys, OAuth tokens, private keys, passwords or connection strings;
- case evidence, transcripts, personal records or confidential operational data;
- production service-account identities or unrestricted authority maps;
- private Bible content or private Mission Intelligence Packets.

## Required pattern

```text
PUBLIC REPOSITORY
→ REDACTED CONTRACTS, TEMPLATES AND CODE
→ PRIVATE RUNTIME CONFIGURATION
→ SECURE CAPABILITY BROKER
→ PRIVATE CANONICAL BACKEND
→ REDACTED PUBLIC RECEIPT
```

Public files must use placeholders such as:

- `PRIVATE_RUNTIME_CONFIG`
- `PRIVATE_RECEIPT_REFERENCE`
- `PRIVATE_IN_PLACE_CANONICAL_BRIDGE`

Live identifiers belong in the private EvidenceOps control plane, managed secret/configuration stores, or private runtime environment variables.

## History boundary

Removing a value from the current branch does not erase it from Git history. Exposed historical identifiers must be treated as retired and replaced with rotated private identifiers. Any credential exposure requires immediate revocation and rotation.

## Release gate

Every push and pull request must pass `public_repository_leak_guard.py`. A failing guard blocks release until the sensitive value is removed or replaced by an approved placeholder.
