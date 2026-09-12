#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/out"
mkdir -p "${OUT}"
python3 "${ROOT}/tests/validate_candidate.py" --root "${ROOT}"
python3 - "$ROOT" "$OUT/build-receipt.json" <<'PY'
import hashlib, json, pathlib, platform, sys, datetime
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2])
files=[]
for p in sorted(root.rglob('*')):
    if p.is_file() and '/out/' not in p.as_posix() and not p.as_posix().endswith('.pyc'):
        files.append({"path":str(p.relative_to(root)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"size":p.stat().st_size})
receipt={"schema":"FUSE-AIOS-LOCAL-BUILD-RECEIPT-V1","candidate":"0.1.0","platform":platform.platform(),"python":platform.python_version(),"files":files,"truth":"SOURCE_CANDIDATE_VALIDATED_ONLY","generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding='utf-8')
print(out)
PY
sha256sum "${OUT}/build-receipt.json"
