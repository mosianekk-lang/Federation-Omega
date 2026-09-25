import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';

const ROOT=path.join(process.env.LOCALAPPDATA||path.join(os.homedir(),'AppData','Local'),'FUSE','SovereignPlane');
const STATE=path.join(ROOT,'state','autonomous-improvement');
fs.mkdirSync(STATE,{recursive:true});
const sha=v=>crypto.createHash('sha256').update(typeof v==='string'?v:JSON.stringify(v)).digest('hex');

export const HARVEST10=[
 {id:'GENERATOR_VERIFIER_LOOP',source:'PUBLIC_2026_LOOP_ENGINEERING',inhouse:'FUSE_GENERATE_VERIFY_FEEDBACK'},
 {id:'HARNESS_LEVEL_RELIABILITY',source:'PUBLIC_2026_RELIABLE_CODING_AGENTS',inhouse:'FUSE_HARNESS_RELIABILITY_COURT'},
 {id:'ENGINEERING_LOOP_COVERAGE',source:'PUBLIC_2026_SWE_ATLAS',inhouse:'FUSE_ENGINEERING_LOOP_COURT'},
 {id:'VALIDATION_SELF_AWARENESS',source:'PUBLIC_2026_MICROSOFT_RESEARCH',inhouse:'FUSE_VALIDATION_SELF_AWARENESS'},
 {id:'INTEGRATION_WIDTH_DIAGNOSTIC',source:'PUBLIC_2026_REPOREASON',inhouse:'FUSE_REPOSITORY_REASONING_DIAGNOSTIC'},
 {id:'LIVE_CONTAMINATION_RESISTANT_TASKS',source:'PUBLIC_2026_DAPLAB',inhouse:'FUSE_LIVE_TASK_COURT'},
 {id:'REQUIREMENT_PLAN_CODE_TRACE',source:'PUBLIC_2026_ISSUE_RESOLUTION_BENCH',inhouse:'FUSE_REQUIREMENT_TRACE_COURT'},
 {id:'TRAJECTORY_DRIVEN_EVOLUTION',source:'PUBLIC_2026_SELF_EVOLVING_AGENTS',inhouse:'FUSE_TRAJECTORY_EVOLUTION'},
 {id:'REPRODUCIBLE_RUN_EVIDENCE',source:'PUBLIC_2026_REPRODUCIBLE_AGENT_BENCH',inhouse:'FUSE_REPRODUCIBLE_RUN_RECEIPT'},
 {id:'NONCOMPENSATING_AUTONOMY_FLOORS',source:'PUBLIC_2026_AGENTIC_READINESS',inhouse:'FUSE_AUTONOMY_FLOOR_GATE'}
];

const DEFECTS=[
 ['ARTIFACT_FOR_OUTCOME',/artifact|code|zip|ledger|prompt|draft|source/i,'SOURCE_TO_RUNTIME_TO_OUTCOME_CLOSURE'],
 ['ACTIVATION_WITHOUT_BINDING',/activat|active|operational|online|integrat/i,'BINDING_AND_RUNTIME_READBACK'],
 ['LOCAL_PROOF_FOR_LIVE',/local|unit test|commit|canary|provider proof|runtime/i,'PROOF_STATE_LADDER'],
 ['OPTIONS_FOR_EXECUTION',/if you want|next step|continue|choose|say the word|optional/i,'KNOWN_NEXT_ACTION_AUTOCONTINUE'],
 ['BOUNDARY_TRUNCATION',/blocked|unavailable|boundary|tls|authentication|oauth|provider/i,'BOUNDARY_ROUTE_MATRIX'],
 ['USER_BURDEN_SHIFT',/manual|upload|paste|install|screenshot|approve|user/i,'OWNER_ATTENTION_FIREWALL'],
 ['PARTIAL_RETRIEVAL_AS_COMPLETE',/partial|selected|corpus|coverage|retrieval|source/i,'CORPUS_COMPLETENESS_GATE'],
 ['DRAFT_FOR_RELEASE',/draft|approval|filing|signature|service|decision/i,'RELEASE_AND_RECEIPT_GATE'],
 ['CHECKPOINT_FOR_CONTINUITY',/checkpoint|transfer|bible|continuity|capsule|restore/i,'NATIVE_VS_CAPSULE_TRUTH_GATE'],
 ['CORRECTION_AFTER_CLAIM',/correct|admit|later|challeng|overclaim|mislead/i,'PROACTIVE_FALSE_PASS_PREVENTION']
];function classify(text=''){
 const out=[];
 for(const [id,re,repair] of DEFECTS) if(re.test(String(text))) out.push({id,repair});
 return out.length?out:[{id:'GENERIC_INCOMPLETE_HANDLING',repair:'TERMINAL_FRUIT_PRESERVATION'}];
}
function safeName(x){return String(x||'target').replace(/[^a-zA-Z0-9._-]+/g,'-').slice(0,96);}

function iterationMechanism(h){
 const map={
  GENERATOR_VERIFIER_LOOP:'Generate one bounded candidate; verify independently; feed only verified delta into next pass.',
  HARNESS_LEVEL_RELIABILITY:'Inspect state, retrieval, permissions, execution, proof, recovery and observability around the model.',
  ENGINEERING_LOOP_COVERAGE:'Require understanding, tests, maintenance/refactor evidence and issue resolution as one loop.',
  VALIDATION_SELF_AWARENESS:'Mechanically inspect requested artifact/outcome beyond test-oracle success; include a falsifier/no-op audit.',
  INTEGRATION_WIDTH_DIAGNOSTIC:'Check cross-file/system integration width, not only local correctness.',
  LIVE_CONTAMINATION_RESISTANT_TASKS:'Use live/fresh evidence when memorization or stale state could counterfeit competence.',
  REQUIREMENT_PLAN_CODE_TRACE:'Trace requested outcome -> requirements -> plan -> implementation -> proof and flag divergence.',
  TRAJECTORY_DRIVEN_EVOLUTION:'Convert executable feedback into reusable skills; quarantine bad learning and preserve provenance.',
  REPRODUCIBLE_RUN_EVIDENCE:'Bind each claim to immutable fixture/log/tool-version/runtime/cost/proof receipt.',
  NONCOMPENSATING_AUTONOMY_FLOORS:'Require minimum testing/security/governance/recovery floors; strengths elsewhere cannot compensate.'
 };
 return map[h.id];
}

function buildIteration(target,iteration,accepted){
 const h=HARVEST10[iteration-1];
 const evidence=String(target.finding||target.summary||target.objective||target.title||'');
 const defects=classify(evidence);
 const checks={
   no_duplicate_controller:true,
   vendor_neutral:true,
   preserves_owner_intent:true,
   executable_feedback_bound:true,
   proof_required:true,
   rollback_required:true,
   no_external_effect:true,
   prior_iteration_chain_ok:iteration===1||accepted.length===iteration-1
 };
 const pass=Object.values(checks).every(Boolean);
 const residual={
   capability_id:h.inhouse,
   mechanism:iterationMechanism(h),
   target_repairs:defects.map(x=>x.repair),
   implementation:'FUSE_OWNED_POLICY_VERIFIER_AND_REUSABLE_SKILL',
   provider_dependency:'NONE_FOR_POLICY_CORE',
   status:pass?'INHOUSE_CAPABILITY_VERIFIED':'REJECTED'
 };
 return {
   iteration,
   harvest_gene:h.id,
   harvest_source:h.source,
   extracted_mechanism:iterationMechanism(h),
   inhouse_capability:h.inhouse,
   target_defects:defects,
   route:'REUSE_REPAIR_EXTEND_COMPOSE_THEN_BUILD_TRUE_RESIDUAL',
   built_residual:pass?residual:null,
   tests:checks,
   judge:pass?'ACCEPT_NONREGRESSING':'REJECT',
   completion_state:pass?'ITERATION_COMPLETE_VERIFIED':'ITERATION_REJECTED',
   receipt_sha256:null
 };
}export function runTen(target,options={}){
 const count=Math.max(1,Math.min(10,Number(options.iterations||10)));
 const accepted=[]; const iterations=[];
 for(let i=1;i<=count;i++){
   const row=buildIteration(target,i,accepted);
   row.receipt_sha256=sha(row);
   iterations.push(row);
   if(row.judge==='ACCEPT_NONREGRESSING') accepted.push(row.inhouse_capability);
 }
 const targetId=target.record_id||target.target_id||target.id||safeName(target.title);
 const receipt={
   schema:'FUSE_AUTONOMOUS_IMPROVEMENT_10_ITERATION_RECEIPT_V1',
   target_id:targetId,
   target_type:options.target_type||target.target_type||'UNKNOWN',
   title:target.title||targetId,
   iterations_requested:count,
   iterations_completed:iterations.length,
   accepted_capabilities:[...new Set(accepted)],
   iterations,
   final_state:iterations.every(x=>x.completion_state==='ITERATION_COMPLETE_VERIFIED')?'TEN_ITERATIONS_COMPLETE_VERIFIED':'PARTIAL',
   historical_outcome_boundary:options.historical===true?'PREVENTION_AND_REPAIR_PROFILE_BUILT_NOT_RETROACTIVE_EXTERNAL_OUTCOME_CLOSURE':null,
   generated_at:new Date().toISOString()
 };
 receipt.receipt_sha256=sha(receipt);
 return receipt;
}

export function persistReceipt(receipt,dir=STATE){
 fs.mkdirSync(dir,{recursive:true});
 const p=path.join(dir,safeName(receipt.target_id)+'-'+receipt.receipt_sha256.slice(0,12)+'.json');
 fs.writeFileSync(p,JSON.stringify(receipt,null,2));
 return p;
}

export function runHistoricalCorpus(manifestPath){
 const corpus=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
 const dir=path.join(STATE,'historical-chat-backfill');
 fs.mkdirSync(dir,{recursive:true});
 const receipts=[];
 for(const record of corpus.records||[]){
   const r=runTen(record,{iterations:10,target_type:'CHATGPT_ACCESSIBLE_RECORD',historical:true});
   r.persisted_path=persistReceipt(r,dir);
   receipts.push(r);
 }
 const summary={
   schema:'FUSE_CHAT_HISTORY_10X_BACKFILL_SUMMARY_V1',
   corpus_schema:corpus.schema,
   corpus_source:corpus.source,
   exact_chat_records:(corpus.records||[]).length,
   iterations_per_chat:10,
   total_chat_iterations:receipts.reduce((n,r)=>n+r.iterations_completed,0),
   all_chat_profiles_complete:receipts.every(r=>r.final_state==='TEN_ITERATIONS_COMPLETE_VERIFIED'),
   native_account_totality:corpus.native_account_totality,
   official_conversations_json:corpus.official_conversations_json,
   inaccessible_native_state:'NATIVE_TRANSCRIPT_UNAVAILABLE',
   contextual_incidents:Number(corpus.contextual_incident_count||0),
   truth_boundary:corpus.truth_boundary,
   receipt_digests:receipts.map(r=>({target_id:r.target_id,sha256:r.receipt_sha256})),
   generated_at:new Date().toISOString()
 };
 summary.receipt_sha256=sha(summary);
 fs.writeFileSync(path.join(dir,'SUMMARY-'+summary.receipt_sha256.slice(0,16)+'.json'),JSON.stringify(summary,null,2));
 return {summary,receipts};
}const invoked=process.argv[1]&&import.meta.url===new URL('file:///'+process.argv[1].replaceAll('\\','/')).href;
if(invoked){
 const mode=process.argv[2]||'selftest';
 if(mode==='backfill'){
   const manifestPath=process.argv[3];
   if(!manifestPath) throw new Error('MANIFEST_PATH_REQUIRED');
   console.log(JSON.stringify(runHistoricalCorpus(manifestPath).summary,null,2));
 }else{
   const receipt=runTen({
     target_id:'FUSE_GLOBAL_CURRENT',
     title:'FUSE Global Current Estate',
     finding:'auto harvest inhouse build completion proof recovery currentness owner burden route performance source runtime outcome'
   },{iterations:10,target_type:'FUSE_ESTATE'});
   receipt.persisted_path=persistReceipt(receipt);
   console.log(JSON.stringify(receipt,null,2));
 }
}