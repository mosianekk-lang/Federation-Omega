# Provider Authority Attachment Truth Boundary

- Source code does not create Google Cloud or OpenAI authority.
- Owner intent does not bypass provider authentication.
- The Google attachment tool defaults to plan or verification mode.
- Service enablement requires an exact environment confirmation and a provider-authenticated account matching the expected project.
- The metadata probe uses Secret Manager `describe` only and never retrieves a secret version payload.
- No service-account JSON key is created or accepted.
- No IAM role is granted by this release.
- No Cloud Run deployment, traffic change or provider canary occurs.
- A capability handle may be issued only after a provider-native redacted receipt passes validation.
- A read-only handle is capped at 600 seconds and must be expired or revoked.
- Existing OpenAI key deletion remains an official provider-account action after dependency migration.
- Key values, suffixes, hashes and fingerprints are prohibited from receipts.
