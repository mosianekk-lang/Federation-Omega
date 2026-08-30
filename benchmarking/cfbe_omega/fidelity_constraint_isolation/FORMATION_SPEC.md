# Formation Specification

## Mission

Provide one deterministic, fail-closed boundary between canonical intent and platform execution capability. The kernel must preserve source identity, reject semantic or structural dilution, select only admissible evidence-backed routes, and retain gaps as build work rather than rewriting the source around them.

## Architecture

1. `CanonicalSource` binds source identity, version, media type, fidelity mode, optional protected invariants, and expected SHA-256.
2. `evaluate_fidelity` produces `ACCEPT_ZERO_DILUTION` or `REJECT_DILUTION` before route analysis.
3. The maturity ladder prevents source, test, registration, authorization, readiness, deployment, and readback evidence from collapsing into one claim.
4. The adapter selector enforces authority, recurring cost, user burden, external-effect, preservation, and evidence limits.
5. Existing `CapabilityResolutionGate` supplies exact-platform boundary language.
6. Stable AO-CRA triggers retain unresolved requirements without modifying canonical material.
7. The CLI emits an atomic, hash-bound, content-free receipt.

## Interfaces and data

- Input: local JSON file or typed Python objects.
- Output: public-safe JSON report under schema `CFBE-OMEGA-FIDELITY-CONSTRAINT-ISOLATION-RESULT-V1`.
- Persistent database: not applicable; this kernel is pure and stateless.
- Queue or worker: not applicable; the kernel executes synchronously and performs no provider action.
- Frontend: not applicable; consumers render the JSON report.
- Authentication and secrets: not accepted. Evidence fields are references, never secret values.

## Security and truth controls

- Invalid identity, hash, enum, evidence, authority, cost, or selector input fails closed.
- Raw source and candidate data never enter the receipt.
- Adapter routes cannot override a fidelity rejection.
- `NOT_EXECUTED` is immutable in evaluator output.
- Readback maturity requires explicit deployment and readback evidence through every preceding rung.
- The kernel neither bypasses governing safety boundaries nor lets a platform limitation dilute canonical work.

## Observability

The result records source/candidate hashes, fidelity violations, requirement decisions, route rejections, selected adapters, build triggers, truth-boundary booleans, and a deterministic receipt hash. No throughput or provider-live claim is inferred from source tests.

## Failure and recovery

- Parse or contract failure: reject the request; do not replace an existing output.
- Fidelity failure: emit `REJECT_DILUTION`; do not negotiate routes.
- Platform gap: emit `PLATFORM_BOUNDARY` and one stable trigger per missing capability.
- Interrupted output: temporary file is removed; prior output remains intact.
- Rollback: discard the candidate/report. The evaluator never mutates canonical source or provider state.

## Deployment boundary

The package is source implementation only until deterministic verification completes. GitHub admission can prove repository serving state, but no runtime deployment exists unless a separate authorized provider route supplies an independent semantic readback receipt.

## Verification matrix

- Exact acceptance and modification rejection.
- Ordered additive text and recursive additive JSON.
- Literal, JSON-pointer, and Python-AST protected invariants.
- Maturity evidence ladder and overclaim rejection.
- Authority, cost, burden, external-effect, and fidelity-evidence gates.
- Native, adapter, and platform-boundary selection.
- Stable AO-CRA triggers and deterministic receipts.
- Atomic CLI output and raw-content exclusion.
- Repository anti-dilution and regression suites.
