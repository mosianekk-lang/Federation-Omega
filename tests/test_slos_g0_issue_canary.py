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
    # G0 proves keyless identity without requiring G2/G3 deployment privileges.
    assert "bootstrap_github_wif.sh --plan" in w
    assert "bootstrap_github_wif.sh --verify" not in w
    assert "bootstrap_gemini_gateway.sh --plan" in w
    assert "bootstrap_gemini_gateway.sh --verify" not in w
    assert "WIF_IDENTITY_VERIFIED" in w
    assert "GITHUB_WIF_ADC_TRANSPORT_VERIFIED" in w
    assert "WORKLOAD_IDENTITY_VERIFIED" in w
    assert "fhu_047_workload_identity_proven':True" in w
    assert "identity_verified_independent_of_deploy_roles':True" in w
    assert "deployment_readiness_proven" in w
    assert "security_hardening_complete" in w
    assert "long_lived_service_account_key_used':False" in w
    assert "mutation_performed':False" in w
    assert "provider_effect_executed':False" in w
    path='.github/workflows/fo-wif-semantic-canary-v2.yml'
    assert path in p['active_workflow_allowlist']
    assert path in p['oidc_workflow_allowlist']
    assert p['allowed_events'][path]==['issues']
    assert path in p['execution_quarantine']['keep_active']
    assert p['provider_credential_reference_policy']['g0_identity_probe_workflow']==path
    refs=re.findall(r'uses:\s*([^\s]+)',w)
    assert refs and all(re.search(r'@[0-9a-f]{40}$',r) for r in refs),refs


def test_g0_identity_receipt_preserves_security_and_deployment_gaps():
    w=W.read_text(encoding='utf-8')
    # A working OIDC/WIF exchange cannot silently certify stronger deployment state.
    assert "provider_attribute_condition_ref_scope" in w
    assert "provider_attribute_mapping" in w
    assert "cloud_run_developer_role" in w
    assert "cloud_run_invoker_role" in w
    assert "artifact_registry_writer_role" in w
    assert "gemini_deployment_readiness_gaps" in w
    assert "gemini_deployment_ready" in w
    # The actual credential file must be external-account WIF and service-account bound.
    assert "cred.get('type')=='external_account'" in w
    assert "service_account_impersonation_url" in w
    assert "WIF_PROVIDER" in w
    assert "DEPLOYER_SA" in w


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
