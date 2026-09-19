# KDV_READ_CONTINUITY_V1

## Purpose

Provide provider-neutral read continuity for Kim Dataverse without creating a
second KDV, memory root, truth root, or writer.

This residual exists because the estate already has the stronger foundations:

- KDV typed schema and structural schema digests;
- source/runtime/provider projection separation;
- OOXML semantic decoding;
- guarded writes with live-schema readback;
- FKCM event-first local shadow convergence;
- FKCM deterministic restart/replay equality;
- SOVARA deterministic backup/restore.

The missing piece is a sealed package that keeps those existing semantics
readable during provider unavailability.

## Flow

fresh provider/canonical observation -> FKCM events -> deterministic private snapshot
-> local restore -> deterministic replay -> AS_OF_ONLY reader

The archive binds source revision, observation time, structural schema SHA-256,
event-log SHA-256 and replayed projection SHA-256.

## Currentness

A snapshot that was captured from a verified provider read records that fact as
historical provenance only. After restoration it is still AS_OF_ONLY.

Calling the local reader with require_current=true fails with
KDV_PROVIDER_READ_REQUIRED_FOR_PRESENT_TENSE. Present-tense truth still requires
a fresh authorised provider or canonical read.

## Authority

The reader has no write method.

It performs no KDV mutation, Google mutation, provider effect or cutover. It
cannot become canonical and cannot promote FKCM shadow state into authority.

This extends the existing KDV/FKCM plane; it does not replace it.