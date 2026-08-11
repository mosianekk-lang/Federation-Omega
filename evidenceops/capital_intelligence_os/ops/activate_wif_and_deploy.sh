#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP="${SCRIPT_DIR}/bootstrap_github_wif.sh"

case "${1:---plan}" in
  --plan)
    exec "$BOOTSTRAP" --plan
    ;;
  --verify-wif)
    exec "$BOOTSTRAP" --verify
    ;;
  --apply-wif)
    exec "$BOOTSTRAP" --apply
    ;;
  --help|-h)
    cat <<'USAGE'
Usage: ops/activate_wif_and_deploy.sh [--plan|--verify-wif|--apply-wif]

This compatibility wrapper no longer builds or deploys directly. It keeps one
canonical production path: the manually dispatched, zero-traffic canary workflow
`.github/workflows/deploy-cloud-run.yml`.

--plan        Read-only WIF and least-privilege inspection. Default.
--verify-wif  Require the exact FEDOMEGA-WIF-CLOUD-VERIFIED receipt.
--apply-wif   Apply WIF only after the explicit approval environment variable
              required by bootstrap_github_wif.sh is present.

After verification, manually dispatch the deployment workflow with:
  confirmation = DEPLOY_SLRK_V3_2_TO_ARCHITRON9
  wif_receipt  = FEDOMEGA-WIF-CLOUD-VERIFIED
  promote      = false for canary-only, true for verified promotion
USAGE
    ;;
  *)
    echo "Direct build/deploy mode has been retired to prevent duplicate or unverified production mutation." >&2
    echo "Use --plan, --verify-wif or --apply-wif, then the manual canary workflow." >&2
    exit 2
    ;;
esac
