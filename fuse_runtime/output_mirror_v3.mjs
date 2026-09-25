import { createMirrorV2 } from './output_mirror_v2.mjs';

export const POWER_DIARY_SOURCE_SHA256='3d95834ff0070e06c8de385b9240c65490d9b71ceb63fa5e3364f407261c0495';
export const POWER_DIARY_CHAPTER_COUNT=40;
const FAMILY_MAP={
  maximum_capability:[1,3,16,28,35,37,40],
  owner_intent_fidelity:[2,8,36,40],
  durable_mission_continuity:[4,30,31,32,33,34,35],
  solve_before_report:[5,25,35],
  reuse_and_convergence:[6,7,19,35],
  creative_fidelity:[8,9,26,27,38],
  research_evidence:[10,35,37],
  investigation_rigor:[11,18,35],
  production_engineering:[12,13,14,24,39],
  provider_neutral_routing:[15,17,26,35],
  independent_challenge:[18,27,28,35],
  clean_room_harvest:[20],
  commercial_product:[21],
  owner_attention:[22,23,29,35,40],
  truthful_completion:[14,24,25,31,35,39,40],
  command_semantics:[30,31,32,33,34],
  reality_clause:[36,40]
};
const ALL_CHAPTERS=[...new Set(Object.values(FAMILY_MAP).flat())].sort((a,b)=>a-b);
function gate(required,pass,reason,evidence=null){
  if(!required)return {required:false,state:'NA',reason:null,evidence};
  return {required:true,state:pass?'PASS':'FAIL',reason:pass?null:reason,evidence};
}
function exactCommand(prompt){
  const p=String(prompt||'').trim().toLowerCase();
  if(p==='n')return 'N';
  if(p==='do all')return 'DO_ALL';
  if(p==='finish')return 'FINISH';
  if(p==='better'||p==='more'||p==='more / better')return 'BETTER';
  if(p==='restore'||p.startsWith('restore '))return 'RESTORE';
  return null;
}function diaryProfile(prompt,baseProfile={}){
  const p=String(prompt||'');
  const creative=/\b(creative|design|fashion|visual|image|video|film|music|brand|logo|ui\/ux|art|storyboard|render|animation|architecture)\b/i.test(p);
  const research=/\b(research|sources?|evidence|verify|fact[- ]check|literature|current facts?|external facts?)\b/i.test(p);
  const investigation=/\b(investigat|forensic|attribut|hypothes|contradiction|root cause|incident|evidence trail)\b/i.test(p);
  const commercial=/\b(commercial|business|customer|pricing|revenue|market share|moneti[sz]|product launch|distribution|unit economics)\b/i.test(p);
  const harvest=/\b(harvest|reverse engineer|clean[- ]room|mechanism|benchmark market|market[- ]leading|capability gap)\b/i.test(p);
  const createSystem=/\b(create|build|design|architect|new)\b.*\b(system|engine|agent|framework|platform|runtime|workflow|product)\b/i.test(p);
  const providerNeutral=/\b(provider[- ]neutral|multi[- ]provider|replaceable provider|federat|cross[- ]surface|multi[- ]surface)\b/i.test(p);
  const highConsequence=baseProfile.sensitive===true||baseProfile.effectful===true||/\b(legal|medical|health|financial|security|cyber|production|disciplin|arbitration|criminal|safety[- ]critical)\b/i.test(p);
  const outcomeRequired=/\b(finish|complete|completed|operational|deploy|deployed|outcome|done|production[- ]ready)\b/i.test(p);
  const substantial=p.trim().length>=24||baseProfile.execution_required===true||creative||research||investigation||commercial||harvest||outcomeRequired;
  return {creative,research,investigation,commercial,harvest,createSystem,providerNeutral,highConsequence,outcomeRequired,substantial,command:exactCommand(p)};
}
function selectedSurfaceCount(result){
  const selected=result?.surface_portfolio?.selected;
  return Array.isArray(selected)?selected.length:0;
}
function hasSourceEvidence(result){
  return (Array.isArray(result?.source_refs)&&result.source_refs.length>0) ||
    (Array.isArray(result?.currentness?.source_refs)&&result.currentness.source_refs.length>0) ||
    result?.research_evidence?.verified===true;
}
function hasReusableHistory(result,meta){
  return result?.reuse_gate?.checked===true || result?.historical_recall?.checked===true ||
    result?.existing_work_reused===true || meta?.bootstrap_guard?.ok===true;
}
export function createMirrorV3({trustContext}){
  const v2=createMirrorV2({trustContext});
  return {
    assess(prompt,result,meta={},cfg={}){
      const base=v2.assess(prompt,result,meta,cfg);
      if(cfg.enabled!==true)return {...base,schema:'FUSE_OUTPUT_MIRROR_V3'};
      const r=result&&typeof result==='object'?result:{};
      const dp=diaryProfile(prompt,base.task_profile||{});
      const hardBoundary=base.state==='PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY';
      let baseIssues=Array.isArray(base.issues)?[...base.issues]:[];
      if(dp.command)baseIssues=baseIssues.filter(issue=>!String(issue).startsWith('INTENT_FIDELITY:'));
      const baseRelease=baseIssues.length===0;
      const intentPass=dp.command?true:base.dimensions?.intent_fidelity?.state==='PASS';
      const challenged=!!r.tournament||(Array.isArray(r.challengers)&&r.challengers.length>0)||
        (Array.isArray(r.acceptance_tests)&&r.acceptance_tests.length>0)||String(meta.depth||'').toUpperCase()==='DEEP';
      const independentlyChallenged=r.independent_challenger?.verified===true||
        (Array.isArray(r.challengers)&&r.challengers.length>0)||(Array.isArray(r.acceptance_tests)&&r.acceptance_tests.length>0);
      const machineRoute=r.machine_route_available===true||r.next_machine_route_available===true;
      const manual=Array.isArray(r.manual_user_tasks)?r.manual_user_tasks:[];
      const hasPortfolio=selectedSurfaceCount(r)>0||!!r.mission_graph||!!r.capability_census;
      const reuseChecked=hasReusableHistory(r,meta);
      const errorOutstanding=!!r.error||!!r.mirror_recompile_error||
        (r.reason&&!hardBoundary&&r.completion_state!=='COMPLETE_VERIFIED');
      const creativePass=!dp.creative||hardBoundary||(
        (r.creative_direction||r.route==='CREATIVE'||r.provider_independent_master) &&
        (r.provider_independent_master||r.editable_master||r.source_master||r.surface_portfolio)
      );
      const researchPass=!dp.research||hardBoundary||hasSourceEvidence(r);
      const investigationPass=!dp.investigation||hardBoundary||(
        Array.isArray(r.observations)&&Array.isArray(r.hypotheses)&&
        Array.isArray(r.alternative_hypotheses)&&Array.isArray(r.contradictions)&&r.confidence!=null
      );
      const providerPass=!dp.providerNeutral||hardBoundary||selectedSurfaceCount(r)>=2||r.provider_neutral_contract===true;
      const challengePass=!dp.highConsequence||hardBoundary||independentlyChallenged;
      const harvestPass=!dp.harvest||hardBoundary||(
        r.harvest_contract?.clean_room===true&&r.harvest_contract?.provenance_preserved===true&&
        r.harvest_contract?.mechanism_extracted===true
      );
      const commercialPass=!dp.commercial||hardBoundary||(
        r.commercial_checks?.customer_problem===true&&r.commercial_checks?.distribution===true&&
        r.commercial_checks?.operating_cost===true&&r.commercial_checks?.measurable_value===true
      );
      const outcomePass=!dp.outcomeRequired||hardBoundary||r.completion_state==='COMPLETE_VERIFIED'||r.proof_state==='COMPLETE_VERIFIED';
      const commandPass=!dp.command||hardBoundary||(
        meta.bootstrap_guard?.ok===true &&
        (dp.command!=='FINISH'||r.completion_state==='COMPLETE_VERIFIED'||r.route==='OUTPUT_MIRROR_HOLD') &&
        (dp.command!=='BETTER'||!!r.mirror_strengthening||challenged) &&
        (dp.command!=='DO_ALL'||!!r.mission_graph||!!r.execution_dag) &&
        (dp.command!=='RESTORE'||reuseChecked) &&
        (dp.command!=='N'||reuseChecked)
      );
      const diary_contracts={
        maximum_capability:gate(dp.substantial,hasPortfolio||hardBoundary,'AVAILABLE_CAPABILITY_CENSUS_OR_ROUTE_PORTFOLIO_NOT_EVIDENCED',{selected_surfaces:selectedSurfaceCount(r)}),
        owner_intent_fidelity:gate(true,intentPass,'OWNER_INTENT_FIDELITY_FAILED',base.dimensions?.intent_fidelity||null),
        durable_mission_continuity:gate(!!dp.command,meta.bootstrap_guard?.ok===true||hardBoundary,'DURABLE_MISSION_BOOTSTRAP_NOT_EVIDENCED',{command:dp.command}),
        solve_before_report:gate(dp.substantial,!errorOutstanding||hardBoundary,'MACHINE_SOLVABLE_ERROR_OR_BLOCKER_ESCAPED_TO_DELIVERY'),
        reuse_and_convergence:gate(dp.createSystem||!!dp.command,reuseChecked||hardBoundary,'RECALL_BEFORE_CREATE_OR_CONTINUATION_NOT_EVIDENCED'),
        creative_fidelity:gate(dp.creative,creativePass,'CREATIVE_TARGET_OR_PROVIDER_INDEPENDENT_MASTER_NOT_PRESERVED'),
        research_evidence:gate(dp.research,researchPass,'RESEARCH_RESULT_LACKS_SOURCE_OR_CURRENTNESS_EVIDENCE'),
        investigation_rigor:gate(dp.investigation,investigationPass,'INVESTIGATION_LACKS_OBSERVATION_HYPOTHESIS_ALTERNATIVE_CONTRADICTION_CONFIDENCE_CHAIN'),
        production_engineering:gate(base.task_profile?.code_task===true,base.dimensions?.design_code_health?.state!=='FAIL'&&base.dimensions?.testing?.state!=='FAIL'&&base.dimensions?.proof_evidence?.state!=='FAIL','PRODUCTION_ENGINEERING_COURT_FAILED'),
        provider_neutral_routing:gate(dp.providerNeutral,providerPass,'PROVIDER_NEUTRAL_REQUEST_LACKS_MULTI_SURFACE_OR_PROVIDER_NEUTRAL_CONTRACT'),
        independent_challenge:gate(dp.highConsequence,challengePass,'HIGH_CONSEQUENCE_RESULT_LACKS_INDEPENDENT_CHALLENGER'),
        clean_room_harvest:gate(dp.harvest,harvestPass,'HARVEST_REQUEST_LACKS_CLEAN_ROOM_PROVENANCE_AND_MECHANISM_EVIDENCE'),
        commercial_product:gate(dp.commercial,commercialPass,'COMMERCIAL_RESULT_LACKS_PRODUCT_VALUE_DISTRIBUTION_COST_EVIDENCE'),
        owner_attention:gate(true,!(machineRoute&&manual.length>0),'OWNER_TASK_SURFACED_WHILE_MACHINE_ROUTE_EXISTS',{manual_user_tasks:manual.length}),
        truthful_completion:gate(true,!r.overclaim&&outcomePass&&base.dimensions?.proof_evidence?.state!=='FAIL','COMPLETION_OR_PROOF_STATE_OVERCLAIMED'),
        command_semantics:gate(!!dp.command,commandPass,'SHORT_COMMAND_SEMANTICS_NOT_PRESERVED',{command:dp.command}),
        reality_clause:gate(true,r.overclaim!==true&&cfg.reality_clause_preserved!==false,'NON_OVERRIDABLE_REALITY_OR_TRUTH_BOUNDARY_VIOLATION')
      };
      const diaryIssues=Object.entries(diary_contracts).filter(([,v])=>v.required&&v.state==='FAIL').map(([k,v])=>'DIARY_'+k.toUpperCase()+':'+v.reason);
      const allIssues=[...baseIssues,...diaryIssues];
      const release=baseRelease&&diaryIssues.length===0;
      return {...base,schema:'FUSE_OUTPUT_MIRROR_V3',version:String(cfg.version||'3.0.0'),
        release_allowed:release,state:release?(hardBoundary?'PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY':'PASS_BEST_AVAILABLE_RESULT'):'FAIL_RECOMPILE_OUTPUT',issues:allIssues,
        power_diary:{source_sha256:cfg.power_diary?.source_sha256||POWER_DIARY_SOURCE_SHA256,chapter_count:40,
          covered_chapters:ALL_CHAPTERS,family_count:Object.keys(FAMILY_MAP).length,families:FAMILY_MAP},
        diary_profile:dp,diary_contracts,
        required_diary_contracts:Object.values(diary_contracts).filter(x=>x.required).length,
        passed_diary_contracts:Object.values(diary_contracts).filter(x=>x.required&&x.state==='PASS').length};
    }
  };
}