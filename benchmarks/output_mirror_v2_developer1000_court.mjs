import {createMirrorV2} from '../fuse_runtime/output_mirror_v2.mjs';
const dims=['intent_fidelity','execution_finality','proof_evidence','design_code_health','testing','security_privacy','reliability_recovery','performance_cost','currentness_reproducibility','owner_value'];
const langs=['TypeScript','Python','JavaScript','Java','C#','PHP','Shell','C++','HCL','Go'];
const trustContext=p=>({trust_zone:'OWNER_PRIVATE',sensitive_matter:/(tut|legal|evidence)/i.test(String(p||''))});
const mirror=createMirrorV2({trustContext});
const cfg={enabled:true,version:'2.0.0',intent_similarity_floor:0.18,developer1000:{count:1000,sha256:'f7277e2244f1d59849f64f5d4f48af7c20de14ecb8573dba763353bf6084cb7e'},benchmark_court:{cases:1000,dataset_sha256:'d69644412e285ef3a5baeab0b0ef4683ae42280ddca0bdb4a0ea2ce3a5fd6510'}};
function base(prompt,lang){return {objective:prompt,route:'ENGINEERING_VERIFIED',completion_state:'COMPLETE_VERIFIED',
 tasks:['understand','change','test','verify'],next_action:'No residual machine-safe work remains.',acceptance_tests:['correctness','regression','user_value'],
 challengers:['incumbent','counterfactual'],proof:{build:true,tests:true,readback:true,source:true,authority:true,privacy:true,security:true,recovery:true},
 change_batch:'small',maintainability:'improved_or_nonnegative',review_context:true,tests:{status:'passed',regression:true,edge_cases:true},
 authority_proven:true,privacy_check:true,security_review:true,rollback:true,recovery:true,idempotency:'bounded',effect_readback:true,
 performance:{measured:true,before:100,after:20,cost_before:1,cost_after:.8},currentness:{checked:true,observed_at:'2026-09-25T01:30:00+02:00',source_refs:['provider','source']},
 source_refs:['provider','source'],manual_user_tasks:[],machine_route_available:true,language:lang};}
function promptFor(d,lang){
 if(d==='performance_cost')return `Implement this ${lang} change and improve latency by 10x if measured evidence supports it.`;
 if(d==='currentness_reproducibility')return `Implement a ${lang} change using the latest current 2026 source evidence.`;
 if(d==='security_privacy')return `Deploy a bounded ${lang} update for TUT legal evidence with verified privacy and authority.`;
 if(d==='reliability_recovery')return `Deploy and run a bounded ${lang} service update with rollback and effect readback.`;
 return `Implement and verify a bounded ${lang} code change that improves the requested user outcome.`;
}function degrade(d,r){
 if(d==='intent_fidelity')r.objective='Write a recipe for chocolate cake.';
 else if(d==='execution_finality'){r.completion_state='PLANNED_ACCELERATED';r.proof={build:false,tests:false,readback:false};}
 else if(d==='proof_evidence'){r.proof={build:false,tests:false,readback:false};r.overclaim=true;}
 else if(d==='design_code_health'){r.change_batch='large_unbounded';r.maintainability='degraded';r.review_context=false;}
 else if(d==='testing'){r.tests={status:'missing',regression:false};r.proof.tests=false;}
 else if(d==='security_privacy'){r.authority_proven=false;r.privacy_check=false;r.security_review=false;r.proof.authority=false;r.proof.privacy=false;r.proof.security=false;}
 else if(d==='reliability_recovery'){r.rollback=false;r.recovery=false;r.effect_readback=false;r.idempotency='unknown';r.proof.recovery=false;}
 else if(d==='performance_cost')r.performance={measured:false,before:null,after:null};
 else if(d==='currentness_reproducibility'){r.currentness={checked:false,observed_at:null,source_refs:[]};r.source_refs=[];}
 else if(d==='owner_value'){r.completion_state='PLANNED_ACCELERATED';r.manual_user_tasks=['finish manually'];r.next_action='User must finish it.';}
 return r;
}
function v11(prompt,r){
 const issues=[];if(!String(r.objective||'').trim())issues.push('INTENT');if(!r.completion_state)issues.push('STATE');
 if(!(r.tasks||[]).length&&!r.next_action)issues.push('ACTION');
 const hard=['HELD_WITH_EXACT_REASON','PARTIAL_VERIFIED_CONTINUING'].includes(r.completion_state)&&!!(r.reason||r.fallback_reason)&&!!r.next_action;
 const degraded=r.route==='LOCAL_FALLBACK'||r.completion_state==='PLANNED_LOCAL_FALLBACK';if(degraded&&!hard)issues.push('DEGRADED');
 const power=/(best|ultimate|max(?:imum)?|strongest|powerful|complete|do all|finish|audit|build|harvest|repair|investigate|deploy)/i.test(prompt);
 const challenged=!!r.tournament||(r.challengers||[]).length||(r.acceptance_tests||[]).length;if(power&&!challenged&&!hard)issues.push('CHALLENGE');
 return !issues.length;
}const cases=[];let id=0;
for(const d of dims)for(const lang of langs)for(let v=0;v<10;v++){
 const good=v<5,prompt=promptFor(d,lang),candidate=base(prompt,lang);id++;
 if(!good)degrade(d,candidate);
 cases.push({id:`DEV1000-${String(id).padStart(4,'0')}`,dimension:d,language:lang,expected:good,prompt,candidate});
}
function score(which){
 let tp=0,tn=0,fp=0,fn=0;const by=Object.fromEntries(dims.map(d=>[d,{n:0,c:0}]));
 for(const x of cases){
  const pred=which==='v2'?mirror.assess(x.prompt,x.candidate,{},cfg).release_allowed:v11(x.prompt,x.candidate);
  by[x.dimension].n++;by[x.dimension].c+=pred===x.expected?1:0;
  if(pred&&x.expected)tp++;else if(!pred&&!x.expected)tn++;else if(pred&&!x.expected)fp++;else fn++;
 }
 return {accuracy:(tp+tn)/cases.length,tp,tn,fp,fn,by_dimension:Object.fromEntries(Object.entries(by).map(([k,v])=>[k,+(v.c/v.n).toFixed(3)]))};
}
const report={schema:'FUSE_OUTPUT_MIRROR_V2_SELFTEST',cases:cases.length,v1_1:score('v1'),v2:score('v2'),
 developer1000:cfg.developer1000,benchmark_court:cfg.benchmark_court,ran_at:new Date().toISOString()};
console.log(JSON.stringify(report,null,2));