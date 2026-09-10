from __future__ import annotations
import hashlib, json, os, platform, subprocess, sys, time, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(cmd):
    p=subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd":" ".join(cmd), "returncode":p.returncode, "stdout":p.stdout[-8000:], "stderr":p.stderr[-8000:]}

def tree_hash():
    h=hashlib.sha256()
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        excluded={'.git','.pytest_cache','__pycache__','.venv'}
        if p.is_file() and not any(part in excluded for part in rel.parts) and p.suffix != '.pyc' and p.name not in {'production_status.json','adversarial_court_receipt.json','software_manifest.json'}:
            h.update(str(rel).encode()); h.update(b'\0'); h.update(p.read_bytes())
    return h.hexdigest()

checks=[run([sys.executable,'-m','compileall','-q','src']), run([sys.executable,'-m','pytest','-q']), run([sys.executable,'scripts/validate_assets.py']), run([sys.executable,'scripts/secret_scan.py']), run([sys.executable,'scripts/build_software_manifest.py']), run([sys.executable,'benchmark/run_benchmark.py']), run([sys.executable,'scripts/run_adversarial_court.py']), run([sys.executable,'scripts/smoke_http.py'])]
status={
  "generated_at_epoch": time.time(),
  "python": platform.python_version(),
  "artifact_sha256": tree_hash(),
  "checks": checks,
  "local_reference_release_verified": all(c['returncode']==0 for c in checks),
  "local_http_readback_verified": checks[-1]['returncode']==0,
  "adversarial_court_verified_synthetic": checks[-2]['returncode']==0,
  "software_manifest_generated": checks[4]['returncode']==0,
  "terraform_cli_available": bool(shutil.which("terraform") or shutil.which("tofu")),
  "docker_cli_available": bool(shutil.which("docker")),
  "provider_deployment_verified": False,
  "provider_readback_verified": False,
  "ten_x_market_superiority_verified": False,
  "proof_note": "Provider and 10x claims remain false until independently measured/read back on their required surfaces."
}
(ROOT/'production_status.json').write_text(json.dumps(status, indent=2)+"\n")
print(json.dumps({k:v for k,v in status.items() if k!='checks'}, indent=2))
sys.exit(0 if status['local_reference_release_verified'] else 1)
