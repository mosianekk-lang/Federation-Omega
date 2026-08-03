#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
REGION="${REGION:-africa-south1}"
SERVICE="${SERVICE:-fo-transcription-bridge}"
CASE_ID="${CASE_ID:-MPMB298-26}"
LANGUAGE_CODES="${LANGUAGE_CODES:-en-ZA,en-US}"
MODEL="${MODEL:-chirp_3}"
POLL_SECONDS="${POLL_SECONDS:-30}"

usage() {
  cat <<'USAGE'
Usage:
  ops/fo_transcription_client.sh AUDIO_FILE [OUTPUT_DIRECTORY]

Environment overrides:
  PROJECT_ID, REGION, SERVICE, CASE_ID, LANGUAGE_CODES, MODEL, POLL_SECONDS

The caller must already be authenticated with gcloud and authorized to invoke the
private Cloud Run service and read the private output bucket.
USAGE
}

[[ $# -ge 1 ]] || { usage; exit 2; }
AUDIO_FILE="$1"
OUTPUT_DIRECTORY="${2:-./fo-transcription-output}"
[[ -f "$AUDIO_FILE" ]] || { echo "Audio file not found: $AUDIO_FILE" >&2; exit 2; }

command -v gcloud >/dev/null || { echo "gcloud is required" >&2; exit 2; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 2; }

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
[[ -n "$SERVICE_URL" ]] || { echo "Cloud Run service URL could not be resolved" >&2; exit 3; }
TOKEN="$(gcloud auth print-identity-token --audiences="$SERVICE_URL")"
SIZE_BYTES="$(python3 - "$AUDIO_FILE" <<'PY'
import os, sys
print(os.path.getsize(sys.argv[1]))
PY
)"
CONTENT_TYPE="$(python3 - "$AUDIO_FILE" <<'PY'
import mimetypes, sys
print(mimetypes.guess_type(sys.argv[1])[0] or 'application/octet-stream')
PY
)"
FILENAME="$(basename "$AUDIO_FILE")"

CREATE_BODY="$(python3 - "$CASE_ID" "$FILENAME" "$CONTENT_TYPE" "$SIZE_BYTES" "$LANGUAGE_CODES" "$MODEL" <<'PY'
import json, sys
print(json.dumps({
  'case_id': sys.argv[1],
  'filename': sys.argv[2],
  'content_type': sys.argv[3],
  'size_bytes': int(sys.argv[4]),
  'language_codes': [x.strip() for x in sys.argv[5].split(',') if x.strip()],
  'model': sys.argv[6],
}))
PY
)"

CREATE_RESPONSE="$(curl --fail --silent --show-error \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "$CREATE_BODY" \
  "$SERVICE_URL/v1/uploads")"

readarray -t UPLOAD_FIELDS < <(python3 - "$CREATE_RESPONSE" <<'PY'
import json, sys
obj=json.loads(sys.argv[1])
print(obj['job_id'])
print(obj['upload']['url'])
print(obj['upload']['headers']['Content-Type'])
PY
)
JOB_ID="${UPLOAD_FIELDS[0]}"
UPLOAD_URL="${UPLOAD_FIELDS[1]}"
UPLOAD_CONTENT_TYPE="${UPLOAD_FIELDS[2]}"

echo "Uploading original audio for job $JOB_ID..."
curl --fail --silent --show-error \
  -X PUT \
  -H "Content-Type: $UPLOAD_CONTENT_TYPE" \
  --data-binary "@$AUDIO_FILE" \
  "$UPLOAD_URL" >/dev/null

TOKEN="$(gcloud auth print-identity-token --audiences="$SERVICE_URL")"
curl --fail --silent --show-error \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}' \
  "$SERVICE_URL/v1/jobs/$JOB_ID/start" >/dev/null

echo "Transcription job started: $JOB_ID"
while true; do
  sleep "$POLL_SECONDS"
  TOKEN="$(gcloud auth print-identity-token --audiences="$SERVICE_URL")"
  STATUS_RESPONSE="$(curl --fail --silent --show-error \
    -H "Authorization: Bearer $TOKEN" \
    "$SERVICE_URL/v1/jobs/$JOB_ID")"
  STATUS="$(python3 - "$STATUS_RESPONSE" <<'PY'
import json, sys
print(json.loads(sys.argv[1]).get('status', 'UNKNOWN'))
PY
)"
  echo "Status: $STATUS"
  case "$STATUS" in
    COMPLETED) break ;;
    FAILED)
      python3 -m json.tool <<<"$STATUS_RESPONSE"
      exit 4
      ;;
  esac
done

mkdir -p "$OUTPUT_DIRECTORY/$JOB_ID"
python3 -m json.tool <<<"$STATUS_RESPONSE" > "$OUTPUT_DIRECTORY/$JOB_ID/job.json"

python3 - "$STATUS_RESPONSE" "$OUTPUT_DIRECTORY/$JOB_ID" <<'PY'
import json, os, subprocess, sys
job=json.loads(sys.argv[1])
out=sys.argv[2]
for name, uri in (job.get('artifacts') or {}).items():
    if not uri.startswith('gs://'):
        continue
    suffix = {
        'txt': 'transcript.txt',
        'srt': 'transcript.srt',
        'vtt': 'transcript.vtt',
        'json': 'transcript.json',
        'manifest': 'evidence-manifest.json',
        'receipt': 'completion-receipt.json',
    }.get(name, os.path.basename(uri))
    subprocess.run(['gcloud', 'storage', 'cp', uri, os.path.join(out, suffix)], check=True)
print(out)
PY

echo "Completed. Local outputs: $OUTPUT_DIRECTORY/$JOB_ID"
