# RealityGuard

RealityGuard is a runnable, offline, deterministic protection and solutions layer for AI-assisted work. It compares what a model claims against what the supplied evidence can actually prove, blocks unsafe completion language, independently preserves the valid owner objective through a reuse-first solution route, and gates new construction on a current environment inventory.

Version 0.4.1 adds a central, private-data-safe fault-book manager alongside the governed automatic-upgrade decision. It verifies hash-chained fault ledgers, preserves revisions and forks, deduplicates exact re-imports, holds raw event content in the private registry, and emits a redacted Federation manifest. It never treats source presence as proof that every ChatGPT or Federation host is bound.

It is **implemented and tested locally**. It is not installed in ChatGPT, not bound to a signed-in browser, and not deployed as a provider-side interceptor. Those states require separate authority and target-system readback.

## Core state contract

`DESCRIBED → BUILT → TESTED → STORED → REGISTERED → INSTALLED → BOUND → DEPLOYED → RUNNING → READ_BACK → ACCEPTED`

RealityGuard never infers a later state from an earlier one. An artifact does not prove installation; a test does not prove deployment; a receipt does not prove semantic success; and model-authored proof is not independent proof.

## Run

```bash
PYTHONPATH=src python -m realityguard.cli health
PYTHONPATH=src python -m realityguard.cli taxonomy
PYTHONPATH=src python -m realityguard.cli scan --input examples/false_ownership.json
PYTHONPATH=src python -m realityguard.cli resolve --input examples/chatbridge_solution_request.json --capabilities examples/federation_capabilities.json
PYTHONPATH=src python -m realityguard.cli prebuild --input examples/chatbridge_prebuild_request.json --capabilities examples/federation_capabilities.json
PYTHONPATH=src python -m realityguard.cli upgrade --input examples/material_cycle_upgrade.json --capabilities examples/federation_capabilities.json
PYTHONPATH=src python -m realityguard.cli federation-upgrade --input examples/material_cycle_upgrade.json --capabilities examples/federation_capabilities.json --adapter-contract federation/REALITYGUARD_AUTO_UPGRADE_ADAPTER.v1.json
PYTHONPATH=src python -m realityguard.cli faultbook-import --ledger FAULTS.jsonl --metadata IMPORT.json --registry PRIVATE_REGISTRY.json
PYTHONPATH=src python -m realityguard.cli faultbook-verify --registry PRIVATE_REGISTRY.json
PYTHONPATH=src python -m realityguard.cli faultbook-manifest --registry PRIVATE_REGISTRY.json
```

Exit codes: `0` bounded claim/action or valid manager result emitted, `2` invalid input, `3` claim blocked or rewrite required, `4` proposed build blocked or redirected to reuse, `5` duplicate or unsafe upgrade blocked, `6` private registry verification failed.

## Central fault-book manager

`faultbook-import` verifies the complete parent-plus-payload hash chain before an atomic registry write. It records exact artifact digests, normalized fault fingerprints, open regression tests and per-surface consumer states. An identical source import is a no-write duplicate; a changed source is preserved as a revision.

`faultbook-manifest` is safe for source review: it excludes raw events, local paths and private storage references. Historical or inaccessible chats remain `ADAPTER_REQUIRED`; the package does not claim they were rewritten or synchronized. See `docs/CENTRAL_FAULTBOOK_MANAGER.md`.

## Reuse-first solution contract

`resolve` keeps two decisions separate:

1. `truth` decides what the evidence supports.
2. `solution` decides how to preserve the objective through `ADOPT`, `ADAPT`, `COMPOSE`, `PATCH_EXISTING`, or `BUILD_NEW_ONLY_IF_GAP`.

An unsafe claim can therefore be blocked while its objective continues. New construction is never automatically authorized: the broker first filters stale, unverified, unauthorized, externally effectful, costly and semantically duplicate capabilities, and a remaining gap still requires bounded proof.

The included Federation capability manifest is a provenance map derived from current source readback. It does not import Alpha-Omega's commercial domain and does not claim a live Federation runtime binding. RealityGuard adapts its reusable patterns: canonical identity, deduplication, dependency ordering, atomic journaling, idempotency and uncertain-outcome quarantine. It also recognizes the existing tested-local `chatbridge-companion` as the implementation of the button/capsule layer, so only browser installation, signed-in binding and live semantic canary work remain as gaps.

## Mandatory pre-build contract

`prebuild` binds the decision to the canonical hash of a finite capability manifest. It fails closed unless the supplied inventory contract says it is current, enumerated, inspected to its declared end and source-identified. It then applies explicit supersession and semantic duplicate suppression before selecting a route:

- complete existing coverage: `BLOCK_DUPLICATE_BUILD` and `ADOPT`;
- scoped extension of a selected component: `ROUTE_PATCH_EXISTING`;
- usable partial capabilities: `ROUTE_COMPOSE_EXISTING`;
- unproven residual gap: `BLOCK_BUILD_GAP_PROOF_REQUIRED`;
- installation/binding/deployment/readback deficit: `BLOCK_BUILD_LIFECYCLE_GAP`;
- exact evidenced residual capability with no viable existing route: `ALLOW_BOUNDED_NEW_BUILD`.

The proposed component must cover the proven gap exactly: missing scope and extra unproven scope both block authorization. The output separates `reuse_route_authorized`, `build_authorized`, and `proposed_action_authorized` so a valid reuse recommendation cannot be mistaken for permission to build the rejected replacement.

`inventory_verified` is deliberately scoped by `inventory_verification_scope=CALLER_SUPPLIED_MANIFEST_HASH_AND_DECLARATIONS`. RealityGuard proves internal binding and decision consistency; the adapter that inventories a real filesystem, repository, Drive, account or cloud runtime must separately prove that its enumeration was complete. The local gate does not invent that external proof.

For ChatBridge, the canary blocks a replacement extension because the existing 0.2.0 companion already provides the local button, capture, capsule, injection, validation and one-time route, together with a read-only Windows policy-readiness assessor and a fail-closed enterprise handoff. The assessor has not run on the target work laptop. Browser policy readback, installation, signed-in binding, live interception and successor-chat readback are lifecycle execution/proof gaps; they are not permission to discard or rebuild that source or bypass employer policy.

## Governed learning

```bash
PYTHONPATH=src python -m realityguard.cli learn \
  --incident examples/capability_dilution_incident.json \
  --ledger proof/adaptive_learning_ledger.json \
  --promotion-state TESTED \
  --regression-test test_false_claim_is_blocked_while_objective_is_preserved
```

The learning ledger deduplicates by a stable incident fingerprint and increments recurrence instead of creating another engine or skill. `REGISTERED` and `BEHAVIOR_PROVEN` cannot be self-promoted by this local command. Governed executors must also fail closed after a permit or validation failure; `RG-026` records command-sequence fallthrough, while `RG-027` records construction started before reuse preflight.

## Governed automatic upgrades

`upgrade` is an invocation-driven material-cycle hook, not a daemon. It binds the decision to a current finite capability-manifest hash and the exact attested environment, tests whether the event is strong enough to justify more than observation, preserves declared healthy capabilities, blocks cost/authority/burden expansion, and calculates which dependent artifacts must be invalidated and repaired in order.

Every actionable result still has `automatic_execution_authorized=false` and `promotion_authorized=false`. The integrated host must obtain and consume a separate single-use Formation permit before its selected executor acts, then pass the original-failure, healthy-case, rollback and semantic-readback gates. This separation makes improvement automatic without making authority automatic.

The single executable Federation source adapter accepts every system ID in the current canonical contract, so those systems do not need separate RealityGuard engines. It still marks each live host as `ADAPTER_REQUIRED` until that runtime calls and proves the hook. See `docs/FEDERATION_AUTO_UPGRADE_CONTRACT.md`.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Integration contract

Place RealityGuard immediately before user-visible completion/status output. The caller supplies a structured claim, evidence records and scope context. If the verdict is not `ALLOW_BOUNDED`, the caller must suppress the original status and use `safe_statement` plus the findings and missing proof gates.

The default `scan`, `resolve`, `prebuild`, `upgrade`, `faultbook-verify`, and `faultbook-manifest` paths perform no network access. Explicit local mutation paths are `scan --audit-log`, `learn --ledger`, and `faultbook-import --registry`; the latter atomically publishes a verified private registry. The gate is mandatory for any pipeline that places it before construction or a material cycle boundary; this local package does not claim universal interception of systems that have not integrated it.
