# ADR-0001 — Upstream-first Linux base
Status: ACCEPTED FOR V0.1 CANDIDATE

## Decision
Use upstream Linux LTS/stable plus a conventional GNU/POSIX userspace as the initial kernel/userspace base. Maintain a minimal FUSE-owned delta rather than a broad proprietary fork.

## Why
This maximizes hardware coverage, security review, ecosystem compatibility and maintainability while preserving sovereignty through source mirroring, reproducible builds, FUSE signing, policy and recovery.

## Rules
- Each downstream patch has owner, rationale, test, upstream/reference issue where practical and deletion criteria.
- Kernel configuration is versioned and reviewed as code.
- Tier-1 CPU architectures are x86_64 and ARM64.
- RISC-V remains tier-2 until toolchain/boot/driver gates pass.

## Rejected for now
- New kernel from scratch: unjustified security and driver burden.
- Permanent hard fork of Linux: unnecessary sovereignty cost.
