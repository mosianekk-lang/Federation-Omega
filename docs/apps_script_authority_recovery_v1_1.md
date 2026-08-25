# Current-Main Integration — Federation-Omega

## Base

- repository: `mosianekk-lang/Federation-Omega`
- selected base main: `725f9fe85b4210e9f3b13bba6108f89c8d2b586d`
- existing source guard: merged PR #571
- workflow changes required: none

The selected base and exact old gate/test blobs are preserved under `provenance/current_main_725f_selected/`. A fresh GitHub branch must be created from the current live main; if live main differs, the payload must be rebased and rerun before any PR.

## Payload

The integration patch updates the existing `ops/apps_script_authorization_gate.py` and its tests, and adds the two-plane candidate, Node hostile test, provider-cutover-v3 admission wrapper, signer, governance contract, public-safe receipt and documentation.

The existing Airlock already runs `test_phoenix_provider_cutover_v3*.py` and `test_apps_script_authorization_gate.py`; no workflow addition is needed.

## Admission conditions

- branch descends from live current main;
- no private fleet source, raw secret, credential, binary cache or signed URL;
- exact-head Airlock, Leak Guard and Bubbles checks pass;
- source candidate remains provider-disabled;
- merge does not claim live Apps Script repair or Google authority.
