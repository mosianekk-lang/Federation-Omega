import {
  assessHyperBinding,
  compileOwnerIntent,
  compileParallelWaves,
  performanceVerdict,
  preMortem,
  rankRoutes,
  selectCognitiveDepth,
  selfRepairDecision,
  sovereignKernelHook
} from './hyper_intelligence_performance_v1.mjs';
import { runTen } from './autonomous_improvement_loop_v1.mjs';

export const FCOA_INTELLIGENCE_RUNTIME_SCHEMA='FCOA_FORMATION_HYPER_AUTOIMPROVE_RUNTIME_V1';
export const FCOA_INTELLIGENCE_RUNTIME_VERSION='1.0.0';

const cfgDefaults={
  enabled:true,
  required_for_substantial_tasks:true,
  improvement_iterations:10,
  promotion_requires:'MATCHED_NONREGRESSION_PROOF_READBACK_ROLLBACK_AND_PROVENANCE',
  tie_behavior:'KEEP_CURRENT_CHAMPION'
};

export function runFcoaIntelligenceCycle(input={}){
  const cfg={...cfgDefaults,...(input.cfg||{})};
  const prompt=String(input.prompt||input.objective||'');
  const result=input.result||{};
  const meta=input.meta||{};
  const ownerIntent=compileOwnerIntent({
    objective:prompt,
    requested_output:input.requested_output,
    success_condition:input.success_condition,
    constraints:input.constraints||[],
    prohibited_effects:input.prohibited_effects||[],
    requested_effects:input.requested_effects||[],
    target_scope:input.target_scope||[],
    scope_locked:input.scope_locked===true,
    owner_burden_target:'MINIMAL_MACHINE_FIRST'
  });
  const depth=selectCognitiveDepth({prompt,result,meta});
  const rankedRoutes=rankRoutes(input.routes||[]);
  const waves=compileParallelWaves(input.nodes||[]);
  const premortem=preMortem(input.plan||{});
  const preCompile=sovereignKernelHook('PRE_COMPILE',{
    currentness_valid:input.currentness_valid!==false,
    intent_diff_pass:input.intent_diff_pass!==false,
    scope_locked:input.scope_locked===true,
    unknown_effect:input.unknown_effect===true
  });
  const preEffect=sovereignKernelHook('PRE_EFFECT',{
    currentness_valid:input.currentness_valid!==false,
    intent_diff_pass:input.intent_diff_pass!==false,
    effect_state:input.effect_state||result.effect_state||'NONE',
    authority_valid:input.authority_valid!==false,
    privacy_valid:input.privacy_valid!==false,
    rollback_defined:input.rollback_defined!==false
  });
  const postEffect=sovereignKernelHook('POST_EFFECT',{
    effect_state:input.effect_state||result.effect_state||'NONE',
    readback_complete:input.readback_complete===true,
    semantic_match:input.semantic_match===true,
    rollback_verified:input.rollback_verified===true
  });
  const repair=selfRepairDecision(input.event||{intent_diff_pass:true});
  const hyper=assessHyperBinding(prompt,result,meta,{
    enabled:cfg.enabled===true,
    required_for_substantial_tasks:cfg.required_for_substantial_tasks!==false
  });
  const improvement=runTen({
    target_id:input.target_id||input.workflow_id||'FCOA_CURRENT',
    title:input.title||'FCOA Intelligence Cycle',
    finding:input.finding||prompt,
    target_type:'FCOA_WORKFLOW'
  },{
    iterations:Math.max(1,Math.min(10,Number(cfg.improvement_iterations||10))),
    target_type:'FCOA_WORKFLOW'
  });
  const performance=input.performance
    ? performanceVerdict(input.performance,input.performance_cfg||{})
    : null;
  return {
    schema:FCOA_INTELLIGENCE_RUNTIME_SCHEMA,
    version:FCOA_INTELLIGENCE_RUNTIME_VERSION,
    owner_intent:ownerIntent,
    cognitive_depth:depth,
    ranked_routes:rankedRoutes,
    parallel_waves:waves,
    premortem,
    hooks:{PRE_COMPILE:preCompile,PRE_EFFECT:preEffect,POST_EFFECT:postEffect},
    self_repair:repair,
    hyper_binding:hyper,
    autonomous_improvement:improvement,
    performance,
    formation_required:true,
    formation_contract:'FUSE-FORMATION-POWER-002',
    hyper_contract:'FUSE-HIPB-001',
    autonomous_improvement_contract:'FUSE_AUTONOMOUS_IMPROVEMENT_LOOP_V1',
    max_mutating_lanes:1,
    external_effect_authorized:false,
    provider_execution_proven:false,
    builder_self_certification_allowed:false,
    creates_new_controller:false,
    creates_new_scheduler:false,
    creates_new_authority_root:false,
    truth_boundary:
      'FCOA_RUNTIME_INTELLIGENCE_CYCLE!=FORMATION_EXECUTED!=PROVIDER_EXECUTED'+
      '!=MATCHED_HYPER_PERFORMANCE_PROVEN!=NATURAL_IMPROVEMENT_PREVENTION!=OWNER_VALUE!=COMPLETE'
  };
}
