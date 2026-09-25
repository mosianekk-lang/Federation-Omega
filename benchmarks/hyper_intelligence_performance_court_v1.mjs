import {
  assessHyperBinding,
  selectCognitiveDepth,
  rankRoutes,
  compileParallelWaves,
  performanceVerdict
} from '../fuse_runtime/hyper_intelligence_performance_v1.mjs';

const failures=[];
const check=(name,ok,detail=null)=>{if(!ok)failures.push({name,detail});};

const formationDepth=selectCognitiveDepth({
  prompt:'Deploy a security-sensitive runtime repair.',
  result:{effect_state:'UNKNOWN',uncertainty_score:0.8,same_semantic_failure_count:2,effectful:true}
});
check('unknown_effect_forces_formation',formationDepth==='FORMATION',formationDepth);

const ranked=rankRoutes([
  {id:'fast-bad',authority:false,latency_cost:0.1},
  {id:'strong',terminal_unlock:1,correctness_probability:.95,current_callability:1,proof_strength:.95,recovery_quality:.9,information_gain:.8,future_option_value:.8,privacy_score:1,sovereignty:.9,latency_cost:.5,financial_cost:.5,coordination_tax:.5,failure_correlation:.4,architecture_entropy:.5,owner_burden:.3},
  {id:'weak',terminal_unlock:.7,correctness_probability:.7,current_callability:.8,proof_strength:.6,recovery_quality:.5,information_gain:.4,future_option_value:.4,privacy_score:1,sovereignty:.7,latency_cost:1,financial_cost:1,coordination_tax:1,failure_correlation:1,architecture_entropy:1,owner_burden:1}
]);
check('hard_floor_filters_unauthorized',ranked.every(x=>x.route.id!=='fast-bad'),ranked);
check('strong_route_wins',ranked[0]?.route.id==='strong',ranked);

const waves=compileParallelWaves([
  {id:'read-a',read_scope:['a']},
  {id:'read-b',read_scope:['b']},
  {id:'write-a',write_scope:['a']},
  {id:'effect-x',effect_scope:['x']},
  {id:'effect-x-2',effect_scope:['x']}
]);
check('parallelism_present',waves.length>=2,waves);
const sameWaveConflict=waves.some(w=>w.some((a,i)=>w.slice(i+1).some(b=>a.effect_scope?.some(x=>b.effect_scope?.includes(x))||a.write_scope?.some(x=>b.read_scope?.includes(x)))));
check('conflicts_serialized',sameWaveConflict===false,waves);

const perf=performanceVerdict({
  matched_benchmark:true,
  before:{latency_ms:1000,tool_calls:10,owner_prompts:4},
  after:{latency_ms:400,tool_calls:7,owner_prompts:1},
  quality_delta:0,
  false_green_count:0,
  unintended_writes:0,
  unchanged_retries:0,
  owner_rescues:0
},{latency_speedup_floor:1.5,tool_call_reduction_floor:.2,owner_prompt_reduction_floor:.5});
check('matched_hyper_performance_promotes',perf.hyper_performance_verified===true,perf);

const unMatched=performanceVerdict({
  before:{latency_ms:1000},after:{latency_ms:100},quality_delta:1
},{});
check('no_matched_no_promotion',unMatched.hyper_performance_verified===false,unMatched);

const cfg={
  enabled:true,
  required_for_substantial_tasks:true,
  matched_benchmark_required_for_hyper_performance_claim:true,
  latency_speedup_floor:1.5,
  tool_call_reduction_floor:.2,
  owner_prompt_reduction_floor:.5,
  false_green_ceiling:0,
  unchanged_retry_ceiling:0,
  owner_rescue_ceiling:0
};
const meta={depth:'DEEP',bootstrap_guard:{ok:true},autonomous_improvement:{iterations_completed:10,final_state:'TEN_ITERATIONS_COMPLETE_VERIFIED'}};
function goodResult(){
  return {
    objective:'Elevate runtime binding to hyper-intelligence and hyper-performance',
    currentness:{checked:true,source_refs:['canon']},
    source_refs:['canon'],
    mission_graph:{nodes:[1]},
    execution_dag:{nodes:[1]},
    uncertainty_map:{known:[],unknown:[]},
    causal_graph:{edges:[1]},
    future_envelope:{next_bottleneck:'runtime deployment'},
    value_of_information:{resolved:['runtime identity']},
    active_cognition_map:[{actor:'executor'},{actor:'falsifier'}],
    parallel_waves:[[1],[2]],
    route_candidates:[{id:'a'},{id:'b'}],
    tournament:{selected:'a'},
    challengers:['falsifier'],
    acceptance_tests:['truth','performance'],
    reuse_gate:{checked:true},
    existing_work_reused:true,
    changed_mechanism:true,
    same_semantic_failure_count:2,
    performance:{
      matched_benchmark:true,
      before:{latency_ms:1000,tool_calls:10,owner_prompts:4},
      after:{latency_ms:400,tool_calls:7,owner_prompts:1},
      quality_delta:0,
      false_green_count:0,
      unintended_writes:0,
      unchanged_retries:0,
      owner_rescues:0
    }
  };
}
const good=assessHyperBinding('Improve the runtime binding to hyper-intelligence and hyper-performance.',goodResult(),meta,cfg);
check('full_hyper_binding_passes',good.pass===true&&good.state==='HYPER_INTELLIGENCE_AND_PERFORMANCE_VERIFIED',good);

const missingFuture=goodResult(); delete missingFuture.future_envelope; delete missingFuture.recovery; delete missingFuture.next_action; missingFuture.rollback=false;
const badFuture=assessHyperBinding('Improve this substantial runtime architecture.',missingFuture,meta,cfg);
check('missing_future_envelope_holds',badFuture.pass===false&&badFuture.issues.includes('FUTURE_ENVELOPE_NOT_EVIDENCED'),badFuture);

const loop=goodResult();loop.same_semantic_failure_count=2;loop.changed_mechanism=false;delete loop.failure_handling;
const badLoop=assessHyperBinding('Improve this substantial runtime architecture.',loop,meta,cfg);
check('unchanged_retry_semantics_hold',badLoop.pass===false&&badLoop.issues.includes('ANTI_LOOP_MECHANISM_CHANGE_NOT_EVIDENCED'),badLoop);

const noPerf=goodResult();noPerf.performance={matched_benchmark:false,before:{latency_ms:1000},after:{latency_ms:200},quality_delta:0};
const badClaim=assessHyperBinding('Deliver hyper-performance for this runtime.',noPerf,meta,cfg);
check('hyper_claim_requires_matched_proof',badClaim.pass===false&&badClaim.issues.includes('HYPER_PERFORMANCE_CLAIM_LACKS_MATCHED_NONREGRESSION_PROOF'),badClaim);

const report={
  schema:'FUSE_HYPER_INTELLIGENCE_PERFORMANCE_COURT_V1',
  cases:11,
  failures,
  passed:failures.length===0,
  truth_boundary:'HYPER_INTELLIGENCE_IS_ENGINEERING_ORCHESTRATION_NOT_SENTIENCE; HYPER_PERFORMANCE_REQUIRES_MATCHED_EMPIRICAL_PROOF',
  ran_at:new Date().toISOString()
};
console.log(JSON.stringify(report,null,2));
if(!report.passed)process.exitCode=1;
