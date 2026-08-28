from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'.github/workflows/fo-wif-semantic-canary-v2.yml'
PW=ROOT/'.github/workflows/sovara-litellm-v2-3-provider-admission.yml'
P=ROOT/'governance/github_airlock_policy.json'
G=ROOT/'sovara/gemini/bootstrap_gateway.sh'

def test_slos_g0_issue_canary_is_owner_only_read_only_and_pinned():
    w=W.read_text(encoding='utf-8')
    p=json.loads(P.read_text(encoding='utf-8'))
    assert "issues:" in w and "types: [opened]" in w
    assert "author_association == 'OWNER'" in w
    assert "[FO-DISPATCH] SLOS_G0_READ_ONLY_AUTH_CANARY_V2" in w
    assert "contents: read" in w and "contents: write" not in w
    assert "id-token: write" in w
    assert "persist-credentials: false" in w
    for bad in ("git push","git commit","gcloud services enable","add-iam-policy-binding","secrets versions access"):
        assert bad not in w
    assert "bootstrap_github_wif.sh --verify" in w
    assert "bootstrap_gemini_gateway.sh --verify" in w
    assert "mutation_performed'] is False" in w
    path='.github/workflows/fo-wif-semantic-canary-v2.yml'
    assert path in p['active_workflow_allowlist']
    assert path in p['oidc_workflow_allowlist']
    assert p['allowed_events'][path]==['issues']
    assert path in p['execution_quarantine']['keep_active']
    assert p['provider_credential_reference_policy']['g0_identity_probe_workflow']==path
    refs=re.findall(r'uses:\s*([^\s]+)',w)
    assert refs and all(re.search(r'@[0-9a-f]{40}$',r) for r in refs),refs


def test_gemini_g1_only_enables_services_when_readback_reports_missing_apis():
    g=G.read_text(encoding='utf-8')
    provider_workflow=PW.read_text(encoding='utf-8')
    guard='if ((${#MISSING_APIS[@]} > 0)); then'
    enable='gcloud services enable "${MISSING_APIS[@]}" --project "$PROJECT_ID"'
    assert guard in g
    assert enable in g
    assert g.index(guard) < g.index(enable)
    assert './sovara/gemini/bootstrap_gateway.sh --plan' in provider_workflow
    assert './sovara/gemini/bootstrap_gateway.sh --apply' in provider_workflow
    assert './sovara/gemini/bootstrap_gateway.sh --verify' in provider_workflow
    assert './ops/bootstrap_gemini_gateway.sh --apply' not in provider_workflow
    # Never regress to the old unconditional fixed-list enable call that required
    # Service Usage Admin even when the plan had already proven all APIs active.
    assert 'gcloud services enable \\\n  aiplatform.googleapis.com' not in g
