from pathlib import Path
import re, sys
ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
  'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
  'google_api_key': re.compile(r'AIza[0-9A-Za-z_-]{30,}'),
  'github_token': re.compile(r'gh[pousr]_[0-9A-Za-z]{20,}'),
  'openai_key': re.compile(r'sk-(?:proj-)?[0-9A-Za-z_-]{20,}'),
}
findings=[]
for p in ROOT.rglob('*'):
    if not p.is_file() or '.git' in p.parts or p.name in {'production_status.json'}:
        continue
    if p.suffix.lower() in {'.zip','.png','.jpg','.jpeg','.pdf','.pyc'}:
        continue
    try: text=p.read_text(errors='ignore')
    except Exception: continue
    for name, rx in PATTERNS.items():
        if rx.search(text): findings.append({'file':str(p.relative_to(ROOT)),'pattern':name})
if findings:
    print(findings); sys.exit(1)
print('secret-scan: PASS')
