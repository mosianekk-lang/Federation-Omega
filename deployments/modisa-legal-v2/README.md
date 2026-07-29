# MODISA–EvidenceOps Sovereign Legal Intelligence OS v2 deployment payload

This branch stores a sealed, evidence-free deployment package for MODISA V2. It does not contain API keys, local JWT/HMAC/AES secrets, legal evidence, emails or runtime databases.

## Package

- Version: `2.0.1-deployment`
- Archive: reconstructed by concatenating `archive.parts/part-*`, base64-decoding the result and verifying the SHA-256 file.
- Deterministic qualification: 27/27 Python tests and 20/20 behavioural cases passed in the 29 July 2026 session runtime.
- Live Agents result: blocked before model execution because the restricted host lacked `openai-agents` and did not receive the API key created through the ChatGPT secure setup flow.

The CI workflow reconstructs the archive, verifies its checksum, installs the official dependencies from PyPI, runs tests and evaluations, starts the HTTP service, and performs a live smoke only when `OPENAI_API_KEY` is configured as a repository secret.

`main` was not modified by creating this deployment branch.
