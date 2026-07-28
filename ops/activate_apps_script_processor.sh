#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/apps_script/sentinel_processor"
PRIMARY="1cUQy4k_IE_9BNhIJzk5ik49Xhus3xWD7qLjIv6yf8ncEKwzCqjjGhh7D"
SECONDARY="1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R"

require() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
require clasp
require node
require mktemp

cp "${SRC_DIR}/Code.gs" /tmp/fedomega_sentinel_code.js
node --check /tmp/fedomega_sentinel_code.js
node -e 'JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"));' "${SRC_DIR}/appsscript.json"

activate_candidate() {
  local script_id="$1"
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN

  cp "${SRC_DIR}/Code.gs" "${work}/Code.gs"
  cp "${SRC_DIR}/appsscript.json" "${work}/appsscript.json"
  cat > "${work}/.clasp.json" <<JSON
{"scriptId":"${script_id}","rootDir":"."}
JSON

  (
    cd "$work"
    clasp push --force
    local output
    output="$(clasp run installSentinelProcessor 2>&1)" || {
      echo "$output" >&2
      return 1
    }
    echo "$output"
    grep -q 'FEDOMEGA-GAS-INSTALLED' <<<"$output"
  )

  printf '{"receipt":"FEDOMEGA-GAS-ACTIVATION-VERIFIED","scriptId":"%s","source":"apps_script/sentinel_processor","queueSpreadsheetId":"1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg"}\n' "$script_id"
}

for candidate in "$PRIMARY" "$SECONDARY"; do
  echo "Attempting Apps Script candidate: ${candidate}"
  if activate_candidate "$candidate"; then
    exit 0
  fi
  echo "Candidate failed: ${candidate}" >&2
done

echo "Both Apps Script candidates failed activation." >&2
exit 1
