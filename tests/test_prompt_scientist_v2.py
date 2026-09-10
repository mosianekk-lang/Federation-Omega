from federation.prompt_scientist_v2 import Diagnosis, PromptEvaluation, PromptGenome, PromptRunMetrics, PromptScientistV2




def base():
    return PromptGenome("V4","V3",{
        "OWNER_AUTHORITY":"IMMUTABLE","PROOF_FLOOR":"IMMUTABLE","SECURITY_FLOOR":"IMMUTABLE","PRIVACY_FLOOR":"IMMUTABLE","TRUTH_BOUNDARIES":"IMMUTABLE","PROVIDER_NATIVE_PROOF":"IMMUTABLE","ROLLBACK_REQUIREMENTS":"IMMUTABLE",
        "OUTPUT_POLICY":"HANDOFF_AFTER_PROGRESS","RUNTIME_REENTRY":"NONE","MATURITY_POLICY":"MVP_ONLY"
    })




def test_diagnoses_output_boundary_and_missing_reentry():
    s=PromptScientistV2(); m=PromptRunMetrics("V4","BUILD",output_boundary_stop=True,persistent_runner_available=True,reentry_enqueued=False,commercial_maturity_gap=True)
    d=s.diagnose(m)
    assert Diagnosis.OUTPUT_BOUNDARY_STOP in d
    assert Diagnosis.MISSING_RUNTIME_REENTRY in d
    assert Diagnosis.COMMERCIAL_MATURITY_GAP in d




def test_challengers_modify_genes_not_invariants():
    s=PromptScientistV2(); cs=s.generate_challengers(base(),[Diagnosis.OUTPUT_BOUNDARY_STOP,Diagnosis.MISSING_RUNTIME_REENTRY])
    assert len(cs)==3
    assert all(c.protected_invariants==base().protected_invariants for c in cs)
    assert cs[0].genes["OUTPUT_POLICY"]=="NON_TERMINAL_PROGRESS_CONTINUES"




def test_promotion_requires_measured_green_gain():
    s=PromptScientistV2()
    dims={k:0.8 for k in ("completion","correctness","proof","execution_efficiency","parallel_utilization","owner_burden","recovery","context_efficiency","creative_freedom")}
    inc=PromptEvaluation("V4",dims,("i",))
    better={**dims,"completion":1.0,"owner_burden":1.0,"execution_efficiency":1.0}
    cand=PromptEvaluation("V5",better,("c",))
    d=s.select_for_promotion(inc,[cand],minimum_score_delta=3.0)
    assert d.state=="PROMPT_PROMOTED" and d.selected_candidate_id=="V5"




def test_commercial_regression_is_veto():
    s=PromptScientistV2(); dims={k:0.8 for k in ("completion","correctness","proof","execution_efficiency","parallel_utilization","owner_burden","recovery","context_efficiency","creative_freedom")}
    inc=PromptEvaluation("V4",dims,("i",)); high={k:1.0 for k in dims}
    bad=PromptEvaluation("BAD",high,("b",),commercial_maturity_regression=True)
    assert s.select_for_promotion(inc,[bad]).state=="PROMPT_RETAINED"
