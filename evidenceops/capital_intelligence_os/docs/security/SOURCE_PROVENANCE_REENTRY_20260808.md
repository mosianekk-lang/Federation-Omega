# Source Provenance Re-entry — 8 August 2026

## Purpose

This record preserves the fail-closed handling of direct-push commit `b325d0ab302c89b0546007e47d82ebc7bff264f2` and defines the only acceptable repository re-entry path after its source-provenance admission failure.

## Truth boundary

- The direct-push commit remains historical `UNADMITTED_HISTORY`; this document does not retroactively associate it with a pull request.
- No provenance rule, Airlock rule, Leak Guard rule, OpenAI semantic rule, Apps Script authorization rule, or ancestry rule is weakened or bypassed.
- No provider credential, authorization value, secret payload, Cloud Run mutation, Secret Manager mutation, OpenAI key mutation, or production traffic change is performed by this repository change.
- Provider-native OpenAI rotation remains fail-closed until action-specific provider readback proves the remaining gates in `governance/openai_credential_rotation_manifest.json`.

## Re-entry procedure

1. Read current `main` immediately before branch creation.
2. Create the repair branch from that exact `main` SHA.
3. Require the pull-request Airlock to emit `HEAD_ANCESTRY_VERIFIED` before setup or regression execution.
4. Run the mandatory Airlock, Phoenix export purity, OpenAI semantic, Apps Script authorization, source provenance, provider-cutover, and Public Repository Leak Guard controls.
5. Re-read current `main` immediately before merge. If it advanced, do not force merge; rebuild from the new exact main.
6. Merge only the exact admitted head, then verify the exact post-merge main files and push-triggered Airlock/Leak Guard/Phoenix status.

## Recovery interpretation

A later PR-associated commit can restore PR-governed admission for new changes, but it does not erase or relabel the historical direct push. Any audit must continue to preserve the failed run and immutable provenance receipt for `b325d0ab302c89b0546007e47d82ebc7bff264f2`.

## OpenAI rotation boundary

Repository admission recovery is not provider proof. Secret Manager metadata, `mosiane-live-thread` destination binding, isolated canary success, exposed-key revocation, and old-key rejection remain separate provider-native gates and must not be inferred from repository status, HTTP success, wrapper `DONE`, generic health, source packages, ACTIVE labels, or heartbeat-only evidence.
