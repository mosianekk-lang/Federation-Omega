# SOVARA Canva two-layer canary v1

This source-only envelope compresses the current four-candidate Canva canary
without choosing a candidate or calling Canva. It extends the existing SOVARA
canary pattern; it does not relax the public-synthetic canary's no-mutation
invariant.

## Build classification and architecture

This increment is a Python library plus deterministic test suite at **PROD
FOUNDATION (source/test only)**. The public interface is the typed API exported
from `sovara.creative`; the governance JSON is the candidate-neutral input.

- Frontend, backend service, database, queue, worker, scheduler, cache, and
  durable storage are `NOT_APPLICABLE`: the evaluator is pure and persists
  nothing.
- Authentication is `NOT_APPLICABLE` inside this module: it accepts only a
  non-secret connector reference and requires externally issued authority
  receipts. It never reads a credential.
- Provider execution and deployment are `NOT_APPLICABLE` in this increment.
  A future adapter may translate a ready decision into a connector invocation,
  but it must remain outside this authority-free evaluator.
- Observability is deterministic: every decision carries a state, reason set,
  next gate, receipt-validation flag, structural-precondition flag, an
  envelope-consistency flag, an always-false provider-effect flag, and a fixed
  truth boundary. `contract_preconditions_met` remains false until an external
  trust service authenticates provenance.

The bounded lifecycle is:

`INVARIANT → OWNER_SELECTION → CREATE_AUTHORITY → CREATE_READBACK → DRAFT_AUTHORITY → DRAFT_PREVIEW → COMMIT_APPROVAL → COMMIT_READBACK → RECEIPT_VALIDATED`

Any stale, mismatched, replayed, unapproved, non-rollbackable, or forbidden
effect enters a held/quarantine state rather than retrying or inheriting
authority.

## Layer 1 — candidate-neutral invariants

The governance contract binds a candidate-roster commitment, a strict current
Canva connector-schema shape and provenance commitment, one-design blast
radius, verified eligibility states, zero raw-sensitive-payload handling,
required readbacks, and create/draft rollback requirements. It deliberately
contains no `candidate_id`, `job_id`, or selected-candidate value and grants no
create, draft, commit, export, download, share, or publish effect.

The only successful Layer 1 outcome is `HOLD_OWNER_SELECTION`. A stale connector
snapshot stops earlier at `HOLD_SCHEMA_FRESHNESS`.

## Layer 2 — selection-bound execution

Layer 2 accepts externally issued evidence but never issues authority itself.
The gates are sequential and non-transitive:

1. An explicit, owner-authored, trusted-surface, non-inferred, single-use
   selection receipt binds the invariant, candidate set and roster commitment,
   exact `job_id`, exact `candidate_id`, brand-control hash,
   eligibility-evidence hash, and current connector-schema hash. A separate
   typed eligibility envelope must bind claimed membership plus exact adult,
   consent, rights, origin, and privacy states. These fields are not a signature
   verifier; their provenance remains external and untrusted here.
2. A separate current one-create authority binds the exact selection, request
   hash, expected owner/title hashes, runtime, opaque non-secret credential
   handle, zero-cost ceiling, privacy eligibility, and a provider-native create
   rollback tool present in the strict schema. Only then can the evaluator
   return the envelope-only state `READY_FOR_CANDIDATE_CONVERSION`.
3. Provider-native `get_design` metadata must match the selected job/candidate
   and show the create authority was consumed. This does not authorize editing.
4. A separate single-use draft authority binds the created design and exact
   operations hash. `cancel_editing_transaction` capability must be proven
   before `READY_FOR_DRAFT_EDIT`.
5. Draft operations must remain uncommitted and produce an owner-visible preview
   receipt. Preview alone never authorizes commit.
6. A new explicit owner approval must be issued after that preview and bind its
   exact design, transaction, operations, and preview hashes. Only then can the
   evaluator return `READY_FOR_COMMIT`.
7. Commit and post-commit design readbacks must match every prior binding,
   expected post-commit design hash, and show approval consumption through the
   propagated transition ledger. The terminal source decision is
   `SAVED_DESIGN_RECEIPT_VALIDATED`, not a provider-runtime or production claim.

The enforced chronology is strict:

`ELIGIBILITY ≤ SELECTION < CREATE_AUTHORITY < CREATE_READBACK < DRAFT_AUTHORITY < PREVIEW < OWNER_APPROVAL < COMMIT_READBACK`

Every receipt class rejects blank identifiers, naive timestamps, malformed
SHA-256 bindings, raw-secret-shaped credential values, nonzero/unknown cost at
create, draft, approval, or commit,
unsafe multiplicity, stale windows, mismatches, duplicate consumption events,
and replay. Issuance objects remain immutable `consumed=false` snapshots;
consumption is represented by the propagated ID ledger plus the matching
provider readback transition.
Any export, download, share, or publish observation quarantines the receipt.

Because this module cannot authenticate a connector invocation, every
`CanvaCanaryDecision.ready_for_effect` and `contract_preconditions_met` values
are false. A `READY_*` state with `envelope_consistent=true` means only that a
caller-supplied envelope is structurally self-consistent; no executor may treat
that as membership, provenance, rollback, cost, or provider authority proof.

## Provider capability gap retained

The current connector exposes candidate conversion, transactional drafting,
cancel, commit, preview/read, and design readback. It does not expose a callable
export/download/publish path, and this schema snapshot does not assume a
provider-native delete/archive operation for a newly created design. Therefore
the checked-in governance loader admits exactly the eight captured tools and
five exact semantic invariants; editing in a delete/archive tool, candidate
choice, or recomputed schema hash is rejected. The current contract therefore
deterministically remains at
`HOLD_CREATE_ROLLBACK`; an arbitrary proof string cannot bypass the gate. A
future fresh schema may add an exact `delete_design` or `archive_design` tool,
but provider authority and authenticated provenance would still remain external.

## Proof and maturity boundary

The module is a pure deterministic evaluator. Local tests or CI prove source
behavior only. Simulated observations cannot prove Canva execution. Even a
structurally valid provider-native receipt set must have its provenance
authenticated outside this module. One saved-design receipt does not prove
export, download, sharing, publishing, repeated success, commercial value,
deployment, traffic admission, or production maturity.

The next live sequence is therefore gated by two owner decisions and current
provider capabilities: select one candidate before create, then explicitly
approve the exact draft after preview before commit. No gate may be inferred or
reused.

## Files and validation

- `sovara/creative/canva_two_layer_canary.py` — typed pure evaluator
- `governance/sovara_canva_two_layer_canary_contract_v1.json` — neutral
  invariant and canonical connector-schema snapshot
- `tests/test_sovara_creative_canva_two_layer_canary.py` — happy path, invalid input,
  permission denial, staleness, replay, rollback, forbidden-effect, readback,
  chronology, schema-forgery, strict-loader, cost/secret, and truth-boundary tests
- `sovara/creative/__init__.py` — package exports
- `.github/workflows/sovara-litellm-v2-3-provider-admission.yml` — preserves the
  source-only null provider-exit-code invariant without changing triggers or
  permissions

Run the focused suite:

```bash
python -m unittest -v tests.test_sovara_creative_canva_two_layer_canary
```

Run the bounded SOVARA regression set:

```bash
python -m unittest -v \
  tests.test_sovara_creative_canary \
  tests.test_sovara_creative_canary_authority \
  tests.test_sovara_provider_execution_fabric \
  tests.test_sovara_creative_canva_two_layer_canary
```

Compile and verify whitespace/integrity before a PR:

```bash
python -m compileall -q sovara/creative tests/test_sovara_creative_canva_two_layer_canary.py
git diff --check
```

Deployment means source admission through a purpose-branch PR and CI only. It
does not mean Canva execution or production promotion. Roll back an admitted
source change with `git revert <admitted-commit>`; no provider rollback is
needed for this source-only increment because it creates no provider object.

## Debugging guide

| Symptom | Likely cause | Safe fix |
|---|---|---|
| `HOLD_SCHEMA_FRESHNESS` | Connector snapshot expired | Fresh-read the callable schemas, update the canonical snapshot and hash, rerun tests |
| `HOLD_SELECTION_RECEIPT` | Choice was inferred, stale, mismatched, or replayed | Capture a new explicit owner selection receipt; do not copy authority |
| `HOLD_CREATE_ROLLBACK` | No proven delete/archive/reversal for the created design | Keep create disabled until the provider/bridge exposes and verifies bounded rollback |
| `HOLD_DRAFT_ROLLBACK` | Draft cancellation is unavailable or unproven | Verify `cancel_editing_transaction`; never begin the draft without it |
| `HOLD_COMMIT_APPROVAL` | Preview missing or approval predates/mismatches it | Show the exact preview and capture a new single-use owner approval |
| `HOLD_*_READBACK` | Provider metadata or hashes do not reconcile | Quarantine the result; preserve receipts; do not retry or promote |
| `SAVED_DESIGN_RECEIPT_VALIDATED` in a unit test | Simulated fixture passed structural checks | Do not claim provider execution; authenticate real receipt provenance separately |
