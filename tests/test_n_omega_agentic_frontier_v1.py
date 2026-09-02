from benchmarking.cfbe_omega.n_omega_agentic_frontier_v1 import (
    AgenticFrontierCompiler,
    MissionProfile,
    compile_n_directive,
    frontier_summary,
)


def test_frontier_coverage_and_truth_boundary():
    s = frontier_summary()
    assert s["vendor_reference_count"] == 17
    assert s["capability_gene_count"] == 40
    assert s["domain_count"] == 18
    assert s["zero_unrouted"] is True
    assert s["one_mutating_lane"] is True
    assert s["stable_self_promotion_authorized"] is False
    assert s["provider_effect_authorized_by_benchmark"] is False
    assert s["n_omega_cfbe_integrated"] is True


def test_consequential_multiagent_compiles_proof_safe_superstack():
    p = AgenticFrontierCompiler().compile(MissionProfile(
        mission_id="T", domains=frozenset({"ORCHESTRATION", "TOOLS", "SECURITY"}),
        long_running=True, multi_agent=True, tool_heavy=True, consequential=True,
        requires_memory=True, requires_dynamic_models=True, requires_release=True,
    ))
    assert p.max_mutating_lanes == 1
    assert p.external_model_authority == "PROPOSAL_ONLY"
    assert "AGF-034" in p.selected_gene_ids
    assert "AGF-035" in p.selected_gene_ids
    assert "ACTION_SPECIFIC_AUTHORITY" in p.proof_required
    assert "POST_EFFECT_READBACK" in p.proof_required
    assert "DURABLE_CHECKPOINT_RESUME" in p.orchestration
    assert "INDEPENDENT_CHALLENGER" in p.orchestration


def test_provider_gated_requires_native_readback():
    p = AgenticFrontierCompiler().compile(MissionProfile(
        mission_id="P", domains=frozenset({"EXECUTION"}), browser_or_computer=True
    ))
    assert "PROVIDER_IDENTITY" in p.proof_required
    assert "SEMANTIC_PROVIDER_READBACK" in p.proof_required


def test_n_omega_cfbe_bridge_is_integrated_but_independent():
    p = compile_n_directive(MissionProfile(
        mission_id="N", domains=frozenset({"ORCHESTRATION", "EVALUATION"}), multi_agent=True
    ))
    assert p.lifecycle[0] == "CFBE_PREPASS"
    assert "N_COMPILE" in p.lifecycle
    assert p.lifecycle[-2] == "CFBE_POSTPASS"
    assert p.cfbe_role == "INDEPENDENT_BENCHMARK_CHALLENGE_EVOLUTION_GOVERNOR"
    assert p.n_omega_role == "MISSION_COMPILER_EXECUTION_MANAGER"
    assert p.self_certification_allowed is False
    assert p.stable_promotion_requires_owner_value is True


def test_compiler_catalog_unique_and_complete():
    c = AgenticFrontierCompiler()
    c.validate()
    ids = list(c.genes)
    assert len(ids) == len(set(ids)) == 40
    for g in c.genes.values():
        assert g.sources and g.binding and g.proof_gate
