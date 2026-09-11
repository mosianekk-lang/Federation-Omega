#!/usr/bin/env python3
import argparse, json, pathlib
REQUIRED = [
    'FUSE-AIOS-CONSTITUTION.md','adr/0001-upstream-first-linux.md',
    'adr/0002-immutable-transactional-host.md','adr/0003-sovereign-trust-plane.md',
    'architecture/SOVEREIGNTY-DEPENDENCY-GRAPH.json',
    'architecture/CFBE-CAPABILITY-MATRIX.json','build/manifest.json'
]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ns=ap.parse_args(); root=pathlib.Path(ns.root)
    missing=[p for p in REQUIRED if not (root/p).is_file()]
    assert not missing, f'missing files: {missing}'
    graph=json.loads((root/'architecture/SOVEREIGNTY-DEPENDENCY-GRAPH.json').read_text())
    matrix=json.loads((root/'architecture/CFBE-CAPABILITY-MATRIX.json').read_text())
    manifest=json.loads((root/'build/manifest.json').read_text())
    assert graph['core_planes']['ai_inference']['local_cpu_path_required'] is True
    assert graph['core_planes']['agents']['host_root_default'] is False
    assert set(manifest['architectures']) == {'x86_64','arm64'}
    ids=[x['id'] for x in matrix['capabilities']]
    assert len(ids)==len(set(ids)) and len(ids)>=10
    print(json.dumps({'status':'PASS','required_files':len(REQUIRED),'capabilities':len(ids),'truth':'SOURCE_CANDIDATE_VALIDATED_ONLY'},sort_keys=True))
if __name__=='__main__': main()
