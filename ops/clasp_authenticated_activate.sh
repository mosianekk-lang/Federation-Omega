#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/mosianekk-lang/Federation-Omega.git"
WORKDIR="${HOME}/federation-omega-clasp-activation"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require git
require node
require npm

if ! command -v clasp >/dev/null 2>&1; then
  npm install --global @google/clasp
fi
require clasp

if ! clasp login --status >/dev/null 2>&1; then
  echo "No authenticated clasp session found." >&2
  echo "Run: clasp login" >&2
  exit 2
fi

rm -rf "$WORKDIR"
git clone --depth 1 "$REPO_URL" "$WORKDIR"
cd "$WORKDIR"

bash ops/activate_apps_script_processor.sh

echo '{"receipt":"FEDOMEGA-CLASP-LAUNCHER-COMPLETED","repository":"mosianekk-lang/Federation-Omega","next_proof":"FEDOMEGA-GAS-ACTIVATION-VERIFIED plus fresh Heartbeat row"}'
