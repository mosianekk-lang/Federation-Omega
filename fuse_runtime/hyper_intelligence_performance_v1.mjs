export const HYPER_BINDING_SCHEMA='FUSE_HYPER_INTELLIGENCE_PERFORMANCE_BINDING_V1';
export const HYPER_BINDING_VERSION='1.0.0';

const clamp=(v,min=0,max=1)=>Math.max(min,Math.min(max,Number(v)));
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const arr=v=>Array.isArray(v)?v:[];

function substantial(prompt,result={}){
  const p=String(prompt||'');
  return p.trim().length>=24 ||
    result.execution_required===true ||
    /\b(build|create|deploy|finish|complete|audit|investigat|research|architect|harvest|benchmark|legal|security|production|runtime|system|agent|commercial)\b/i.test(p);
}
function highConsequence(prompt,result={}){
  return result.sensitive===true||result.effectful===true||
    /\b(legal|medical|health|financial|security|cyber|production|disciplin|arbitration|criminal|safety[- ]critical|external effect|deploy|publish|send|buy)\b/i.test(String(prompt||''));
}
function hyperClaim(prompt,result={}){
  return result.hyper_performance_claim===true||
    /\b(hyper[- ]performance|10x|ten[- ]x|market[- ]leading|best[- ]in[- ]market|dominant performance|superhuman|hyper[- ]intelligence)\b/i.test(String(prompt||''));
}

export function selectCognitiveDepth({prompt='',result={},meta={}}={}){
  const uncertainty=n(result.uncertainty_score,result.uncertainty_map?0.7:0);
  const repeated=n(result.same_semantic_failure_count,0);
  const unknownEffect=String(result.effect_state||'').toUpperCase()==='UNKNOWN'||result.unknown_effect===true;
  const consequential=highConsequence(prompt,result);
  const architectural=/\b(architecture|runtime|controller|scheduler|mission bus|authority|proof root|source mutation)\b/i.test(String(prompt||''));
  if(unknownEffect || repeated>=2 || (consequential&&(uncertainty>=0.5||architectural))) return 'FORMATION';
  if(consequential || uncertainty>=0.5 || architectural || String(meta.depth||'').toUpperCase()==='DEEP') return 'DEEP';
  if(substantial(prompt,result)) return 'ADAPTIVE';
  return 'FAST';
}

export function routeValue(route={}){
  const hard={
    authority:route.authority!==false,
    security:route.security!==false,
    privacy:route.privacy!==false,
    legality:route.legality!==false,
    truth:route.truth!==false,
    proof:route.proof!==false
  };
  if(!Object.values(hard).every(Boolean)) return {eligible:false,score:0,hard};
  const num=
    clamp(route.terminal_unlock??1,0.05,1)*
    clamp(route.correctness_probability??0.8,0.05,1)*
    clamp(route.current_callability??0.8,0.05,1)*
    clamp(route.proof_strength??0.8,0.05,1)*
    clamp(route.recovery_quality??0.8,0.05,1)*
    clamp(route.information_gain??0.5,0.05,1)*
    clamp(route.future_option_value??0.5,0.05,1)*
    clamp(route.privacy_score??1,0.05,1)*
    clamp(route.sovereignty??0.8,0.05,1);
  const den=
    Math.max(0.05,n(route.latency_cost,1))*
    Math.max(0.05,n(route.financial_cost,1))*
    Math.max(0.05,n(route.coordination_tax,1))*
    Math.max(0.05,n(route.failure_correlation,1))*
    Math.max(0.05,n(route.architecture_entropy,1))*
    Math.max(0.05,n(route.owner_burden,1));
  return {eligible:true,score:num/den,hard};
}

export function rankRoutes(routes=[]){
  return arr(routes).map((route,index)=>({route,index,...routeValue(route)}))
    .filter(x=>x.eligible)
    .sort((a,b)=>b.score-a.score||a.index-b.index);
}

function conflicts(a={},b={}){
  if(a.scope_known===false||b.scope_known===false) return true;
  if(a.touches_canonical_state||b.touches_canonical_state) return true;
  const aw=new Set(arr(a.write_scope)),bw=new Set(arr(b.write_scope));
  const ar=new Set(arr(a.read_scope)),br=new Set(arr(b.read_scope));
  const ae=new Set(arr(a.effect_scope)),be=new Set(arr(b.effect_scope));
  const intersects=(x,y)=>[...x].some(v=>y.has(v));
  return intersects(ae,be)||intersects(aw,bw)||intersects(aw,br)||intersects(bw,ar);
}

export function compileParallelWaves(nodes=[]){
  const waves=[];
  for(const node of arr(nodes)){
    let placed=false;
    for(const wave of waves){
      if(wave.every(existing=>!conflicts(node,existing))){
        wave.push(node); placed=true; break;
      }
    }
    if(!placed) waves.push([node]);
  }
  return waves;
}

export function performanceVerdict(performance={},cfg={}){
  const before=performance.before||performance.baseline||{};
  const after=performance.after||performance.observed||performance;
  const hasLatency=n(before.latency_ms,0)>0&&n(after.latency_ms,0)>0;
  const hasToolCalls=n(before.tool_calls,0)>0&&n(after.tool_calls,-1)>=0;
  const hasOwnerPrompts=n(before.owner_prompts,0)>0&&n(after.owner_prompts,-1)>=0;
  const latencySpeedup=hasLatency?n(before.latency_ms)/n(after.latency_ms):null;
  const toolReduction=hasToolCalls?1-(n(after.tool_calls)/n(before.tool_calls)):null;
  const ownerPromptReduction=hasOwnerPrompts?1-(n(after.owner_prompts)/n(before.owner_prompts)):null;
  const qualityNonnegative=performance.quality_nonnegative!==false &&
    (performance.quality_delta==null||n(performance.quality_delta)>=0);
  const falseGreens=n(performance.false_green_count,0);
  const unintendedWrites=n(performance.unintended_writes,0);
  const unchangedRetries=n(performance.unchanged_retries,0);
  const ownerRescues=n(performance.owner_rescues,0);
  const matched=performance.matched_benchmark===true||performance.matched===true;
  const floors={
    matched_benchmark:matched,
    latency_speedup:latencySpeedup!=null&&latencySpeedup>=n(cfg.latency_speedup_floor,1.5),
    tool_call_reduction:toolReduction==null||toolReduction>=n(cfg.tool_call_reduction_floor,0.2),
    owner_prompt_reduction:ownerPromptReduction==null||ownerPromptReduction>=n(cfg.owner_prompt_reduction_floor,0.5),
    quality_nonnegative:qualityNonnegative,
    false_green:falseGreens<=n(cfg.false_green_ceiling,0),
    unintended_writes:unintendedWrites===0,
    unchanged_retries:unchangedRetries<=n(cfg.unchanged_retry_ceiling,0),
    owner_rescues:ownerRescues<=n(cfg.owner_rescue_ceiling,0)
  };
  const verified=Object.values(floors).every(Boolean);
  return {
    matched_benchmark:matched,
    hyper_performance_verified:verified,
    state:verified?'HYPER_PERFORMANCE_VERIFIED':matched?'MATCHED_BENCHMARK_NONPROMOTING':'MEASUREMENT_ONLY',
    latency_speedup:latencySpeedup,
    tool_call_reduction:toolReduction,
    owner_prompt_reduction:ownerPromptReduction,
    floors
  };
}

function intelligenceEvidence(result={},meta={}){
  const challenge=arr(result.challengers).length>0||arr(result.acceptance_tests).length>0||result.independent_challenger?.verified===true;
  const world=!!result.world_model||!!result.mission_graph||!!result.capability_census||result.currentness?.checked===true;
  const uncertainty=!!result.uncertainty_map||result.uncertainty_score!=null||challenge;
  const causal=!!result.causal_graph||!!result.mission_graph||!!result.execution_dag;
  const future=!!result.future_envelope||!!result.next_action||result.recovery!=null||result.rollback===true;
  const voi=!!result.value_of_information||arr(result.source_refs).length>0||result.research_evidence?.verified===true||challenge;
  const collective=!!result.active_cognition_map||arr(result.challengers).length>0||arr(result.acceptance_tests).length>0;
  const safeParallel=!!result.parallel_waves||!!result.execution_dag||!!result.mission_graph;
  const routes=arr(result.route_candidates);
  const tournament=!!result.tournament||routes.length>1||arr(result.surface_portfolio?.selected).length>1||arr(result.challengers).length>0;
  const reuse=result.reuse_gate?.checked===true||result.existing_work_reused===true||result.historical_recall?.checked===true||meta.bootstrap_guard?.ok===true;
  const tenPass=meta.autonomous_improvement?.iterations_completed===10||
    meta.autonomous_improvement?.final_state==='TEN_ITERATIONS_COMPLETE_VERIFIED'||
    meta.bootstrap_guard?.ok===true;
  const falsification=challenge||result.falsification?.passed===true;
  const antiLoop=n(result.same_semantic_failure_count,0)<2||result.changed_mechanism===true||result.failure_handling?.changed_mechanism===true;
  return {world,uncertainty,causal,future,voi,collective,safeParallel,tournament,reuse,tenPass,falsification,antiLoop};
}

export function assessHyperBinding(prompt,result={},meta={},cfg={}){
  const enabled=cfg.enabled===true;
  if(!enabled) return {schema:HYPER_BINDING_SCHEMA,version:HYPER_BINDING_VERSION,required:false,pass:true,state:'DISABLED',issues:[]};
  const required=cfg.required_for_substantial_tasks!==false?substantial(prompt,result):true;
  const depth=selectCognitiveDepth({prompt,result,meta});
  const evidence=intelligenceEvidence(result,meta);
  const gates={
    adaptive_depth:depth!=='FAST'||!required,
    world_model:evidence.world,
    uncertainty_map:evidence.uncertainty,
    causal_reasoning:evidence.causal,
    future_envelope:evidence.future,
    value_of_information:evidence.voi,
    collective_cognition:evidence.collective,
    safe_parallelism:evidence.safeParallel,
    route_tournament:evidence.tournament,
    reuse_before_build:evidence.reuse,
    ten_pass_improvement:evidence.tenPass,
    adversarial_falsification:evidence.falsification,
    anti_loop_mechanism_change:evidence.antiLoop
  };
  const issues=required?Object.entries(gates).filter(([,v])=>!v).map(([k])=>k.toUpperCase()+'_NOT_EVIDENCED'):[];
  const perf=performanceVerdict(result.performance||{},cfg);
  const claim=hyperClaim(prompt,result);
  if(claim&&cfg.matched_benchmark_required_for_hyper_performance_claim!==false&&!perf.hyper_performance_verified){
    issues.push('HYPER_PERFORMANCE_CLAIM_LACKS_MATCHED_NONREGRESSION_PROOF');
  }
  const pass=issues.length===0;
  return {
    schema:HYPER_BINDING_SCHEMA,
    version:HYPER_BINDING_VERSION,
    required,
    pass,
    state:pass?(claim&&perf.hyper_performance_verified?'HYPER_INTELLIGENCE_AND_PERFORMANCE_VERIFIED':'HYPER_INTELLIGENCE_POLICY_PASS'):'HOLD_RECOMPILE',
    cognitive_depth:depth,
    gates,
    performance:perf,
    truth_boundary:{
      hyper_intelligence_means:'adaptive evidence-grounded collective reasoning and execution orchestration',
      hyper_intelligence_does_not_mean:'sentience omniscience supernatural foresight or unavailable access',
      hyper_performance_requires:'matched empirical nonregression proof before performance promotion'
    },
    issues
  };
}

export default {assessHyperBinding,selectCognitiveDepth,rankRoutes,compileParallelWaves,performanceVerdict};
