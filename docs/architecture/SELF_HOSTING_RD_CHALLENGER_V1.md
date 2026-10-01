# SELF_HOSTING_RD_CHALLENGER_V1

## Purpose

This harness advances the Self-Hosting R&D Court from a source contract to a bounded local challenger execution primitive.

It reuses FUSE Virtual Forge and does not create a second executor authority.

## Allowed surface

The v1 challenger accepts only local Python module execution for `compileall` and `unittest`. It forbids shell execution, inline `python -c`, URL/network-style task inputs, provider effects, IAM changes, public invocation, production activation, and source-main mutation.

## Evidence

A challenger plan binds:

- source epoch,
- owner-goal digest,
- build tasks,
- test tasks,
- expected artifact SHA-256 values,
- declared external runtime dependencies,
- disconnected rebuild requirement,
- rollback reference.

The receipt records task evidence and artifact evidence. Its reproducibility fingerprint intentionally excludes wall-clock timing and uses stable task/plan/artifact projections.

## Maturity boundary

`challenger_ready=true` means bounded source-independent local evidence only.

It does **not** prove matched incumbent/challenger quality, production runtime, owner-value gain, persistent hosting, physical-device behavior, or independent Judge approval.

The next court is matched incumbent/challenger evaluation plus a stronger cold-start disconnected rebuild.
