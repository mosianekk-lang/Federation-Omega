from __future__ import annotations
import hashlib, json, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
pyproject=tomllib.loads((ROOT/'pyproject.toml').read_text())
files=[]
for p in sorted((ROOT/'src').rglob('*.py')):
    files.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
manifest={
    'schema':'AEGIS_SOFTWARE_MANIFEST_V1',
    'name':pyproject['project']['name'],
    'version':pyproject['project']['version'],
    'python_requires':pyproject['project']['requires-python'],
    'dependencies':sorted(pyproject['project']['dependencies']),
    'source_files':files,
    'generated_runtime_receipt':False,
}
raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
manifest['manifest_sha256']=hashlib.sha256(raw).hexdigest()
(ROOT/'software_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps({'source_files':len(files),'manifest_sha256':manifest['manifest_sha256']},indent=2))
