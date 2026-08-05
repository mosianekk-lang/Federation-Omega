# Provider Authority Attachment

This release closes the internal engineering path for attaching provider-native Google Cloud identity and consuming a redacted metadata receipt without storing credentials.

## Google Cloud

Use the regular Google Cloud console's Cloud Shell while signed in as `mosianekk@gmail.com`. Do not use an Open-in-Cloud-Shell link that clones a non-Google repository for the authority step, because that can open an ephemeral environment without the user's Google Cloud credentials.

Run the plan first:

```bash
chmod 700 tools/gcp_provider_authority_attach.sh
./tools/gcp_provider_authority_attach.sh --plan
```

The plan performs no mutation.

After verifying the exact account, project ID and project number, the bounded provider action is:

```bash
FEDOMEGA_PROVIDER_AUTHORITY_APPLY=ATTACH_GCP_READ_ONLY_V1 \
  ./tools/gcp_provider_authority_attach.sh --apply
```

This enables only the APIs required for metadata proof. It does not grant IAM roles, create service-account keys, access secret payloads, deploy Cloud Run or change traffic.

The verifier produces a redacted `provider-metadata-receipt.json`. Federation Omega validates that receipt before issuing one opaque read-only capability handle for at most ten minutes. The handle must then expire or be revoked and recorded through semantic readback.

## OpenAI

Existing-key deletion remains an official OpenAI provider-account action. It must occur only after dependent runtimes have migrated to the verified replacement references. The closure receipt records provider key-record identity, deletion time and rejected authentication result without retaining the key, suffix, hash or fingerprint.

## Truth boundary

Source, owner intent, CI and a sealed packet do not grant Google Cloud or OpenAI authority. Provider-native authentication and readback remain mandatory. No provider mutation is performed by this source release.
