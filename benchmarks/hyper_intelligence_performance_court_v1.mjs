import {
  assessHyperBinding, selectCognitiveDepth, rankRoutes, compileParallelWaves,
  performanceVerdict, compileOwnerIntent, intentDiff, rankInformationGaps,
  buildFutureEnvelope, calibrateForecast, detectCommonModeEvidence,
  propagateBlastRadius, preMortem, counterfactuals, selfRepairDecision,
  sovereignKernelHook, cognitiveCheckpoint
} from '../fuse_runtime/hyper_intelligence_performance_v1.mjs';

const failures=[];
const check=(name,ok,detail=null)=>{if(!ok)failures.push({name,detail});};

const formationDepth=selectCognitiveDepth({prompt:'Deploy a security-sensitive runtime repair.',result:{effect_state:'UNKNOWN',uncertainty_score:.8,same_semantic_failure_count:2,effectful:true}});
check('unknown_effect_forces_formation',formationDepth==='FORMATION',formationDepth);

const owner=compileOwnerIntent({objective:'Deploy an on-demand 24-hour summary prompt',requested_effects:['CONFIG'],recurrence_requested:false,target_scope:['FUSE_SUMMARY'],scope_locked:true});
const badIntent=intentDiff(owner,{effect_class:'CONFIG',recurrence:true,target:'FUSE_SUMMARY'});
check('unrequested_recurrence_fails',badIntent.pass===false&&badIntent.issues.includes('UNREQUESTED_RECURRENCE'),badIntent);
const goodIntent=intentDiff(owner,{effect_class:'CONFIG',recurrence:false,target:'FUSE_SUMMARY'});
check('on_demand_intent_passes',goodIntent.pass===true,goodIntent);

const ranked=rankRoutes([
  {id:'fast-bad',authority:false,latency_cost:.1},
  {id:'strong',terminal_unlock:1,correctness_probability:.95,current_callability:1,proof_strength:.95,recovery_quality:.9,information_gain:.8,future_option_value:.8,privacy_score:1,sovereignty:.9,latency_cost:.5,financial_cost:.5,coordination_tax:.5,failure_correlation:.4,architecture_entropy:.5,owner_burden:.3},
  {id:'weak',terminal_unlock:.7,correctness_probability:.7,current_callability:.8,proof_strength:.6,recovery_quality:.5,information_gain:.4,future_option_value:.4,privacy_score:1,sovereignty:.7,latency_cost:1,financial_cost:1,coordination_tax:1,failure_correlation:1,architecture_entropy:1,owner_burden:1}
]);
check('hard_floor_filters_unauthorized',ranked.every(x=>x.route.id!=='fast-bad'),ranked);
check('strong_route_wins',ranked[0]?.route.id==='strong',ranked);

const waves=compileParallelWaves([{id:'read-a',read_scope:['a']},{id:'read-b',read_scope:['b']},{id:'write-a',write_scope:['a']},{id:'effect-x',effect_scope:['x']},{id:'effect-x-2',effect_scope:['x']}]);
const sameWaveConflict=waves.some(w=>w.some((a,i)=>w.slice(i+1).some(b=>a.effect_scope?.some(x=>b.effect_scope?.includes(x))||a.write_scope?.some(x=>b.read_scope?.includes(x)))));
check('conflicts_serialized',sameWaveConflict===false,waves);

const voi=rankInformationGaps([{id:'cheap-important',decision_impact:1,probability_changes_decision:.9,downstream_cost_avoided:10,acquisition_cost:1},{id:'expensive-low',decision_impact:.2,probability_changes_decision:.2,downstream_cost_avoided:1,acquisition_cost:10}]);
check('voi_prioritizes_decision_changing_gap',voi[0]?.gap.id==='cheap-important',voi);

const future=buildFutureEnvelope({expected_next_state:'DEPLOYED',blockers:[{id:'AUTH',impact:.9,confidence:.8},{id:'RUNTIME',impact:.7}],opportunities:[{id:'CACHE',value:.8}]});
check('future_envelope_prioritizes_blocker',future.most_likely_blocker==='AUTH'&&future.hidden_second_order_blocker==='RUNTIME',future);

const calibration=calibrateForecast({...future,expected_next_state:'DEPLOYED',most_likely_blocker:'AUTH'},{state:'DEPLOYED',blocker:'AUTH'});
check('forecast_hit_calibrates',calibration.classification==='HIT',calibration);

const common=detectCommonModeEvidence([{id:1,root_source:'A'},{id:2,root_source:'A'},{id:3,root_source:'B'}]);
check('common_mode_collapses_duplicate_roots',common.independent_roots===2&&common.common_mode_groups.length===1,common);

const blast=propagateBlastRadius({edges:[{from:'source',to:'test',type:'REQUIRES_REQUALIFICATION'},{from:'test',to:'deploy',type:'DEPENDS_ON'},{from:'other',to:'safe',type:'DEPENDS_ON'}]},['source']);
check('blast_radius_is_selective',blast.requalify.includes('test')&&blast.requalify.includes('deploy')&&!blast.affected.includes('safe'),blast);

const premortem=preMortem({currentness_valid:true,unknown_effect_strategy:true,effect_state:'KNOWN',rollback_defined:true,effectful:true,proof_target_defined:true,single_provider_dependency:false,owner_intervention_risk:false});
check('premortem_clean_plan_passes',premortem.pass===true,premortem);

const cf=counterfactuals({provider:'X',provider_loss_result:'FAILOVER_OK',no_action_result:'DELAY',simplified_result:'PASS'});
check('counterfactuals_include_provider_loss',cf.scenarios.some(x=>x.question==='IF_PROVIDER_X_DISAPPEARS'),cf);

const rollback=selfRepairDecision({assistant_caused:true,reversible:true,intent_diff_pass:false,rollback_available:true});
check('assistant_caused_drift_auto_rolls_back',rollback.should_rollback===true&&rollback.owner_rescue_required===false,rollback);

const preCompile=sovereignKernelHook('PRE_COMPILE',{currentness_valid:true,intent_diff:{pass:true,issues:[]}});
const preEffect=sovereignKernelHook('PRE_EFFECT',{intent_diff:{pass:true,issues:[]},authority:true,security:true,privacy:true,cost_bounded:true,effect_state:'KNOWN'});
const postEffect=sovereignKernelHook('POST_EFFECT',{effect_state:'KNOWN',semantic_readback:true});
check('three_kernel_hooks_go',preCompile.decision==='GO'&&preEffect.decision==='GO'&&postEffect.decision==='GO',{preCompile,preEffect,postEffect});
const badEffect=sovereignKernelHook('PRE_EFFECT',{intent_diff:{pass:false,issues:['UNREQUESTED_RECURRENCE']},authority:true,security:true,privacy:true,cost_bounded:true,effect_state:'KNOWN'});
check('intent_drift_replans_pre_effect',badEffect.decision==='REPLAN',badEffect);

const checkpoint=cognitiveCheckpoint({owner_objective:'x',mission_id:'m1',source_epoch:'s1',closed_predicates:['A'],open_predicates:['B'],ready_set:['B'],next_machine_actions:['execute-B']});
check('checkpoint_preserves_next_action',checkpoint.next_machine_actions[0]==='execute-B'&&checkpoint.owner_action_required===false,checkpoint);

const perf=performanceVerdict({matched_benchmark:true,before:{latency_ms:1000,tool_calls:10,owner_prompts:4},after:{latency_ms:400,tool_calls:7,owner_prompts:1},quality_delta:0,false_green_count:0,unintended_writes:0,unchanged_retries:0,owner_rescues:0,owner_intent_drift:0,unrequested_recurrence:0,executable_next_action_withheld:0},{latency_speedup_floor:1.5,tool_call_reduction_floor:.2,owner_prompt_reduction_floor:.5,owner_intent_drift_ceiling:0,unrequested_recurrence_ceiling:0,executable_next_action_withheld_ceiling:0});
check('matched_hyper_performance_promotes',perf.hyper_performance_verified===true,perf);
const driftPerf=performanceVerdict({matched_benchmark:true,before:{latency_ms:1000},after:{latency_ms:400},quality_delta:0,owner_intent_drift:1},{owner_intent_drift_ceiling:0});
check('intent_drift_blocks_performance_promotion',driftPerf.hyper_performance_verified===false,driftPerf);

const cfg={enabled:true,required_for_substantial_tasks:true,matched_benchmark_required_for_hyper_performance_claim:true,latency_speedup_floor:1.5,tool_call_reduction_floor:.2,owner_prompt_reduction_floor:.5,false_green_ceiling:0,unchanged_retry_ceiling:0,owner_rescue_ceiling:0,owner_intent_drift_ceiling:0,unrequested_recurrence_ceiling:0,executable_next_action_withheld_ceiling:0};
const meta={depth:'DEEP',bootstrap_guard:{ok:true},autonomous_improvement:{iterations_completed:10,final_state:'TEN_ITERATIONS_COMPLETE_VERIFIED'}};
function goodResult(){
  return {
    objective:'Elevate runtime binding to adaptive sovereign cognition',currentness:{checked:true,source_refs:['canon']},source_refs:['canon'],mission_graph:{nodes:[1]},execution_dag:{nodes:[1]},uncertainty_map:{known:[],unknown:[]},causal_graph:{edges:[1]},future_envelope:future,value_of_information:{resolved:['runtime identity']},active_cognition_map:[{actor:'executor'},{actor:'falsifier'}],parallel_waves:[[1],[2]],route_candidates:[{id:'a'},{id:'b'}],tournament:{selected:'a'},challengers:['falsifier'],acceptance_tests:['truth','performance'],reuse_gate:{checked:true},existing_work_reused:true,changed_mechanism:true,same_semantic_failure_count:2,intent_diff:{pass:true},pre_mortem:{pass:true},counterfactuals:cf,common_mode_evidence:common,kernel_hooks:{pre_compile:true,pre_effect:true,post_effect:true},forecast_calibration:{classification:'HIT'},self_repair:{checked:true},assistant_caused_drift:false,
    performance:{matched_benchmark:true,before:{latency_ms:1000,tool_calls:10,owner_prompts:4},after:{latency_ms:400,tool_calls:7,owner_prompts:1},quality_delta:0,false_green_count:0,unintended_writes:0,unchanged_retries:0,owner_rescues:0,owner_intent_drift:0,unrequested_recurrence:0,executable_next_action_withheld:0}
  };
}
const good=assessHyperBinding('Improve the Sovereign Kernel with hyper-intelligence and hyper-performance.',goodResult(),meta,cfg);
check('full_v2_hyper_binding_passes',good.pass===true&&good.version==='2.0.0'&&good.state==='HYPER_INTELLIGENCE_AND_PERFORMANCE_VERIFIED',good);
const missingIntent=goodResult();delete missingIntent.intent_diff;
const bad=assessHyperBinding('Improve this substantial runtime architecture.',missingIntent,meta,cfg);
check('missing_intent_diff_holds',bad.pass===false&&bad.issues.includes('OWNER_INTENT_DIFF_NOT_EVIDENCED'),bad);

const report={schema:'FUSE_HYPER_INTELLIGENCE_PERFORMANCE_COURT_V2',cases:20,failures,passed:failures.length===0,truth_boundary:'ADAPTIVE_COGNITION_AND_PRECOG_ARE_ENGINEERING_CONTROLS_NOT_SENTIENCE; PERFORMANCE_REQUIRES_MATCHED_EMPIRICAL_PROOF',ran_at:new Date().toISOString()};
console.log(JSON.stringify(report,null,2));
if(!report.passed)process.exitCode=1;
