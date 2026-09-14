# ADR-0003 — Sovereign trust/signing/provenance plane
Status: ACCEPTED FOR V0.1 CANDIDATE

## Decision
FUSE owns release trust roots and can verify artifacts without mandatory third-party online services. Sigstore/SLSA-compatible formats may be used, but public services are optional.

## Required controls
- offline-capable root key ceremony and documented rotation;
- delegated online release keys;
- TPM2/HSM integration where available;
- signed OS/package/container/model/policy artifacts;
- SBOM and provenance bound to exact source/build identity;
- measured/secure boot integration where hardware supports it;
- revocation and rollback plans.

## Prohibition
No maturity claim may treat a hash alone as a signature, or a source-package hash as proof of the final runtime image digest.
