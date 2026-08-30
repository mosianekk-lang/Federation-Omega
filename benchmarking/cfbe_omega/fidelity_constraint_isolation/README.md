# CFBE-Ω Fidelity and Constraint Isolation

This package prevents platform constraints from silently changing canonical code, systems, or directives. It evaluates source fidelity first, negotiates only evidence-backed native or adapter routes second, and preserves every unresolved platform need as a deterministic AO-CRA build trigger.

It composes the admitted `CapabilityResolutionGate` for exact-scope platform-boundary language. Provider-specific execution remains in the existing provider constraint resolver; this package does not create a second execution control plane.

## Result model

| State | Meaning |
|---|---|
| `REJECT_DILUTION` | Canonical material was deleted, modified, reordered, or a protected invariant changed. |
| `PLATFORM_BOUNDARY` | Fidelity passed, but a requirement lacks an admissible native or adapter route. |
| `ROUTE_READY_LOCAL` | All routes have deterministic test and rollback evidence. |
| `ROUTE_READY_PROVEN` | All routes additionally have provider readback proof. |

Every result declares `executionState: NOT_EXECUTED`. A ready route is not a deployment or completion claim.

An unevidenced gap is classified as `UNRESOLVED_CAPABILITY`, not a platform hard limit. Exact hard-limit language is emitted only when a requirement explicitly sets `platformHardLimit: true` and supplies `boundaryEvidenceRef`.

## Fidelity modes

- `EXACT`: UTF-8 content must be byte-exact.
- `EXACT_OR_ADDITIVE`: canonical text lines must remain an ordered subsequence; canonical JSON must remain a recursive ordered subset.
- `PROTECTED_INVARIANTS`: named literals, JSON pointers, or Python AST symbols must remain exact.

## Run

```bash
python -m benchmarking.cfbe_omega.fidelity_constraint_isolation \
  --input request.json \
  --output /tmp/cfbe-fidelity-result.json
```

The CLI replaces its output atomically. Raw canonical and candidate content never appears in the report; only identities and SHA-256 bindings do.

The complete public-safe schema and invariants are in `contract_v1.json`.
