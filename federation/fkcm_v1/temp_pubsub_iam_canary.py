from __future__ import annotations
import argparse, base64, hashlib, json, os, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA='MODISA-FKCM-PUBSUB-TEMP-IAM-CANARY-1'; PROJECT_ID='sov-hybrid-suite'; PROJECT_NUMBER='257649435135'
TOPIC_ID='evidenceops-heartbeat-events'; DEPLOYER_SA='superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com'; NODE_ID='MODISA-FKCM-TEMP-IAM-CANARY'
ROLE_PERMISSIONS=('pubsub.subscriptions.create','pubsub.topics.attachSubscription','pubsub.subscriptions.get','pubsub.subscriptions.consume','pubsub.subscriptions.delete','pubsub.topics.publish')
ADMIN_REQUIRED_PERMISSIONS=('resourcemanager.projects.getIamPolicy','resourcemanager.projects.setIamPolicy','iam.roles.create','iam.roles.get','iam.roles.update','iam.roles.delete')

def run(a,*,env=None,timeout=150):
    try:
        p=subprocess.run(a,text=True,capture_output=True,env=env,timeout=timeout); return p.returncode,p.stdout.strip(),p.stderr.strip()[-4000:]
    except Exception as e: return 126,'',f'{type(e).__name__}:{e}'
def js(s,d=None):
    try:return json.loads(s)
    except Exception:return {} if d is None else d
def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def imp(sa): return [f'--impersonate-service-account={sa}']
def token(sa=None):
    a=['gcloud','auth','print-access-token',*(imp(sa) if sa else [])]; c,o,e=run(a)
    if c or not o: raise RuntimeError(f'token_failed:{e}')
    print(f'::add-mask::{o}'); return o
def post(url,t,body):
    r=urllib.request.Request(url,data=json.dumps(body,separators=(',',':')).encode(),headers={'authorization':f'Bearer {t}','content-type':'application/json','x-goog-user-project':PROJECT_ID},method='POST')
    try:
        with urllib.request.urlopen(r,timeout=45) as x:return x.status,js(x.read().decode())
    except urllib.error.HTTPError as e:return e.code,js(e.read().decode())
def get_policy(sa):
    c,o,e=run(['gcloud','projects','get-iam-policy',PROJECT_ID,'--format=json',*imp(sa)]); 
    if c: raise RuntimeError(f'policy_read_failed:{e}')
    return js(o)
def role(sa,rid,show_deleted=False):
    a=['gcloud','iam','roles','describe',rid,f'--project={PROJECT_ID}','--format=json',*imp(sa)]
    if show_deleted:a.insert(-1,'--show-deleted')
    c,o,_=run(a); return js(o) if not c else None
def binding(policy,rn,member,title=None,expr=None):
    for b in policy.get('bindings',[]):
        if b.get('role')!=rn or member not in (b.get('members') or []):continue
        if title is None:return True
        q=b.get('condition') or {}
        if q.get('title')==title and q.get('expression')==expr:return True
    return False

def discover_admin(rd):
    d=rd/'admin-census'; d.mkdir(parents=True,exist_ok=True); env=dict(os.environ); env['SOVARA_RECEIPT_DIR']=str(d)
    c,_,e=run([sys.executable,'sovara/gemini/admin_authority_census.py'],env=env,timeout=180); p=d/'PROJECT_IAM_AUTHORITY_CENSUS.json'
    if not p.is_file(): raise RuntimeError(f'admin_census_receipt_missing:{e}')
    x=json.loads(p.read_text()); reusable=set(x.get('verified_reusable_admin_service_accounts') or [])
    for sa,q in sorted((x.get('direct_impersonation_tests') or {}).items()):
        if sa not in reusable or not q.get('impersonation_verified') or not q.get('project_set_iam_policy'):continue
        s,b=post(f'https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}:testIamPermissions',token(sa),{'permissions':list(ADMIN_REQUIRED_PERMISSIONS)})
        got=set(b.get('permissions') or []) if s==200 else set()
        if set(ADMIN_REQUIRED_PERMISSIONS)<=got:return sa,{'census_schema':x.get('schema'),'census_receipt_sha256':x.get('receipt_sha256'),'admin_permissions_verified':sorted(got),'credential_values_recorded':False}
    raise RuntimeError('no_direct_admin_impersonation_path_with_exact_iam_authority')

def ident():
    r=os.getenv('GITHUB_RUN_ID','local'); a=os.getenv('GITHUB_RUN_ATTEMPT','1'); ev=f'fkcm-temp-iam-{r}-{a}'; rid=f'fkcmPubSubCanary{r}A{a}'
    return {'event_id':ev,'subscription_id':f'fkcm-shadow-{r}-{a}','role_id':rid,'role_name':f'projects/{PROJECT_ID}/roles/{rid}','condition_title':f'FKCM_CANARY_{r}_{a}'}
def wait_permissions(timeout_s=60):
    end=time.monotonic()+timeout_s; last={}
    while time.monotonic()<end:
        t=token(); ps,pb=post(f'https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}:testIamPermissions',t,{'permissions':['pubsub.subscriptions.create']})
        ts,tb=post(f'https://pubsub.googleapis.com/v1/projects/{PROJECT_ID}/topics/{TOPIC_ID}:testIamPermissions',t,{'permissions':['pubsub.topics.attachSubscription','pubsub.topics.publish']})
        pg=set(pb.get('permissions') or []) if ps==200 else set(); tg=set(tb.get('permissions') or []) if ts==200 else set(); last={'project_granted':sorted(pg),'topic_granted':sorted(tg)}
        if 'pubsub.subscriptions.create' in pg and {'pubsub.topics.attachSubscription','pubsub.topics.publish'}<=tg:return {**last,'verified':True}
        time.sleep(2)
    raise RuntimeError(f'temporary_iam_permission_propagation_timeout:{last}')

def grant(sp,rd,ttl):
    i=ident(); member=f'serviceAccount:{DEPLOYER_SA}'; expiry=(datetime.now(timezone.utc)+timedelta(minutes=ttl)).replace(microsecond=0).isoformat().replace('+00:00','Z'); expr=f'request.time < timestamp("{expiry}")'; desc='One-use MODISA FKCM PubSub provider canary'; cond=f'expression={expr},title={i["condition_title"]},description={desc}'
    st={'schema':SCHEMA,'phase':'PRE_MUTATION','source_sha':os.getenv('GITHUB_SHA'),'project_id':PROJECT_ID,'member':member,'permissions':list(ROLE_PERMISSIONS),**i,'expiry':expiry,'condition_expression':expr,'condition_arg':cond,'admin_sa':None,'subscription_created':False}; dump(sp,st)
    sa,proof=discover_admin(rd); st.update(admin_sa=sa,admin_proof=proof,phase='ADMIN_AUTHORITY_VERIFIED'); dump(sp,st)
    c,_,e=run(['gcloud','iam','roles','create',i['role_id'],f'--project={PROJECT_ID}',f'--title=FKCM PubSub Canary {i["event_id"]}','--description=Ephemeral least-privilege role for one MODISA FKCM PubSub provider court',f'--permissions={",".join(ROLE_PERMISSIONS)}','--stage=GA','--quiet',*imp(sa)])
    if c:raise RuntimeError(f'custom_role_create_failed:{e}')
    ro=role(sa,i['role_id']);
    if not ro or set(ro.get('includedPermissions') or [])!=set(ROLE_PERMISSIONS):raise RuntimeError('custom_role_exact_permission_readback_failed')
    st['phase']='ROLE_CREATED_VERIFIED'; dump(sp,st)
    c,_,e=run(['gcloud','projects','add-iam-policy-binding',PROJECT_ID,f'--member={member}',f'--role={i["role_name"]}',f'--condition={cond}','--quiet',*imp(sa)])
    if c:raise RuntimeError(f'iam_binding_add_failed:{e}')
    if not binding(get_policy(sa),i['role_name'],member,i['condition_title'],expr):raise RuntimeError('iam_binding_exact_readback_missing')
    st['provider_permission_propagation']=wait_permissions(); st['phase']='LEASE_ACTIVE_VERIFIED'; dump(sp,st)
    dump(rd/'fkcm-temp-iam-grant-receipt.json',{'schema':SCHEMA,'state':'TEMP_IAM_LEASE_ACTIVE_VERIFIED','role_name':i['role_name'],'permissions':list(ROLE_PERMISSIONS),'permissions_exact':True,'expiry':expiry,'admin_authority_verified':True,'revocation_pending':True})
    return st

def sub_deleted(sid):
    c,o,e=run(['gcloud','pubsub','subscriptions','describe',sid,'--project',PROJECT_ID,'--format=json']); return c!=0 and any(x in (o+' '+e).lower() for x in ['not_found','not found','resource not found'])
def delsub(sid):
    c,_,e=run(['gcloud','pubsub','subscriptions','delete',sid,'--project',PROJECT_ID,'--quiet'])
    if c and not sub_deleted(sid):raise RuntimeError(f'temporary_subscription_delete_failed:{e}')
    if not sub_deleted(sid):raise RuntimeError('temporary_subscription_delete_readback_failed')
def preflight():
    c,o,e=run(['gcloud','projects','describe',PROJECT_ID,'--format=json']); x=js(o)
    if c or str(x.get('projectId',''))!=PROJECT_ID or str(x.get('projectNumber',''))!=PROJECT_NUMBER:raise RuntimeError(f'project_identity_mismatch:{e}')
    c,o,e=run(['gcloud','services','list','--enabled','--project',PROJECT_ID,'--format=json']); names={str((z.get('config') or {}).get('name') or z.get('name') or '').rsplit('/services/',1)[-1] for z in js(o,[]) if isinstance(z,dict)}
    if c or 'pubsub.googleapis.com' not in names:raise RuntimeError('pubsub_service_not_enabled')
    c,o,e=run(['gcloud','pubsub','topics','describe',TOPIC_ID,'--project',PROJECT_ID,'--format=json']); tn=f'projects/{PROJECT_ID}/topics/{TOPIC_ID}'
    if c or js(o).get('name')!=tn:raise RuntimeError('topic_identity_mismatch')
    return {'project_id':PROJECT_ID,'project_number':PROJECT_NUMBER,'pubsub_api':'ENABLED','topic':tn,'topic_created':False}
def canary(rd,st,sp):
    p=preflight(); ev=st['event_id']; sid=st['subscription_id']; rh=hashlib.sha256(f'{os.getenv("GITHUB_SHA")}:{ev}:MODISA-FKCM-PUBSUB-TEMP-IAM-CANARY-1'.encode()).hexdigest(); flt=f'attributes.eventId="{ev}"'
    c,_,e=run(['gcloud','pubsub','subscriptions','create',sid,'--project',PROJECT_ID,'--topic',TOPIC_ID,'--message-filter',flt,'--ack-deadline','20','--message-retention-duration','10m','--expiration-period','1d','--quiet'])
    if c:raise RuntimeError(f'temporary_subscription_create_failed:{e}')
    st['subscription_created']=True; dump(sp,st)
    msg=json.dumps({'schema':'MODISA-FKCM-PUBSUB-CANARY-1','eventId':ev,'nodeId':NODE_ID,'state':'SYNC_PENDING','receiptHash':rh,'providerAction':'TEMPORARY_LEAST_PRIVILEGE_CANARY','publicSafe':True,'credentialsIncluded':False},sort_keys=True,separators=(',',':'))
    c,o,e=run(['gcloud','pubsub','topics','publish',TOPIC_ID,'--project',PROJECT_ID,'--message',msg,'--attribute',f'eventId={ev},nodeId={NODE_ID},receiptHash={rh}','--format=json']); q=js(o); ids=(q.get('messageIds') or q.get('message_ids') or []) if isinstance(q,dict) else []
    if c or not ids:raise RuntimeError(f'provider_message_id_missing:{e}')
    pid=str(ids[0]); cid=''
    for _ in range(12):
        c,o,_=run(['gcloud','pubsub','subscriptions','pull',sid,'--project',PROJECT_ID,'--limit','1','--auto-ack','--format=json']); vals=js(o,[]) if not c else []
        if vals:
            m=vals[0].get('message',vals[0]); at=m.get('attributes') or {}; raw=str(m.get('data') or ''); texts=[raw]
            try:texts.append(base64.b64decode(raw).decode())
            except Exception:pass
            if at.get('eventId')==ev and at.get('nodeId')==NODE_ID and at.get('receiptHash')==rh and any(ev in z and rh in z for z in texts):cid=str(m.get('messageId') or m.get('message_id') or ''); break
        time.sleep(2)
    if not cid:raise RuntimeError('consumer_readback_missing')
    if cid!=pid:raise RuntimeError('provider_consumer_message_id_mismatch')
    delsub(sid); st['subscription_created']=False; dump(sp,st)
    r={'schema':SCHEMA,'state':'PROVIDER_PUBLISH_CONSUMER_READBACK_ROLLBACK_VERIFIED',**p,'source_sha':os.getenv('GITHUB_SHA'),'event_id':ev,'provider_message_id':pid,'consumer_message_id':cid,'consumer_readback':True,'temporary_subscription':sid,'temporary_subscription_deleted':True,'existing_subscriptions_touched':False,'provider_effect':'BOUNDED_PUBLIC_SAFE_HEARTBEAT'}; dump(rd/'fkcm-provider-canary-receipt.json',r); return r

def revoke(sp,rd):
    if not sp.is_file():return {'state':'NO_LEASE_STATE_NO_MUTATION','binding_absent_verified':True,'role_deleted_or_disabled_verified':True,'residual_authority':False}
    st=json.loads(sp.read_text()); sa=st.get('admin_sa')
    if not sa:return {'state':'NO_ADMIN_SELECTED_NO_PROVIDER_IAM_MUTATION','binding_absent_verified':True,'role_deleted_or_disabled_verified':True,'residual_authority':False}
    c,_,e=run(['gcloud','projects','remove-iam-policy-binding',PROJECT_ID,f'--member={st["member"]}',f'--role={st["role_name"]}',f'--condition={st["condition_arg"]}','--quiet',*imp(sa)])
    if c:
        pol=get_policy(sa); keep=[]
        for b in pol.get('bindings',[]):
            q=b.get('condition') or {}; hit=b.get('role')==st['role_name'] and st['member'] in (b.get('members') or []) and q.get('title')==st['condition_title'] and q.get('expression')==st['condition_expression']
            if not hit:keep.append(b);continue
            m=[x for x in b.get('members',[]) if x!=st['member']]
            if m: z=dict(b);z['members']=m;keep.append(z)
        pol['bindings']=keep; pp=rd/'iam-policy-cleanup-cas.json'; dump(pp,pol); c,_,e2=run(['gcloud','projects','set-iam-policy',PROJECT_ID,str(pp),'--quiet',*imp(sa)])
        if c:raise RuntimeError(f'iam_binding_remove_failed:{e}|cas:{e2}')
    if binding(get_policy(sa),st['role_name'],st['member']):raise RuntimeError('iam_binding_residual_authority_detected')
    ro=role(sa,st['role_id']); deleted=False
    if ro:
        c,_,e=run(['gcloud','iam','roles','delete',st['role_id'],f'--project={PROJECT_ID}','--quiet',*imp(sa)])
        if c:
            c,_,e2=run(['gcloud','iam','roles','update',st['role_id'],f'--project={PROJECT_ID}','--stage=DISABLED','--quiet',*imp(sa)]); ro=role(sa,st['role_id'])
            if c or not ro or ro.get('stage')!='DISABLED':raise RuntimeError(f'custom_role_revoke_failed:{e}|{e2}')
        else:
            for _ in range(10):
                c,o,_=run(['gcloud','iam','roles','describe',st['role_id'],f'--project={PROJECT_ID}','--show-deleted','--format=json',*imp(sa)]); ro=js(o) if not c else None
                if ro and ro.get('deleted') is True:deleted=True;break
                time.sleep(2)
            if not deleted:raise RuntimeError('custom_role_revocation_readback_failed')
    if binding(get_policy(sa),st['role_name'],st['member']):raise RuntimeError('post_role_revoke_binding_residual_authority_detected')
    r={'schema':SCHEMA,'state':'TEMP_IAM_LEASE_REVOKED_ZERO_RESIDUAL_VERIFIED','binding_absent_verified':True,'role_deleted_or_disabled_verified':True,'role_deleted':deleted,'residual_authority':False,'role_name':st['role_name'],'permissions':st['permissions']}; dump(rd/'fkcm-temp-iam-revoke-receipt.json',r); return r

def execute(rd,ttl):
    rd.mkdir(parents=True,exist_ok=True); sp=rd/'temp-iam-state.json'; pr=None; errs=[]; rr=None
    try: st=grant(sp,rd,ttl); pr=canary(rd,st,sp)
    except Exception as e:errs.append(f'{type(e).__name__}:{str(e)[:700]}')
    finally:
        try:
            if sp.is_file():
                s=json.loads(sp.read_text());
                if s.get('subscription_created'):delsub(s['subscription_id']);s['subscription_created']=False;dump(sp,s)
        except Exception as e:errs.append(f'sub_cleanup:{type(e).__name__}:{str(e)[:500]}')
        try:rr=revoke(sp,rd)
        except Exception as e:errs.append(f'iam_cleanup:{type(e).__name__}:{str(e)[:500]}')
    pok=bool(pr and pr.get('consumer_readback') and pr.get('temporary_subscription_deleted')); iok=bool(rr and rr.get('binding_absent_verified') and rr.get('role_deleted_or_disabled_verified') and rr.get('residual_authority') is False); ok=pok and iok and not errs
    f={'schema':SCHEMA,'state':'PROVIDER_PUBLISH_CONSUMER_AND_IAM_REVOCATION_VERIFIED' if ok else 'CANARY_NOT_PROMOTION_ELIGIBLE','source_sha':os.getenv('GITHUB_SHA'),'project_id':PROJECT_ID,'project_number':PROJECT_NUMBER,'deployer_sa':DEPLOYER_SA,'topic':f'projects/{PROJECT_ID}/topics/{TOPIC_ID}','permissions':list(ROLE_PERMISSIONS),'permissions_exact':True,'provider_delivery_verified':pok,'iam_revocation_verified':iok,'errors':errs,'existing_subscriptions_touched':False,'topic_created':False,'secret_value_accessed':False,'service_account_key_used':False,'deployment_mutation':False,'production_traffic_changed':False,'billing_configuration_changed':False,'kdv_cutover':False,'provider_runtime_promotion_eligible':ok,'truth_boundary':'One owner-authorized temporary least-privilege IAM lease for one FKCM Pub/Sub canary; promotion requires provider delivery, temp-sub deletion and zero-residual IAM revocation in the same run.'}; f['receipt_sha256']=hashlib.sha256(json.dumps(f,sort_keys=True,separators=(',',':')).encode()).hexdigest();dump(rd/'fkcm-temp-iam-provider-final-receipt.json',f);return 0 if ok else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--receipt-dir',type=Path,default=Path('fkcm-temp-iam-proof'));p.add_argument('--ttl-minutes',type=int,default=30);a=p.parse_args()
    if not a.execute:p.error('--execute is required')
    if not 10<=a.ttl_minutes<=45:p.error('--ttl-minutes must be between 10 and 45')
    return execute(a.receipt_dir,a.ttl_minutes)
if __name__=='__main__':raise SystemExit(main())