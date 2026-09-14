# Security

- Snapshot secrets are supplied only through `CFBE_SNAPSHOT_KEY`; the package never persists them.
- HMAC comparison uses constant-time `hmac.compare_digest`.
- SQLite operations use parameters and `BEGIN IMMEDIATE`; no SQL is built from user values.
- The stream guard quarantines declared secret exposure and raw payload serialization.
- The context capsule emits an omission manifest and does not silently include unknown sections.
- No network, provider, scheduler, email, IAM, billing or deployment operation exists in this package.
- HMAC is symmetric: production integration should bind key rotation, secret storage and producer identity through the authorized runtime.
