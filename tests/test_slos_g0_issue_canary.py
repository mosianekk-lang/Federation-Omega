from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'.github/workflows/fo-wif-semantic-canary.yml'
P=ROOT/'governance/github_airlock_policy.json'

def test_slos_g0_issue_canary_is_owner_only_read_only_and_pinned():
    w=W.read_text(encoding='utf-8')
    p=json.loads(P.read_text(encoding='utf-8'))
    assert "issues:" in w and "types: [opened]" in w
    assert "author_association == 'OWNER'" in w
    assert "[FO-DISPATCH] SLOS_G0_READ_ONLY_AUTH_CANARY" in w
    assert "contents: read" in w and "contents: write" not in w
    assert "id-token: write" in w
    assert "persist-credentials: false" in w
    for bad in ("git push","git commit","gcloud services enable","add-iam-policy-binding","secrets versions access"):
        assert bad not in w
    assert "bootstrap_github_wif.sh --verify" in w
    assert "bootstrap_gemini_gateway.sh --verify" in w
    assert "mutation_performed'] is False" in w
    assert ".github/workflows/fo-wif-semantic-canary.yml'" not in w
    path='.github/workflows/fo-wif-semantic-canary.yml'
    assert path in p['active_workflow_allowlist']
    assert path in p['oidc_workflow_allowlist']
    assert p['allowed_events'][path]==['issues']
    assert path in p['execution_quarantine']['keep_active']
    refs=re.findall(r'uses:\s*([^\s]+)',w)
    assert refs and all(re.search(r'@[0-9a-f]{40}$',r) for r in refs),refs
