# Provider Authority Attachment v1 Release Notes

This release adds a provider-proof intake and read-only capability-handle lifecycle for the final Google Cloud and OpenAI authority gates.

Local verification: six focused tests pass. The tests cover identity mismatch, secret-field rejection, metadata readiness, the 600-second handle ceiling, handle revocation and the prohibition on secret-version access or blanket IAM roles.

No provider mutation, repository creation, IAM grant, secret retrieval, Cloud Run operation, live capability-handle issuance or OpenAI key deletion is performed by this release.
