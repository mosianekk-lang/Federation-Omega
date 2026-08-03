from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('--descriptor', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    archive = Path(args.archive).resolve()
    descriptor = json.loads(Path(args.descriptor).read_text())
    checks: dict[str, bool] = {
        'archive_name': archive.name == descriptor['artifact'],
        'archive_size': archive.stat().st_size == descriptor['archive_bytes'],
        'archive_sha256': sha256(archive) == descriptor['archive_sha256'],
    }
    with zipfile.ZipFile(archive) as zf:
        checks['zip_integrity'] = zf.testzip() is None
        roots = {Path(name).parts[0] for name in zf.namelist() if name and not name.endswith('/')}
        checks['single_root'] = len(roots) == 1
        root = next(iter(roots))
        manifest_bytes = zf.read(f'{root}/SOURCE_MANIFEST.json')
        manifest = json.loads(manifest_bytes)
        checks['manifest_version'] = manifest.get('version') == descriptor['version']
        checks['manifest_sha256'] = hashlib.sha256(manifest_bytes).hexdigest() == descriptor['source_manifest_sha256']
        mismatches = []
        for item in manifest['entries']:
            member = f"{root}/{item['path']}"
            try:
                data = zf.read(member)
            except KeyError:
                mismatches.append({'path': item['path'], 'state': 'MISSING'})
                continue
            observed = hashlib.sha256(data).hexdigest()
            if observed != item['sha256'] or len(data) != item['bytes']:
                mismatches.append({'path': item['path'], 'expected': item['sha256'], 'observed': observed, 'bytes': len(data)})
        checks['manifest_entries'] = not mismatches
        wheel_member = f"{root}/dist/{descriptor['wheel_name']}"
        wheel = zf.read(wheel_member)
        checks['wheel_sha256'] = hashlib.sha256(wheel).hexdigest() == descriptor['wheel_sha256']
    passed = all(checks.values())
    receipt = {
        'schema':'OMEGAMAX_GITHUB_EXACT_ARCHIVE_PREFLIGHT_V1',
        'version':descriptor['version'],
        'archive':archive.name,
        'checks':checks,
        'manifest_mismatches':mismatches,
        'passed':passed,
        'external_effects':0,
        'truth_boundary':descriptor['truth_boundary'],
    }
    Path(args.output).write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    if not passed:
        raise SystemExit(1)
    print(json.dumps(receipt,indent=2,sort_keys=True))


if __name__ == '__main__':
    main()
