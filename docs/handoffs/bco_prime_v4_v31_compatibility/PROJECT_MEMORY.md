# Project memory — BCΩ-PRIME v4 compatibility

## Immutable facts

- Mission: `CFBE-BCO-V4-COMPAT-20260902`, version 1.
- Fresh main at build start: `b70244dd2eadb28ddab5cb5596507d9081b1c2df`; revalidated immediately before publication at `ceb5cf36d1e608d0520a23114fe4bfc08eab644a` (four upstream commits changing only `bubbles/command_bus.py` and `tests/test_bubbles_command_bus.py`).
- v3.1 registry SHA-256: `111e37d3f6d990819f5d7ce6463cf62babb13aa3cdbb20db1490ec9366211a26`.
- v4 institution SHA-256: `3cada8deb311b9fcefe04990c0063086b0e623884591d23fe3359d258c04d0c8`.
- v4 genome bridge SHA-256: `937024053bf593a03ffa59b21dea301f9ab2ce8c7fd86e684ba4669aa3e3f33c`.
- The v4 materialization did not contain the v3.1 module; the isolated test
  workspace deliberately materializes both exact closures without changing the
  source readback directories.
- Root `BUILD_CONTRACT.json` was absent on fresh main; this build creates the v4
  contract rather than modifying a live root contract.

## Design decisions

1. Preserve v3.1 operations by delegation and return inherited receipts without
   a v4 wrapper.
2. Add only manifest, decision compilation, and strategic-genome recommendation.
3. Accept plain JSON at the compatibility boundary and construct the real v4
   dataclasses after strict field/type/range checks.
4. Pin source identity in code, manifest, documentation, and build contract.
5. Keep v4 output local and non-sovereign: no dispatch, provider effect, source
   mutation, deployment, or stable promotion.
6. Support explicit registry injection, but never synthesize a missing v3.1
   implementation.

## Verification memory

- Documentation gate: `ALLOW_CYCLE`, zero issues.
- Adapter focused suite: 23/23 passed after the independent v4.0.1 injected-registry attestation hardening.
- Full combined discovery found only the three expected inherited CFF fixture
  failures caused by its adjacent `cff_unpacked` path not being present at the
  combined workspace parent; 107/110 tests passed. This is a materialization
  limitation, not proof of a v4 regression.
- Final handoff records fresh reruns of syntax, focused adapter tests, v4
  tests, sealed v3.1 tests, MODISA validation, CLI semantic readback, and
  backup/restore hash comparison.

## Known limitations

- The current adapter binds a 40-character Git source identity because the
  existing v4 compiler validates that exact form.
- Full v3.1 execution still depends on its exact inherited local modules and
  optional CFF fixture layout. The safe subset remains usable without an engine;
  engine routes remain `BLOCKED_WITH_ROUTE` when absent.
- No live repository write, merge, deployment, registration, scheduler, provider
  effect, or stable promotion is part of this local build.
