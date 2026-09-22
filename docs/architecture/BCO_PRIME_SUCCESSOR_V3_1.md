# BCO-Prime successor v3.1 architecture

## Outcome

V3.1 turns the v3.0 flight, Capability-DNA and shadow-learning plane into an
on-demand governed regression cycle. It detects drift, extracts only changed
semantic capability records, quarantines hard regressions and produces repair
proposals without applying them. The sealed v2 and v3.0 archives remain the
rollback lineage and are never overwritten.

## Components and boundaries

| Component | Responsibility | Hard boundary |
|---|---|---|
| Baseline registry | Complete predecessor ZIP manifest, tracked files, policy, capability, test and result baselines | Trust requires an externally pinned signer fingerprint |
| Lamport signer | One-time SHA-256 signature from an injected 32-byte seed | Seed is never returned, persisted or scanned |
| Drift engine | Deterministic integrity, source, policy, DNA, test, result and partial-coverage classes | `NO_DRIFT` requires verified signature and complete coverage |
| Incremental scanner | Secure no-follow reads, source-stability checks, secret/licence hold and semantic DNA | Integrity still hashes every in-scope file; only extraction is incremental |
| Scoreboard | Hard-veto, sticky quarantine and append-only hash chain | Positive scores never cancel a hard veto; quarantine never auto-clears |
| Shadow repair planner | Baseline-bound declarative proposals and rollback requirements | `executable=false`; no apply/import/eval/exec/subprocess/network route |
| Cycle coordinator | Lock, cancellation checkpoints, compare, scan diff, candidate, scoreboard and one commit | Cancellation/supersession prevents commit and baseline advancement |
| Successor registry | Strict dispatch for nine additive operations and inherited delegation | Rejects string Boolean/numeric coercion and normalized effect-key escape |

## Baseline trust

The baseline contains its signer public key only to verify a signature. The
caller must separately supply the expected public-key fingerprint from the
trusted release receipt. Verification also checks the body and envelope hashes,
minimum generation and optional parent baseline. A stripped signature, changed
body, replacement key, replayed generation or untrusted key returns hold.

## Privacy and licence handling

The scanner holds secret-bearing files before DNA extraction. It detects common
private-key, JWT, cloud-token, URI-credential, assignment and high-entropy
signals. Held outputs contain only a hashed path token and reason code—no raw
path, content hash, heading, JSON key or symbol. SPDX compounds, conflicts,
unknown licences and non-standard-library dependencies without compatible
licence evidence remain `LICENSE_HOLD`.

## State and recovery

Cycle states are `PASS`, `HOLD`, `QUARANTINED` or `CANCELLED`. The scoreboard is
append-only and hash-chained. A control rollback may select a previously
verified baseline pointer; it cannot mutate the monitored source. Stop by
terminating the invoking process. No worker, scheduler, lease or network
session survives return.

## Truth boundary

Local source and test proof does not authorize deployment, registration,
provider mutation, automatic baseline updates, quarantine clearing or stable
promotion. Runtime state is `ON_DEMAND_GOVERNED` and release authorization stays
false until a separately authorized system consumes the verified package.
