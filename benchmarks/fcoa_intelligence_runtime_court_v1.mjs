import assert from 'node:assert/strict';
import { runFcoaIntelligenceCycle } from '../fuse_runtime/fcoa_intelligence_runtime_v1.mjs';

const out=runFcoaIntelligenceCycle({
  workflow_id:'fcoa-runtime-test',
  prompt:'Design and verify an FCOA device workflow with proof and recovery',
  target_scope:['FCOA'],
  scope_locked:true,
  currentness_valid:true,
  authority_valid:true,
  privacy_valid:true,
  rollback_defined:true,
  effect_state:'NONE',
  routes:[
    {id:'a',authority:true,security:true,privacy:true,current:true,semantic_fit:0.9,reliability:0.9,latency_ms:100,cost:0.1},
    {id:'b',authority:false,security:true,privacy:true,current:true,semantic_fit:1,reliability:1,latency_ms:10,cost:0}
  ],
  nodes:[
    {id:'r1',scope_known:true,read_scope:['a'],write_scope:[],effect_scope:[]},
    {id:'r2',scope_known:true,read_scope:['b'],write_scope:[],effect_scope:[]}
  ],
  plan:{currentness_valid:true,unknown_effect_strategy:true,rollback_defined:true,effectful:false,proof_target_defined:true},
  result:{
    owner_intent_diff:{pass:true},
    world_model:{built:true},
    uncertainty_map:{built:true},
    causal_reasoning:{built:true},
    future_envelope:{built:true},
    value_of_information:{used:true},
    premortem:{pass:true},
    counterfactuals:{built:true},
    common_mode_evidence:{checked:true},
    collective_cognition:{used:true},
    safe_parallelism:{compiled:true},
    route_tournament:{run:true},
    forecast_calibration:{done:true}
  },
  cfg:{enabled:true,improvement_iterations:10}
});

assert.equal(out.schema,'FCOA_FORMATION_HYPER_AUTOIMPROVE_RUNTIME_V1');
assert.equal(out.formation_required,true);
assert.equal(out.hyper_contract,'FUSE-HIPB-001');
assert.equal(out.autonomous_improvement.iterations_completed,10);
assert.equal(out.max_mutating_lanes,1);
assert.equal(out.external_effect_authorized,false);
assert.equal(out.builder_self_certification_allowed,false);
assert.equal(out.creates_new_controller,false);
assert.equal(out.creates_new_scheduler,false);
assert.ok(out.ranked_routes.length>=1);
assert.ok(out.parallel_waves.length>=1);
console.log(JSON.stringify({passed:true,schema:out.schema,depth:out.cognitive_depth,iterations:out.autonomous_improvement.iterations_completed,hyper_state:out.hyper_binding.state}));
