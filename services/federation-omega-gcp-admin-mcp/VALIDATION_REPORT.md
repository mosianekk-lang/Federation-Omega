# Validation report — v0.2.2

Validated 2026-08-17.

- TypeScript no-emit and compiled build: PASS.
- Integrated Node suite: 46/46 PASS.
- Complete tool surface: 17/17 preserved.
- Alpha-Omega DAG: acyclic; one serialized effectful lane.
- WIF fixture canaries: exact numeric identity PASS; name-only identity rejection PASS; Owner/Editor rejection PASS.
- Cloud Build and GitHub workflow YAML parse: PASS.
- `ops/verify_gcp_admin_mcp_wif.sh` and normalized Cloud Build rollout shell syntax: PASS.
- Health smoke: version 0.2.2, `transport_liveness_only`.
- Live provider deployment: NOT RUN; authority gate remains fail-closed.
