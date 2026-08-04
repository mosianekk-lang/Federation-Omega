from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract-to')
    parser.add_argument('--run-tests', action='store_true')
    args = parser.parse_args()
    descriptor = json.loads((ROOT / 'release_descriptor.json').read_text())
    encoded = ''.join((ROOT / path).read_text().strip() for path in descriptor['chunk_paths'])
    archive = ROOT / descriptor['archive_name']
    archive.write_bytes(base64.b64decode(encoded, validate=True))
    assert sha256(archive) == descriptor['archive_sha256']
    with zipfile.ZipFile(archive) as zf:
        assert zf.testzip() is None
    target = Path(args.extract_to).resolve() if args.extract_to else Path(tempfile.mkdtemp(prefix='lbf-v2-'))
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text())
    assert manifest['version'] == descriptor['version']
    assert manifest['file_count'] == len(manifest['files'])
    for relative, expected in manifest['files'].items():
        path = target / relative
        assert path.is_file(), relative
        assert sha256(path) == expected['sha256'], relative
        assert path.stat().st_size == expected['bytes'], relative
    if args.run_tests:
        subprocess.run([sys.executable, '-m', 'compileall', '-q', str(target / 'live_bible_fabric')], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-build-isolation', '-e', str(target)], check=True)
        subprocess.run([sys.executable, '-m', 'pytest', '-q', str(target / 'tests')], check=True)
    print('LIVE_BIBLE_CAPTURE_FABRIC_V2_OK')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
