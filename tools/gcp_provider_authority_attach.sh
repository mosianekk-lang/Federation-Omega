#!/usr/bin/env bash
set -euo pipefail
umask 077

MODE="${1:---plan}"
PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
EXPECTED_PROJECT_NUMBER="${EXPECTED_PROJECT_NUMBER:-257649435135}"
EXPECTED_ACCOUNT="${EXPECTED_ACCOUNT:-mosianekk@gmail.com}"
APPLY_MARKER="ATTACH_GCP_READ_ONLY_V1"

required_services=(
  serviceusage.googleapis.com
  secretmanager.googleapis.com
  run.googleapis.com
  cloudbuild.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  sts.googleapis.com
)

need() {
  command -v "$1" >/dev/null || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}
need gcloud
need python3

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

[[ "$ACTIVE_ACCOUNT" == "$EXPECTED_ACCOUNT" ]] || {
  echo "Active Google account mismatch: $ACTIVE_ACCOUNT" >&2
  exit 3
}
[[ "$PROJECT_NUMBER" == "$EXPECTED_PROJECT_NUMBER" ]] || {
  echo "Google project-number mismatch: $PROJECT_NUMBER" >&2
  exit 4
}

list_states() {
  for service in "${required_services[@]}"; do
    state="$(gcloud services list --project="$PROJECT_ID" \
      --filter="config.name=${service}" --format='value(state)' | head -n1)"
    printf '%s\t%s\n' "$service" "${state:-DISABLED_OR_UNAVAILABLE}"
  done
}

case "$MODE" in
  --plan)
    echo "Account: $ACTIVE_ACCOUNT"
    echo "Project: $PROJECT_ID ($PROJECT_NUMBER)"
    list_states
    echo "No mutation performed."
    ;;
  --verify)
    list_states
    python3 "$(dirname "$0")/provider_metadata_probe.py" \
      "$(dirname "$0")/provider-metadata-receipt.json"
    ;;
  --apply)
    [[ "${FEDOMEGA_PROVIDER_AUTHORITY_APPLY:-}" == "$APPLY_MARKER" ]] || {
      echo "Exact FEDOMEGA_PROVIDER_AUTHORITY_APPLY marker required." >&2
      exit 5
    }
    gcloud services enable "${required_services[@]}" --project="$PROJECT_ID"
    "$0" --verify
    ;;
  *)
    echo "Usage: $0 [--plan|--verify|--apply]" >&2
    exit 2
    ;;
esac
