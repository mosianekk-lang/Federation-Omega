# FUSE AI-OS v0.1 bootstrap candidate

This tree is the first implementation candidate for FUSE AI-OS. It is intentionally small, auditable and proof-oriented.

Current proved scope after local validation: architecture/constitution artifacts plus deterministic source-manifest receipt generation. It does not yet prove an OS image, boot, accelerator, signing or deployment.

Next gates: reproducible rootfs/image composition, x86_64 QEMU boot, ARM64 QEMU boot, transactional update/rollback court, offline CPU inference smoke target, then signed release provenance.
