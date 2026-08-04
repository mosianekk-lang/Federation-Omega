from __future__ import annotations
import argparse, json
from pathlib import Path
from authority_snapshot import digest

def load(p: Path)->dict: return json.loads(p.read_text(encoding="utf-8"))

def prove(output: Path)->dict:
    root=Path(__file__).resolve().parent
    c=load(root/'provider_dispatch_outcome_reconciliation_checkpoint.json')
    p=load(root/'canonical_commercial_api_effective_v14.json')
    pe=load(root/'programme_effective_v14.json')
    programme=load(root/'programme.json')
    inst=load(root/'institution_reconciliation_checkpoint.json')
    stages={x['id']:x for x in programme['stages']}
    proof=c['operational_proof_gate']; drive=c['google_drive_release']; truth=c['commercial_truth']; owner=c['owner_authority']
    checks={
      'release_status_verified': c['status']=='PROVIDER_DISPATCH_OUTCOME_RECONCILIATION_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED',
      'implementation_bound': c['implementation_release']=={'implementation_pull_request':150,'implementation_head':'6f61c5c7b654d70ec45fff3976f200259a76eb1a','merge_commit':'6afd09e31dcea910f4e64de59ca776aae834d261','merged':True},
      'provider_proof_bound': proof['workflow_run']==30913614473 and proof['workflow_job']==92006113662 and proof['artifact_id']==8894094769 and proof['artifact_digest']=='sha256:8674a3e2a53e046270a1b4ee1b9ec2fb6c6e88a0430c53fc8f97960d3a6d27a4' and proof['checks_required']==12 and proof['checks_failed']==0 and proof['job_steps_readback_verified'] is True,
      'local_controls_only': proof['durable_submission_boundary']=='PROVIDER_NATIVE_CI_VERIFIED' and proof['unknown_outcome_quarantine']=='PROVIDER_NATIVE_CI_VERIFIED' and proof['mock_provider_reconciliation_conformance']=='PROVIDER_NATIVE_CI_VERIFIED' and proof['provider_native_reconciliation']=='PROVIDER_PROOF_REQUIRED' and proof['external_mutation_performed'] is False,
      'regressions_recorded': len(c['final_head_regression_runs'])==31 and all(isinstance(v,int) and v>0 for v in c['final_head_regression_runs'].values()),
      'drive_readback_bound': drive['file_id']=='1t41v-CbmN4yALeo-NsENCMWQNF_LdGw5vOBrINLm4UA' and drive['readback_verified'] is True and drive['shared'] is False and drive['owner']=='mosianekk@gmail.com' and drive['export_size_bytes']==6519 and drive['export_sha256']=='6fe1f422eebbafc762028b8bcbeb003b20200b245d4f8cdd9c13d95054f63641',
      'dependency_order': c['candidate_projection']['stage_scope']==['C03','C06','C07','C11','C14','C15'] and c['dependency_checkpoint']['programme_dependency_order_verified'] is True,
      'effective_api': p['capability_revision']=='AO-COMMERCIAL-PROVIDER-DISPATCH-OUTCOME-RECONCILIATION-V14' and p['canonical_class']=='OutcomeReconciledProviderDispatchCommercialControlPlane' and p['controls']['provider_native_reconciliation']=='PROVIDER_PROOF_REQUIRED',
      'programme_maturity_updated': pe['latest_verified_capability']==p['capability_revision'] and pe['latest_operational_receipt']['artifact_id']==proof['artifact_id'] and pe['external_maturity_gates_advanced'] is False,
      'service_first': pe['service_enabled_platform_prioritised'] is True and pe['self_service_saas_held'] is True and 'service-enabled platform' in programme['objective'],
      'canonical_gates_open': programme['canonical_status']=='COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN' and stages['C11']['status']=='SERVICE_ENABLED_PLATFORM_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_SELF_SERVICE_HELD' and stages['C15']['status']=='COMMERCIAL_READINESS_VERIFIED_CANONICAL_PROVIDER_ROUTE_ALIGNED_EXTERNAL_MATURITY_GATES_OPEN',
      'institution_preserved': c['institution_projection']==inst['institution_projection'],
      'external_gates_false': all(v is False for v in c['external_gates'].values()),
      'commercial_claims_false': truth['verified_live_revenue_events']==0 and truth['payment_provider_operation_proven'] is False and truth['cloud_run_operation_proven'] is False and truth['provider_native_reconciliation_proven'] is False and truth['distributed_provider_exactly_once_proven'] is False and truth['full_commercial_maturity'] is False,
      'owner_authority_preserved': owner=={'financial_commitments':'OWNER_RESERVED','contracts':'OWNER_RESERVED','external_communications':'OWNER_RESERVED','consequential_releases':'OWNER_RESERVED','revenue_recognition':'OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED'} }
    receipt={'control_id':'AO-COMMERCIAL-PROVIDER-DISPATCH-OUTCOME-RECONCILIATION-V14-RELEASE','status':c['status'],'stage_scope':c['candidate_projection']['stage_scope'],'implementation_release':c['implementation_release'],'provider_proof':proof,'google_drive_release':drive,'programme_maturity':pe,'checks':checks,'checks_required':len(checks),'checks_failed':sum(not x for x in checks.values()),'commercial_truth':truth,'owner_authority':owner,'external_gate_effect':'UNCHANGED'}
    receipt['receipt_sha256']=digest(receipt)
    if receipt['checks_failed']: raise RuntimeError('v14 release proof failed')
    output.mkdir(parents=True,exist_ok=True)
    (output/'provider-dispatch-outcome-reconciliation-release-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return receipt

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=Path('artifacts')); a=ap.parse_args(); print(json.dumps(prove(a.output),indent=2,sort_keys=True))
if __name__=='__main__': main()
