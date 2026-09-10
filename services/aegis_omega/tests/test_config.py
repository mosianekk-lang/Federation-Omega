import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'src'
def _env(extra_env,drop_secret=False):
    env=os.environ.copy();
    if drop_secret: env.pop('AEGIS_HMAC_SECRET',None)
    env.update(extra_env); existing=env.get('PYTHONPATH',''); env['PYTHONPATH']=str(SRC)+(os.pathsep+existing if existing else ''); return env
def _import_config(extra_env):
    return subprocess.run([sys.executable,'-c',"import aegis_omega.config; print('ok')"],env=_env(extra_env),text=True,capture_output=True)
def test_production_rejects_development_hmac_fallback():
    proc=subprocess.run([sys.executable,'-c','import aegis_omega.config'],env=_env({'AEGIS_ENV':'production'},drop_secret=True),text=True,capture_output=True)
    assert proc.returncode !=0 and 'production start refused' in proc.stderr
def test_production_accepts_strong_injected_hmac_secret():
    proc=_import_config({'AEGIS_ENV':'production','AEGIS_HMAC_SECRET':'0123456789abcdef0123456789abcdef'}); assert proc.returncode==0; assert proc.stdout.strip()=='ok'
