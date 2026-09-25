const STOP=new Set(['the','and','for','with','this','that','user','requested','change','verify','verified','please','give','provide']);
function tokens(text){
  return new Set((String(text||'').toLowerCase().match(/[a-z0-9+#.-]+/g)||[]).filter(x=>x.length>2&&!STOP.has(x)));
}
function similarity(a,b){
  const A=tokens(a),B=tokens(b); let inter=0; for(const x of A)if(B.has(x))inter++;
  return inter/Math.max(1,new Set([...A,...B]).size);
}
function dim(required,pass,reason,evidence=null){
  if(!required)return {required:false,state:'NA',reason:null,evidence};
  return {required:true,state:pass?'PASS':'FAIL',reason:pass?null:reason,evidence};
}
function profile(prompt,trustContext){
  const p=String(prompt||'');
  const plan=/\b(plan|planning|recommend|compare|explain|outline|research|analyze|analyse|assess|design)\b/i.test(p);
  const exec=/\b(implement|build|deploy|repair|fix|refactor|create|execute|install|merge|publish|send|delete|update|modify|write|run|improve|upgrade|optimize|optimise|enhance|strengthen)\b/i.test(p);
  const execution_required=exec;
  const code_task=/\b(code|software|developer|function|class|api|bug|debug|refactor|repository|repo|pull request|mirror|bootstrap|algorithm|system|program|runtime|typescript|python|javascript|java|c#|php|shell|c\+\+|go|rust|hcl)\b/i.test(p);
  const performance_required=/\b(10x|performance|latency|cost|faster|speed|benchmark|throughput)\b/i.test(p);  const currentness_required=/\b(latest|current|today|tonight|yesterday|tomorrow|2026|up[- ]to[- ]date)\b/i.test(p);
  const power_request=/(best|ultimate|max(?:imum)?|strongest|powerful|10x|do all|finish|audit|harvest)/i.test(p);
  const trust=trustContext(p)||{};
  const sensitive=trust.sensitive_matter===true;
  const effectful=execution_required&&/\b(deploy|install|merge|publish|send|delete|update|modify|write|execute|run)\b/i.test(p);
  return {plan_only:plan&&!execution_required,execution_required,code_task,performance_required,currentness_required,power_request,sensitive,effectful,trust};
}
export function createMirrorV2({trustContext}){
  return {
    assess(prompt,result,meta={},cfg={}){
      const question=cfg.question||'Did I give the best and most powerful solution available to me as ChatGPT / AI assistant for representing OpenAI and what the user actually asked for?';
      if(cfg.enabled!==true)return {schema:'FUSE_OUTPUT_MIRROR_V2',enabled:false,question,state:'DISABLED',release_allowed:true,issues:[],dimensions:{}};
      const r=result&&typeof result==='object'?result:{};
      const p=String(prompt||'').trim(), objective=String(r.objective||'').trim(), pr=profile(p,trustContext);
      const tasks=Array.isArray(r.tasks)?r.tasks:[], manual=Array.isArray(r.manual_user_tasks)?r.manual_user_tasks:[];
      const hardBoundary=(r.completion_state==='HELD_WITH_EXACT_REASON'||r.completion_state==='PARTIAL_VERIFIED_CONTINUING')&&!!(r.reason||r.fallback_reason)&&!!r.next_action;
      const challenged=!!r.tournament||(Array.isArray(r.challengers)&&r.challengers.length>0)||(Array.isArray(r.acceptance_tests)&&r.acceptance_tests.length>0)||String(meta.depth||'').toUpperCase()==='DEEP'||r.reasoning_effort==='xhigh';
      const proof=r.proof||{}, tests=r.tests||{}, perf=r.performance||{}, current=r.currentness||{}, sg=r.sovereign_gate||{};
      const intentSim=objective?similarity(p,objective):0;
      const complete=r.completion_state==='COMPLETE_VERIFIED'||r.proof_state==='COMPLETE_VERIFIED';      const proofPass=!pr.execution_required||(complete&&(
        (proof.build===true&&proof.readback===true&&(pr.code_task?proof.tests===true:true))||
        r.verification?.complete===true||r.readback?.verified===true
      ));
      const designPass=!pr.code_task||!pr.execution_required||(
        r.change_batch==='small'&&r.maintainability!=='degraded'&&r.review_context!==false
      )||r.engineering_review?.design_code_health==='PASS';
      const testingPass=!pr.code_task||!pr.execution_required||(
        tests.status==='passed'&&tests.regression===true
      )||r.engineering_review?.testing==='PASS';
      const authPass=r.authority_proven===true||proof.authority===true||sg.authorized===true;
      const privacyPass=r.privacy_check===true||proof.privacy===true||sg.data_classification!==undefined;
      const securityPass=!pr.sensitive&&!pr.effectful||(authPass&&privacyPass&&(r.security_review===true||proof.security===true||sg.no_effect===true));
      const reliabilityPass=!pr.effectful||(r.rollback===true&&r.recovery===true&&r.effect_readback===true&&String(r.idempotency||'').toLowerCase()!=='unknown')||proof.recovery===true;
      const perfPass=!pr.performance_required||!pr.execution_required||(perf.measured===true&&perf.before!=null&&perf.after!=null);
      const currentPass=!pr.currentness_required||(current.checked===true&&!!current.observed_at&&Array.isArray(current.source_refs)&&current.source_refs.length>0)||(Array.isArray(r.source_refs)&&r.source_refs.length>0);
      const ownerPass=hardBoundary||(pr.execution_required?complete:(tasks.length>0&&!!r.next_action));
      const dimensions={
        intent_fidelity:dim(true,objective.length>0&&intentSim>=Number(cfg.intent_similarity_floor||0.18),'OUTPUT_DOES_NOT_MATCH_LATEST_OWNER_INTENT',{similarity:Number(intentSim.toFixed(3))}),
        execution_finality:dim(pr.execution_required,complete||hardBoundary,'EXECUTION_REQUEST_STOPPED_BEFORE_COMPLETE_VERIFIED',{completion_state:r.completion_state||null}),
        proof_evidence:dim(pr.execution_required||complete,proofPass||hardBoundary,'MATERIAL_COMPLETION_OR_EXECUTION_LACKS_REQUIRED_PROOF',proof),        design_code_health:dim(pr.code_task&&pr.execution_required,designPass||hardBoundary,'CODE_CHANGE_LACKS_SMALL_BATCH_OR_CODE_HEALTH_EVIDENCE',{change_batch:r.change_batch||null,maintainability:r.maintainability||null}),
        testing:dim(pr.code_task&&pr.execution_required,testingPass||hardBoundary,'CODE_CHANGE_LACKS_REGRESSION_TEST_PROOF',tests),
        security_privacy:dim(pr.sensitive||pr.effectful,securityPass||hardBoundary,'SENSITIVE_OR_EFFECTFUL_WORK_LACKS_AUTHORITY_PRIVACY_SECURITY_PROOF',{authority:authPass,privacy:privacyPass}),
        reliability_recovery:dim(pr.effectful,reliabilityPass||hardBoundary,'EFFECTFUL_WORK_LACKS_ROLLBACK_RECOVERY_OR_READBACK',{rollback:r.rollback||false,recovery:r.recovery||false,effect_readback:r.effect_readback||false,idempotency:r.idempotency||null}),
        performance_cost:dim(pr.performance_required&&pr.execution_required,perfPass||hardBoundary,'PERFORMANCE_OR_10X_REQUEST_LACKS_MEASURED_BEFORE_AFTER',perf),
        currentness_reproducibility:dim(pr.currentness_required,currentPass||hardBoundary,'CURRENT_OR_LATEST_REQUEST_LACKS_FRESH_SOURCE_READBACK',current),
        owner_value:dim(true,ownerPass&&!(r.machine_route_available===true&&manual.length>0),'OWNER_VALUE_NOT_DELIVERED_OR_MANUAL_TASK_LEFT_WHILE_MACHINE_ROUTE_EXISTS',{manual_user_tasks:manual.length})
      };
      const issues=Object.entries(dimensions).filter(([,v])=>v.required&&v.state==='FAIL').map(([k,v])=>k.toUpperCase()+':'+v.reason);
      if(pr.power_request&&!challenged&&!hardBoundary)issues.push('CHALLENGER_OR_ACCEPTANCE_COURT_REQUIRED');
      if(r.overclaim===true)issues.push('UNSUPPORTED_OVERCLAIM');
      const degraded=r.route==='LOCAL_FALLBACK'||r.completion_state==='PLANNED_LOCAL_FALLBACK';
      if(degraded&&!hardBoundary)issues.push('DEGRADED_ROUTE_WITHOUT_HARD_BOUNDARY');
      const release=issues.length===0;
      const requiredCount=Object.values(dimensions).filter(x=>x.required).length;
      const passedCount=Object.values(dimensions).filter(x=>x.required&&x.state==='PASS').length;      return {schema:'FUSE_OUTPUT_MIRROR_V2',enabled:true,version:String(cfg.version||'2.0.0'),question,
        state:release?(hardBoundary?'PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY':'PASS_BEST_AVAILABLE_RESULT'):'FAIL_RECOMPILE_OUTPUT',
        release_allowed:release,issues,dimensions,required_dimensions:requiredCount,passed_dimensions:passedCount,
        task_profile:pr,developer1000:cfg.developer1000||null,benchmark_court:cfg.benchmark_court||null,checked_at:new Date().toISOString()};
    }
  };
}