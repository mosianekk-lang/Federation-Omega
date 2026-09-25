export const HYPER_BINDING_SCHEMA='FUSE_HYPER_INTELLIGENCE_PERFORMANCE_BINDING_V1';
export const HYPER_BINDING_VERSION='2.0.0';
export const KERNEL_HOOK_SCHEMA='FUSE_SOVEREIGN_ADAPTIVE_COGNITION_HOOK_V2';

const clamp=(v,min=0,max=1)=>Math.max(min,Math.min(max,Number(v)));
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const arr=v=>Array.isArray(v)?v:[];
const text=v=>String(v??'').trim();
const upper=v=>text(v).toUpperCase();
const uniq=v=>[...new Set(arr(v).map(x=>String(x)))];

function substantial(prompt,result={}){
  const p=text(prompt);
  return p.length>=24 || result.execution_required===true ||
    /\b(build|create|deploy|finish|complete|audit|investigat|research|architect|harvest|benchmark|legal|security|production|runtime|system|agent|commercial|integrate|kernel|source|effect)\b/i.test(p);
}
function highConsequence(prompt,result={}){
  return result.sensitive===true||result.effectful===true||result.irreversible===true||
    /\b(legal|medical|health|financial|security|cyber|production|disciplin|arbitration|criminal|safety[- ]critical|external effect|deploy|publish|send|buy|merge|delete|iam|credential)\b/i.test(text(prompt));
}
function hyperClaim(prompt,result={}){
  return result.hyper_performance_claim===true||
    /\b(hyper[- ]performance|10x|ten[- ]x|market[- ]leading|best[- ]in[- ]market|dominant performance|superhuman|hyper[- ]intelligence|agi)\b/i.test(text(prompt));
}

export function compileOwnerIntent(input={}){
  const requestedEffects=uniq(input.requested_effects||input.requestedEffects||[]).map(upper);
  const targetScope=uniq(input.target_scope||input.targetScope||[]);
  return {
    schema:'FUSE_OWNER_INTENT_V2',
    literal_objective:text(input.literal_objective||input.objective||input.prompt),
    requested_output:text(input.requested_output||input.output),
    success_condition:text(input.success_condition||input.terminal_condition),
    constraints:uniq(input.constraints||[]),
    prohibited_effects:uniq(input.prohibited_effects||[]).map(upper),
    requested_effects:requestedEffects,
    recurrence_requested:input.recurrence_requested===true,
    target_scope:targetScope,
    scope_locked:input.scope_locked===true,
    owner_burden_target:text(input.owner_burden_target||'MINIMAL_MACHINE_FIRST'),
    terminal_condition:text(input.terminal_condition||input.success_condition)
  };
}

export function intentDiff(ownerIntent={},proposedAction={}){
  const intent=ownerIntent.schema?ownerIntent:compileOwnerIntent(ownerIntent);
  const issues=[];
  const actionEffect=upper(proposedAction.effect_class||proposedAction.effect||'NONE');
  const recurrence=proposedAction.recurrence===true||proposedAction.recurring===true;
  if(recurrence&&!intent.recurrence_requested) issues.push('UNREQUESTED_RECURRENCE');
  if(intent.prohibited_effects.includes(actionEffect)) issues.push('PROHIBITED_EFFECT');
  if(!['NONE','READ_ONLY','ANALYSIS'].includes(actionEffect)&&intent.requested_effects.length>0&&!intent.requested_effects.includes(actionEffect)){
    issues.push('UNREQUESTED_EFFECT_CLASS');
  }
  const target=text(proposedAction.target);
  if(intent.scope_locked&&target&&intent.target_scope.length>0&&!intent.target_scope.includes(target)) issues.push('TARGET_SCOPE_EXPANSION');
  const objective=text(proposedAction.objective);
  if(objective&&intent.literal_objective&&proposedAction.objective_preserved===false) issues.push('OWNER_OBJECTIVE_MUTATED');
  return {
    schema:'FUSE_OWNER_INTENT_DIFF_V2',
    pass:issues.length===0,
    issues,
    owner_objective:intent.literal_objective,
    action_effect:actionEffect,
    recurrence_requested:intent.recurrence_requested,
    recurrence_proposed:recurrence,
    authority_expansion:false
  };
}

export function reasoningPressure({prompt='',result={},meta={}}={}){
  const impact=clamp(result.impact_score??(highConsequence(prompt,result)?0.9:0.4));
  const uncertainty=clamp(result.uncertainty_score??(result.uncertainty_map?0.7:0.2));
  const irreversibility=clamp(result.irreversibility_score??(result.irreversible?1:0.2));
  const authorityRisk=clamp(result.authority_risk??(result.effectful?0.7:0.2));
  const proofRequirement=clamp(result.proof_requirement??(substantial(prompt,result)?0.6:0.2));
  const informationValue=clamp(result.expected_information_value??0.5);
  const pressure=(impact+uncertainty+irreversibility+authorityRisk+proofRequirement+informationValue)/6;
  return {impact,uncertainty,irreversibility,authority_risk:authorityRisk,proof_requirement:proofRequirement,information_value:informationValue,pressure};
}

export function selectCognitiveDepth({prompt='',result={},meta={}}={}){
  const pressure=reasoningPressure({prompt,result,meta});
  const repeated=n(result.same_semantic_failure_count,0);
  const unknownEffect=upper(result.effect_state)==='UNKNOWN'||result.unknown_effect===true;
  const architectural=/\b(architecture|runtime|controller|scheduler|mission bus|authority|proof root|source mutation|kernel|fence|lease)\b/i.test(text(prompt));
  if(unknownEffect||repeated>=2||(highConsequence(prompt,result)&&(pressure.pressure>=0.55||architectural))) return 'FORMATION';
  if(pressure.pressure>=0.65||architectural||upper(meta.depth)==='DEEP') return 'DEEP';
  if(substantial(prompt,result)||pressure.pressure>=0.4) return 'ADAPTIVE';
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
      if(wave.every(existing=>!conflicts(node,existing))){wave.push(node);placed=true;break;}
    }
    if(!placed) waves.push([node]);
  }
  return waves;
}

export function rankInformationGaps(gaps=[]){
  return arr(gaps).map((gap,index)=>{
    const acquisition=Math.max(0.01,n(gap.acquisition_cost,1));
    const score=clamp(gap.decision_impact??0.5)*clamp(gap.probability_changes_decision??0.5)*Math.max(0.01,n(gap.downstream_cost_avoided,1))/acquisition;
    return {gap,index,score};
  }).sort((a,b)=>b.score-a.score||a.index-b.index);
}

export function buildFutureEnvelope(state={}){
  const blockers=arr(state.blockers).slice().sort((a,b)=>n(b.impact,0)-n(a.impact,0));
  const opportunities=arr(state.opportunities).slice().sort((a,b)=>n(b.value,0)-n(a.value,0));
  const primary=blockers[0]||{},secondary=blockers[1]||{},opportunity=opportunities[0]||{};
  return {
    schema:'FUSE_FUTURE_ENVELOPE_V2',
    expected_next_state:text(state.expected_next_state||state.next_state||'UNKNOWN'),
    most_likely_blocker:text(primary.id||primary.name||'UNKNOWN'),
    hidden_second_order_blocker:text(secondary.id||secondary.name||'UNKNOWN'),
    opportunity_branch:text(opportunity.id||opportunity.name||'NONE'),
    early_warning_signal:text(primary.early_warning_signal||state.early_warning_signal||''),
    confidence:clamp(primary.confidence??state.confidence??0.5),
    falsifier:text(primary.falsifier||state.falsifier||''),
    lead_time:n(primary.lead_time,state.lead_time??0),
    impact:clamp(primary.impact??state.impact??0.5),
    no_regret_preparation:text(primary.no_regret_preparation||state.no_regret_preparation||''),
    preparation_cost:n(primary.preparation_cost,state.preparation_cost??0),
    reversal_trigger:text(primary.reversal_trigger||state.reversal_trigger||''),
    expiry:text(primary.expiry||state.expiry||'')
  };
}

export function calibrateForecast(forecast={},observed={}){
  if(observed.regime_change===true) return {classification:'REGIME_BREAK',timing_error:null};
  const expected=upper(forecast.expected_next_state),actual=upper(observed.state||observed.observed_state);
  const blockerExpected=upper(forecast.most_likely_blocker),blockerActual=upper(observed.blocker||observed.actual_blocker);
  const stateHit=expected&&actual&&expected===actual,blockerHit=blockerExpected&&blockerActual&&blockerExpected===blockerActual;
  const classification=stateHit&&blockerHit?'HIT':(stateHit||blockerHit)?'PARTIAL':'MISS';
  const timingError=(forecast.predicted_at!=null&&observed.observed_at!=null&&forecast.expected_after_ms!=null)
    ? Math.abs((n(observed.observed_at)-n(forecast.predicted_at))-n(forecast.expected_after_ms)) : null;
  return {classification,timing_error:timingError};
}

export function detectCommonModeEvidence(evidence=[]){
  const groups=new Map();
  for(const item of arr(evidence)){
    const root=text(item.root_source||item.root||item.origin||`${item.provider||'unknown'}:${item.source_id||item.id||'unknown'}`);
    if(!groups.has(root)) groups.set(root,[]);
    groups.get(root).push(item);
  }
  const roots=[...groups.keys()];
  const common_mode_groups=[...groups.entries()].filter(([,items])=>items.length>1).map(([root,items])=>({root,count:items.length}));
  return {independent_roots:roots.length,observations:arr(evidence).length,common_mode_groups,independence_factor:arr(evidence).length?roots.length/arr(evidence).length:0};
}

export function propagateBlastRadius(graph={},changed=[]){
  const changedSet=new Set(arr(changed).map(String)),affected=new Set(changedSet),adjacency=new Map();
  for(const edge of arr(graph.edges)){
    const type=upper(edge.type||'DEPENDS_ON');
    if(!['DEPENDS_ON','PROVES','DERIVED_FROM','REQUIRES_REQUALIFICATION','INVALIDATES'].includes(type)) continue;
    const from=String(edge.from),to=String(edge.to);
    if(!adjacency.has(from)) adjacency.set(from,[]);
    adjacency.get(from).push(to);
  }
  const queue=[...changedSet];
  while(queue.length){
    const node=queue.shift();
    for(const next of adjacency.get(node)||[]){if(!affected.has(next)){affected.add(next);queue.push(next);}}
  }
  return {changed:[...changedSet],affected:[...affected],requalify:[...affected].filter(x=>!changedSet.has(x))};
}

export function preMortem(plan={}){
  const risks=[];
  if(plan.currentness_valid===false) risks.push('STALE_CURRENTNESS');
  if(plan.unknown_effect_strategy===false||upper(plan.effect_state)==='UNKNOWN') risks.push('UNKNOWN_EFFECT');
  if(plan.rollback_defined===false&&plan.effectful===true) risks.push('ROLLBACK_MISSING');
  if(plan.proof_target_defined===false) risks.push('PROOF_TARGET_MISSING');
  if(plan.single_provider_dependency===true) risks.push('SINGLE_PROVIDER_FAILURE_DOMAIN');
  if(plan.owner_intervention_risk===true) risks.push('OWNER_RESCUE_RISK');
  return {schema:'FUSE_PREMORTEM_V2',pass:risks.length===0,risks,no_regret_actions:uniq(plan.no_regret_actions||[])};
}

export function counterfactuals(plan={}){
  const scenarios=[];
  if(plan.provider) scenarios.push({question:`IF_PROVIDER_${upper(plan.provider)}_DISAPPEARS`,answer:text(plan.provider_loss_result||'UNKNOWN')});
  if(plan.component) scenarios.push({question:`IF_COMPONENT_${upper(plan.component)}_REMOVED`,answer:text(plan.component_removal_result||'UNKNOWN')});
  if(plan.proof_dependency) scenarios.push({question:'IF_PROOF_INVALIDATED',answer:text(plan.proof_invalidation_result||'UNKNOWN')});
  scenarios.push({question:'IF_NO_ACTION',answer:text(plan.no_action_result||'UNKNOWN')});
  scenarios.push({question:'IF_SIMPLIFIED',answer:text(plan.simplified_result||'UNKNOWN')});
  return {schema:'FUSE_COUNTERFACTUAL_SET_V2',scenarios};
}

export function selfRepairDecision(event={}){
  const assistantCaused=event.assistant_caused===true,reversible=event.reversible===true;
  const drift=event.intent_diff_pass===false||event.unrequested_effect===true;
  const rollbackAvailable=event.rollback_available!==false;
  const shouldRollback=assistantCaused&&reversible&&drift&&rollbackAvailable;
  return {schema:'FUSE_SELF_REPAIR_DECISION_V2',should_rollback:shouldRollback,action:shouldRollback?'ROLLBACK_VERIFY_LEARN':drift?'HOLD_AND_RECOMPILE':'NO_ROLLBACK',owner_rescue_required:false};
}

export function sovereignKernelHook(phase,envelope={}){
  const p=upper(phase);
  if(!['PRE_COMPILE','PRE_EFFECT','POST_EFFECT'].includes(p)) throw new Error('UNKNOWN_SOVEREIGN_KERNEL_HOOK_PHASE');
  let decision='GO'; const issues=[];
  if(p==='PRE_COMPILE'){
    if(envelope.currentness_valid===false) issues.push('CURRENTNESS_INVALID');
    if(envelope.intent_diff&&envelope.intent_diff.pass===false) issues.push(...envelope.intent_diff.issues);
  }
  if(p==='PRE_EFFECT'){
    if(envelope.intent_diff&&envelope.intent_diff.pass===false) issues.push(...envelope.intent_diff.issues);
    if(envelope.authority===false) issues.push('AUTHORITY_INVALID');
    if(envelope.security===false) issues.push('SECURITY_INVALID');
    if(envelope.privacy===false) issues.push('PRIVACY_INVALID');
    if(envelope.cost_bounded===false) issues.push('COST_UNBOUNDED');
    if(upper(envelope.effect_state)==='UNKNOWN'&&envelope.unknown_effect_strategy!==true) issues.push('UNKNOWN_EFFECT_STRATEGY_MISSING');
  }
  if(p==='POST_EFFECT'){
    if(upper(envelope.effect_state)==='UNKNOWN') issues.push('READBACK_EFFECT_REQUIRED');
    if(envelope.semantic_readback===false) issues.push('SEMANTIC_READBACK_MISSING');
  }
  if(issues.some(x=>['AUTHORITY_INVALID','SECURITY_INVALID','PRIVACY_INVALID','COST_UNBOUNDED'].includes(x))) decision='HOLD';
  else if(issues.length) decision='REPLAN';
  return {schema:KERNEL_HOOK_SCHEMA,phase:p,decision,issues,authority_expansion:false,provider_effect_authorized:false};
}

export function cognitiveCheckpoint(state={}){
  return {
    schema:'FUSE_COGNITIVE_CHECKPOINT_V2',owner_objective:text(state.owner_objective),mission_id:text(state.mission_id),source_epoch:text(state.source_epoch),
    closed_predicates:uniq(state.closed_predicates||[]),open_predicates:uniq(state.open_predicates||[]),ready_set:uniq(state.ready_set||[]),
    current_fences:arr(state.current_fences),known_effects:arr(state.known_effects),unknown_effects:arr(state.unknown_effects),
    negative_knowledge:uniq(state.negative_knowledge||[]),failure_fingerprints:uniq(state.failure_fingerprints||[]),forecasts:arr(state.forecasts),
    next_machine_actions:uniq(state.next_machine_actions||[]),owner_action_required:state.owner_action_required===true
  };
}

export function performanceVerdict(performance={},cfg={}){
  const before=performance.before||performance.baseline||{},after=performance.after||performance.observed||performance;
  const hasLatency=n(before.latency_ms,0)>0&&n(after.latency_ms,0)>0,hasToolCalls=n(before.tool_calls,0)>0&&n(after.tool_calls,-1)>=0,hasOwnerPrompts=n(before.owner_prompts,0)>0&&n(after.owner_prompts,-1)>=0;
  const latencySpeedup=hasLatency?n(before.latency_ms)/n(after.latency_ms):null,toolReduction=hasToolCalls?1-(n(after.tool_calls)/n(before.tool_calls)):null,ownerPromptReduction=hasOwnerPrompts?1-(n(after.owner_prompts)/n(before.owner_prompts)):null;
  const floors={
    matched_benchmark:performance.matched_benchmark===true||performance.matched===true,
    latency_speedup:latencySpeedup!=null&&latencySpeedup>=n(cfg.latency_speedup_floor,1.5),
    tool_call_reduction:toolReduction==null||toolReduction>=n(cfg.tool_call_reduction_floor,0.2),
    owner_prompt_reduction:ownerPromptReduction==null||ownerPromptReduction>=n(cfg.owner_prompt_reduction_floor,0.5),
    quality_nonnegative:performance.quality_nonnegative!==false&&(performance.quality_delta==null||n(performance.quality_delta)>=0),
    false_green:n(performance.false_green_count,0)<=n(cfg.false_green_ceiling,0),unintended_writes:n(performance.unintended_writes,0)===0,
    unchanged_retries:n(performance.unchanged_retries,0)<=n(cfg.unchanged_retry_ceiling,0),owner_rescues:n(performance.owner_rescues,0)<=n(cfg.owner_rescue_ceiling,0),
    owner_intent_drift:n(performance.owner_intent_drift,0)<=n(cfg.owner_intent_drift_ceiling,0),
    unrequested_recurrence:n(performance.unrequested_recurrence,0)<=n(cfg.unrequested_recurrence_ceiling,0),
    executable_next_action_withheld:n(performance.executable_next_action_withheld,0)<=n(cfg.executable_next_action_withheld_ceiling,0)
  };
  const verified=Object.values(floors).every(Boolean);
  return {matched_benchmark:floors.matched_benchmark,hyper_performance_verified:verified,state:verified?'HYPER_PERFORMANCE_VERIFIED':floors.matched_benchmark?'MATCHED_BENCHMARK_NONPROMOTING':'MEASUREMENT_ONLY',latency_speedup:latencySpeedup,tool_call_reduction:toolReduction,owner_prompt_reduction:ownerPromptReduction,floors};
}

function intelligenceEvidence(result={},meta={}){
  const challenge=arr(result.challengers).length>0||arr(result.acceptance_tests).length>0||result.independent_challenger?.verified===true;
  const world=!!result.world_model||!!result.mission_graph||!!result.capability_census||result.currentness?.checked===true;
  const uncertainty=!!result.uncertainty_map||result.uncertainty_score!=null||challenge,causal=!!result.causal_graph||!!result.mission_graph||!!result.execution_dag;
  const future=!!result.future_envelope||!!result.next_action||result.recovery!=null||result.rollback===true;
  const voi=!!result.value_of_information||arr(result.source_refs).length>0||result.research_evidence?.verified===true||challenge;
  const collective=!!result.active_cognition_map||arr(result.challengers).length>0||arr(result.acceptance_tests).length>0,safeParallel=!!result.parallel_waves||!!result.execution_dag||!!result.mission_graph;
  const routes=arr(result.route_candidates),tournament=!!result.tournament||routes.length>1||arr(result.surface_portfolio?.selected).length>1||arr(result.challengers).length>0;
  const reuse=result.reuse_gate?.checked===true||result.existing_work_reused===true||result.historical_recall?.checked===true||meta.bootstrap_guard?.ok===true;
  const tenPass=meta.autonomous_improvement?.iterations_completed===10||meta.autonomous_improvement?.final_state==='TEN_ITERATIONS_COMPLETE_VERIFIED'||meta.bootstrap_guard?.ok===true;
  const falsification=challenge||result.falsification?.passed===true,antiLoop=n(result.same_semantic_failure_count,0)<2||result.changed_mechanism===true||result.failure_handling?.changed_mechanism===true;
  const ownerIntent=result.intent_diff?.pass===true||result.owner_intent_diff?.pass===true,premortem=result.pre_mortem?.pass===true||result.premortem?.pass===true;
  const counterfactual=arr(result.counterfactuals?.scenarios||result.counterfactuals).length>0,commonMode=result.common_mode_evidence?.independent_roots>0||result.evidence_independence?.checked===true;
  const kernelHooks=result.kernel_hooks?.pre_compile===true&&result.kernel_hooks?.pre_effect===true&&result.kernel_hooks?.post_effect===true;
  const calibration=result.forecast_calibration?.classification!=null||result.forecast_calibration_pending===true,selfRepair=result.self_repair?.checked===true||result.assistant_caused_drift===false;
  return {world,uncertainty,causal,future,voi,collective,safeParallel,tournament,reuse,tenPass,falsification,antiLoop,ownerIntent,premortem,counterfactual,commonMode,kernelHooks,calibration,selfRepair};
}

export function assessHyperBinding(prompt,result={},meta={},cfg={}){
  const enabled=cfg.enabled===true;
  if(!enabled) return {schema:HYPER_BINDING_SCHEMA,version:HYPER_BINDING_VERSION,required:false,pass:true,state:'DISABLED',issues:[]};
  const required=cfg.required_for_substantial_tasks!==false?substantial(prompt,result):true,depth=selectCognitiveDepth({prompt,result,meta}),evidence=intelligenceEvidence(result,meta);
  const gates={
    adaptive_depth:depth!=='FAST'||!required,owner_intent_diff:evidence.ownerIntent,world_model:evidence.world,uncertainty_map:evidence.uncertainty,causal_reasoning:evidence.causal,
    future_envelope:evidence.future,value_of_information:evidence.voi,premortem:evidence.premortem,counterfactuals:evidence.counterfactual,common_mode_evidence:evidence.commonMode,
    collective_cognition:evidence.collective,safe_parallelism:evidence.safeParallel,route_tournament:evidence.tournament,reuse_before_build:evidence.reuse,ten_pass_improvement:evidence.tenPass,
    adversarial_falsification:evidence.falsification,anti_loop_mechanism_change:evidence.antiLoop,sovereign_kernel_hooks:evidence.kernelHooks,forecast_calibration:evidence.calibration,self_repair:evidence.selfRepair
  };
  const issues=required?Object.entries(gates).filter(([,v])=>!v).map(([k])=>k.toUpperCase()+'_NOT_EVIDENCED'):[];
  const perf=performanceVerdict(result.performance||{},cfg),claim=hyperClaim(prompt,result);
  if(claim&&cfg.matched_benchmark_required_for_hyper_performance_claim!==false&&!perf.hyper_performance_verified) issues.push('HYPER_PERFORMANCE_CLAIM_LACKS_MATCHED_NONREGRESSION_PROOF');
  const pass=issues.length===0;
  return {schema:HYPER_BINDING_SCHEMA,version:HYPER_BINDING_VERSION,required,pass,state:pass?(claim&&perf.hyper_performance_verified?'HYPER_INTELLIGENCE_AND_PERFORMANCE_VERIFIED':'HYPER_INTELLIGENCE_POLICY_PASS'):'HOLD_RECOMPILE',cognitive_depth:depth,gates,performance:perf,kernel_hook_schema:KERNEL_HOOK_SCHEMA,truth_boundary:{hyper_intelligence_means:'adaptive evidence-grounded collective reasoning execution orchestration and calibrated pre-cognition',hyper_intelligence_does_not_mean:'sentience omniscience supernatural foresight or unavailable access',hyper_performance_requires:'matched empirical nonregression proof before performance promotion',authority_expansion:false},issues};
}

export default {assessHyperBinding,selectCognitiveDepth,reasoningPressure,compileOwnerIntent,intentDiff,rankRoutes,routeValue,compileParallelWaves,rankInformationGaps,buildFutureEnvelope,calibrateForecast,detectCommonModeEvidence,propagateBlastRadius,preMortem,counterfactuals,selfRepairDecision,sovereignKernelHook,cognitiveCheckpoint,performanceVerdict};
