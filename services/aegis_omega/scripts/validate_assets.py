from pathlib import Path
import json, tomllib, sys
ROOT=Path(__file__).resolve().parents[1]
json.load(open(ROOT/'apps_script/appsscript.json'))
tomllib.loads((ROOT/'pyproject.toml').read_text())
cb=(ROOT/'cloudbuild.yaml').read_text()
for token in ['verify_release.py','docker','build']:
    assert token in cb, token
assert 'gcloud run deploy' not in cb
assert '--allow-unauthenticated' not in cb
for p in (ROOT/'infra/gcp').glob('*.tf'):
    s=p.read_text()
    assert s.count('{') == s.count('}'), f'unbalanced braces: {p}'
for required in ['run.googleapis.com','pubsub.googleapis.com','firestore.googleapis.com','secretmanager.googleapis.com','storage.googleapis.com']:
    assert required in (ROOT/'infra/gcp/main.tf').read_text(), required
print('asset-validation: PASS (structural; terraform CLI validation is a separate provider/tool gate)')

for required_path in ['src/aegis_omega/adversarial/twin.py','src/aegis_omega/adversarial/immune_graph.py','src/aegis_omega/adversarial/neural_sentinel.py','src/aegis_omega/adversarial/evolution_tournament.py','src/aegis_omega/evidence_chain.py']:
    assert (ROOT/required_path).is_file(), required_path

# Direct dependency drift must fail closed for production source.
project=tomllib.loads((ROOT/'pyproject.toml').read_text())
for dep in project['project']['dependencies']:
    assert '==' in dep and '>=' not in dep and '~=' not in dep, f'unpinned direct dependency: {dep}'
for dep in project['build-system']['requires']:
    assert '==' in dep and '>=' not in dep and '~=' not in dep, f'unpinned build dependency: {dep}'
for dep in project['project']['optional-dependencies']['dev']:
    assert '==' in dep and '>=' not in dep and '~=' not in dep, f'unpinned dev dependency: {dep}'
