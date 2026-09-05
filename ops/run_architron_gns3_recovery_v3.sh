#!/usr/bin/env bash
set -euo pipefail

# ARCHITRON / Google Native Scheduler v3 recovery helper.
#
# Safety contract:
# - exact canonical ARCHITRON script only;
# - authenticated human-owner clasp session required;
# - read-only current-project manifest preflight before function invocation;
# - no clasp push/deploy/create/clone operation exists in this helper;
# - preserve a healthy singleton;
# - install only once, only from a proof-readback-verified failed canary;
# - require a second full canary contract after repair.

TARGET_SCRIPT_ID="1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R"
CANARY_FUNCTION="gasSchedulerCanaryV3"
INSTALL_FUNCTION="gasSchedulerInstallV3"
MODE="${1:-canary-only}"

case "$MODE" in
  canary-only|repair-if-needed) ;;
  *) echo "usage: $0 [canary-only|repair-if-needed]" >&2; exit 64 ;;
esac

command -v clasp >/dev/null 2>&1 || { echo "BLOCKED:CLASP_BINARY_ABSENT" >&2; exit 20; }
clasp login --status >/dev/null 2>&1 || { echo "BLOCKED:CLASP_OWNER_OAUTH_SESSION_ABSENT" >&2; exit 21; }

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
printf '{"scriptId":"%s","rootDir":"."}\n' "$TARGET_SCRIPT_ID" > "$work/.clasp.json"

preflight_execution_api() {
  # Read current project source into a disposable directory. Never print source.
  # This is a read-only contract check; no clasp push/deploy operations are allowed.
  (cd "$work" && clasp pull >/dev/null 2>&1) || {
    echo "BLOCKED:CLASP_CURRENT_PROJECT_PULL_FAILED" >&2
    exit 33
  }
  [[ -f "$work/appsscript.json" ]] || {
    echo "BLOCKED:CURRENT_MANIFEST_NOT_READABLE" >&2
    exit 34
  }
  python3 - "$work/appsscript.json" <<'PY2'
import json, sys
p=sys.argv[1]
try:
    data=json.load(open(p, encoding='utf-8'))
except Exception:
    raise SystemExit(2)
execution=data.get('executionApi')
if not isinstance(execution, dict):
    print('BLOCKED:CURRENT_MANIFEST_EXECUTION_API_ABSENT', file=sys.stderr)
    raise SystemExit(3)
access=str(execution.get('access') or '')
if access != 'MYSELF':
    print(f'BLOCKED:CURRENT_MANIFEST_EXECUTION_API_NOT_OWNER_ONLY:{access or "MISSING"}', file=sys.stderr)
    raise SystemExit(4)
scopes=set(data.get('oauthScopes') or [])
required={
  'https://www.googleapis.com/auth/script.scriptapp',
  'https://www.googleapis.com/auth/spreadsheets',
}
missing=sorted(required-scopes)
if missing:
    print('BLOCKED:CURRENT_MANIFEST_REQUIRED_SCOPES_MISSING:'+','.join(missing), file=sys.stderr)
    raise SystemExit(5)
print('GNS3_PREFLIGHT_VERIFIED:executionApi=MYSELF:requiredScopes=present')
PY2
}

run_remote() {
  local fn="$1"
  (cd "$work" && clasp run "$fn")
}

parse_canary() {
  python3 - "$1" <<'PY'
import re, sys
s=sys.argv[1]

def field(name, typ='str'):
    if typ == 'int':
        pats=[rf'"{re.escape(name)}"\s*:\s*(-?\d+)', rf'\b{re.escape(name)}\s*:\s*(-?\d+)']
    elif typ == 'bool':
        pats=[rf'"{re.escape(name)}"\s*:\s*(true|false)', rf'\b{re.escape(name)}\s*:\s*(true|false)']
    else:
        pats=[rf'"{re.escape(name)}"\s*:\s*"([^\"]+)"', rf"\b{re.escape(name)}\s*:\s*['\"]?([A-Za-z0-9_\-]+)"]
    for p in pats:
        m=re.search(p,s,re.I)
        if m: return m.group(1)
    return None
vals={
  'triggerCount':field('triggerCount','int'),
  'manifestCount':field('manifestCount','int'),
  'status':field('status'),
  'readback':field('readback'),
  'ok':field('ok','bool'),
}
for k,v in vals.items():
    print(f'{k}={v or ""}')
if vals['triggerCount'] is None or vals['manifestCount'] is None or vals['status'] is None or vals['readback'] is None:
    raise SystemExit(2)
PY
}

preflight_execution_api

canary_output="$(run_remote "$CANARY_FUNCTION" 2>&1)" || {
  printf '%s\n' "$canary_output" >&2
  echo "BLOCKED:CLASP_CANARY_EXECUTION_FAILED" >&2
  exit 22
}
printf '%s\n' "$canary_output"

parsed="$(parse_canary "$canary_output" 2>/dev/null)" || {
  echo "HELD:CANARY_RESULT_NOT_MACHINE_PARSEABLE_NO_REPAIR" >&2
  exit 23
}
eval "$parsed"

if [[ "$readback" != "VERIFIED" ]]; then
  echo "HELD:CANARY_PROOF_READBACK_NOT_VERIFIED:${readback:-MISSING}" >&2
  exit 28
fi
if ! [[ "$manifestCount" =~ ^[0-9]+$ ]] || (( manifestCount <= 0 )); then
  echo "HELD:CANARY_MANIFEST_INVALID:${manifestCount:-MISSING}" >&2
  exit 29
fi

if [[ "$triggerCount" == "1" ]]; then
  if [[ "$status" != "GNS3_CANARY_VERIFIED" || "$ok" != "true" ]]; then
    echo "HELD:SINGLETON_PRESENT_BUT_CANARY_NOT_VERIFIED:status=${status}:ok=${ok}" >&2
    exit 30
  fi
  echo "GNS3_RECOVERY_STOP:PRESERVE_EXISTING_SINGLETON:manifestCount=${manifestCount}:readback=VERIFIED"
  exit 0
fi

# A repair decision is allowed only from a canary whose own proof row was
# independently read back and whose task manifest is valid. The failed status
# is expected when trigger cardinality is not exactly one.
if [[ "$status" != "GNS3_CANARY_FAILED" ]]; then
  echo "HELD:NON_SINGLETON_WITH_UNEXPECTED_CANARY_STATUS:${status}" >&2
  exit 31
fi
if [[ "$MODE" != "repair-if-needed" ]]; then
  echo "GNS3_CANARY_REPAIR_REQUIRED:triggerCount=${triggerCount}:manifestCount=${manifestCount}:readback=VERIFIED"
  exit 24
fi

install_output="$(run_remote "$INSTALL_FUNCTION" 2>&1)" || {
  printf '%s\n' "$install_output" >&2
  echo "BLOCKED:GNS3_INSTALL_EXECUTION_FAILED" >&2
  exit 25
}
printf '%s\n' "$install_output"

verify_output="$(run_remote "$CANARY_FUNCTION" 2>&1)" || {
  printf '%s\n' "$verify_output" >&2
  echo "BLOCKED:POST_INSTALL_CANARY_FAILED" >&2
  exit 26
}
printf '%s\n' "$verify_output"
verify_parsed="$(parse_canary "$verify_output" 2>/dev/null)" || {
  echo "FAILED:POST_INSTALL_CANARY_NOT_MACHINE_PARSEABLE" >&2
  exit 32
}
eval "$verify_parsed"
if [[ "$triggerCount" != "1" || "$manifestCount" -le 0 || "$status" != "GNS3_CANARY_VERIFIED" || "$readback" != "VERIFIED" || "$ok" != "true" ]]; then
  echo "FAILED:POST_INSTALL_CANARY_CONTRACT_NOT_VERIFIED:triggerCount=${triggerCount}:manifestCount=${manifestCount}:status=${status}:readback=${readback}:ok=${ok}" >&2
  exit 27
fi

echo "GNS3_RECOVERY_VERIFIED:triggerCount=1:manifestCount=${manifestCount}:readback=VERIFIED"
