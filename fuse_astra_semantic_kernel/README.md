# FUSE Astra+ Semantic Kernel v0.1

This package implements the first executable slice of the FUSE Astra+ v2.3 architecture pivot.

## Design rule

Canonical capability identity is semantic. Historical `IH-*` numbers are aliases only and may be ambiguous. The compiler fails closed on ambiguous aliases and unknown canonical capabilities.

## Compile order

1. Freeze mission/profile requirements.
2. Resolve canonical semantic capabilities.
3. Apply hard authority, residency, safety, quality, maturity and proof gates.
4. Remove disallowed providers when the profile requires Astra independence.
5. Score only the remaining qualified implementations for cost, latency, quality, sovereignty and locality.
6. Return the compiled route; execution and maturity remain separate proof stages.

## Current proof boundary

The package has local deterministic unit coverage for:

- preservation of conflicting historical aliases;
- unambiguous semantic identity;
- proof/authority gates before economics;
- Astra-independent routing rejecting OpenAI-only implementations;
- sovereignty-aware local preference after hard floors;
- successful compilation of a fully proved local-offline profile.

It does **not** claim live provider parity, production routing, model-weight ownership, or deployment maturity. Those require the FUSE provider/local readback and parity courts.

## Canonical planes

`CK.STATE`, `CK.CONTEXT`, `CK.MODEL`, `CK.TOOL`, `CK.EXEC`, `CK.IDENTITY`, `CK.POLICY`, `CK.AGENT`, `CK.OBSERVE`, `CK.EVAL`, `CK.PROOF`, `CK.ARTIFACT`.
