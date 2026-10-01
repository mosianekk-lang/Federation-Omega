import { createMirrorV3, POWER_DIARY_SOURCE_SHA256, POWER_DIARY_CHAPTER_COUNT } from '../fuse_runtime/output_mirror_v3.mjs';
const trustContext=p=>({trust_zone:'OWNER_PRIVATE',sensitive_matter:/legal|evidence|security/i.test(String(p||''))});
const mirror=createMirrorV3({trustContext});
const cfg={enabled:true,version:'3.0.0',intent_similarity_floor:0.18,reality_clause_preserved:true,
developer1000:{count:1000,sha256:'f7277e2244f1d59849f64f5d4f48af7c20de14ecb8573dba763353bf6084cb7e'},
benchmark_court:{cases:1000,dataset_sha256:'d69644412e285ef3a5baeab0b0ef4683ae42280ddca0bdb4a0ea2ce3a5fd6510'},
power_diary:{source_sha256:POWER_DIARY_SOURCE_SHA256,chapter_count:40,family_count:17}};
const meta={depth:'DEEP',bootstrap_guard:{ok:true}};
function base(prompt){return {objective:prompt,route:'ENGINEERING_VERIFIED',completion_state:'COMPLETE_VERIFIED',
tasks:['understand','reuse','execute','verify'],next_action:'No residual machine-safe work remains.',
proof:{build:true,tests:true,readback:true,authority:true,privacy:true,security:true,recovery:true},
tests:{status:'passed',regression:true},change_batch:'small',maintainability:'improved_or_nonnegative',review_context:true,
authority_proven:true,privacy_check:true,security_review:true,rollback:true,recovery:true,effect_readback:true,idempotency:'bounded',
performance:{measured:true,before:100,after:20},currentness:{checked:true,observed_at:'2026-09-25T02:45:00+02:00',source_refs:['primary']},
source_refs:['primary'],machine_route_available:true,manual_user_tasks:[],mission_graph:{steps:[1]},
surface_portfolio:{selected:[{surface:'fuse'},{surface:'provider2'}]},challengers:['independent'],acceptance_tests:['correctness'],
reuse_gate:{checked:true},existing_work_reused:true,creative_direction:{target:'preserved'},provider_independent_master:{present:true},
editable_master:true,observations:['obs'],hypotheses:['h1'],alternative_hypotheses:['h2'],contradictions:['none'],confidence:0.9,
harvest_contract:{clean_room:true,provenance_preserved:true,mechanism_extracted:true},
commercial_checks:{customer_problem:true,distribution:true,operating_cost:true,measurable_value:true},
mirror_strengthening:'DETERMINISTIC_CHALLENGE_TOURNAMENT'};}
function assess(prompt,result=base(prompt),m=meta,c=cfg){return mirror.assess(prompt,result,m,c);}
const cases=[];function add(name,prompt,bad){cases.push({name,prompt,bad});}add('maximum_capability','Provide the strongest substantial integration solution.',r=>{delete r.mission_graph;delete r.surface_portfolio;});
add('owner_intent_fidelity','Preserve and execute this exact requested outcome.',r=>{r.objective='Different unrelated objective';});
add('durable_mission_continuity','n',(r,m)=>{m.bootstrap_guard={ok:false};});
add('solve_before_report','Repair this blocked integration and return the result.',r=>{r.error='recoverable error';});
add('reuse_and_convergence','Build a new automation system for this objective.',(r,m)=>{delete r.reuse_gate;delete r.existing_work_reused;m.bootstrap_guard={ok:false};});
add('creative_fidelity','Create an ambitious editable fashion design with provider-independent assets.',r=>{delete r.creative_direction;delete r.provider_independent_master;delete r.editable_master;r.route='LOCAL';});
add('research_evidence','Research the evidence and verify the relevant facts.',r=>{r.source_refs=[];r.currentness={checked:false,source_refs:[]};delete r.research_evidence;});
add('investigation_rigor','Investigate this forensic incident and test alternative hypotheses.',r=>{delete r.alternative_hypotheses;});
add('production_engineering','Implement and verify a Python software change.',r=>{r.tests={status:'missing',regression:false};r.proof.tests=false;});
add('provider_neutral_routing','Design a provider-neutral multi-provider execution route.',r=>{r.surface_portfolio={selected:[{surface:'one'}]};delete r.provider_neutral_contract;});
add('independent_challenge','Assess this high-consequence legal evidence decision.',r=>{r.challengers=[];r.acceptance_tests=[];});
add('clean_room_harvest','Clean-room harvest the public mechanism and benchmark it.',r=>{delete r.harvest_contract;});
add('commercial_product','Build a commercial product with customer value and distribution.',r=>{delete r.commercial_checks;});
add('owner_attention','Complete this task with minimum owner burden.',r=>{r.manual_user_tasks=['manual retry'];r.machine_route_available=true;});
add('truthful_completion','Finish this software outcome with proof.',r=>{r.completion_state='PLANNED_ACCELERATED';r.proof.readback=false;});
add('command_semantics','do all',(r,m)=>{delete r.mission_graph;delete r.execution_dag;m.bootstrap_guard={ok:false};});
add('reality_clause','Deliver the strongest lawful truthful result.',(r,m,c)=>{c.reality_clause_preserved=false;});let positives=0,negatives=0;const details=[];
for(const tc of cases){
  const good=assess(tc.prompt,base(tc.prompt),structuredClone(meta),structuredClone(cfg));
  const badR=base(tc.prompt),badM=structuredClone(meta),badC=structuredClone(cfg);tc.bad(badR,badM,badC);
  const bad=assess(tc.prompt,badR,badM,badC);
  const okGood=good.release_allowed===true;
  const okBad=bad.release_allowed===false;
  positives+=okGood?1:0;negatives+=okBad?1:0;
  details.push({family:tc.name,pass_case:okGood,fail_case:okBad,bad_issues:bad.issues});
}
const sample=assess('Provide a strong useful plan.',base('Provide a strong useful plan.'),meta,cfg);
const expected=Array.from({length:40},(_,i)=>i+1);
const coverageOk=POWER_DIARY_CHAPTER_COUNT===40&&sample.power_diary.chapter_count===40&&
JSON.stringify(sample.power_diary.covered_chapters)===JSON.stringify(expected)&&sample.power_diary.family_count===17;
const report={schema:'FUSE_OUTPUT_MIRROR_V3_POWER_DIARY_COURT',source_sha256:POWER_DIARY_SOURCE_SHA256,
chapter_count:sample.power_diary.chapter_count,covered_chapters:sample.power_diary.covered_chapters,
family_count:sample.power_diary.family_count,static_coverage_40_of_40:coverageOk,behavioral_families:cases.length,
positive_passes:positives,negative_holds:negatives,all_behavioral_pass:positives===cases.length&&negatives===cases.length,
details,ran_at:new Date().toISOString()};
console.log(JSON.stringify(report,null,2));
if(!report.static_coverage_40_of_40||!report.all_behavioral_pass)process.exitCode=1;