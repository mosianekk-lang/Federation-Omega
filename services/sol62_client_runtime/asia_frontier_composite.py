from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


SCHEMA = "SOL62_ASIA_FRONTIER_COMPOSITE_V1"
BENCHMARK_SCHEMA = "SOL62_ASIA_FRONTIER_MATCHED_COURT_V1"


class Disposition(str, Enum):
    REUSE = "REUSE"
    REBIND = "REBIND"
    REPAIR = "REPAIR"
    EXTEND = "EXTEND"
    COMPOSE = "COMPOSE"
    HARVEST = "HARVEST"
    BUILD_MINIMUM = "BUILD_MINIMUM"
    REJECT = "REJECT"


@dataclass(frozen=True)
class FrontierGene:
    gene_id: str
    country: str
    organization: str
    system: str
    capability_family: str
    mechanism: str
    target_organs: tuple[str, ...]
    disposition: Disposition
    evidence_url: str
    evidence_date: str
    maturity: str = "PUBLIC_MECHANISM_REFERENCE"

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["disposition"] = self.disposition.value
        return row


@dataclass(frozen=True)
class MatchedDimension:
    dimension: str
    matched_samples: int
    candidate_noninferior: bool
    candidate_significant_wins: int = 0
    critical_regressions: int = 0


ASIA_FRONTIER_COHORT: tuple[FrontierGene, ...] = (
    FrontierGene(
        "AF-CHN-KIMI-001", "China", "Moonshot AI", "Kimi K3 / Agent Swarm",
        "PARALLEL_AGENT_EXECUTION", "dynamic_large_scale_subagent_swarm",
        ("ALPHA_OMEGA", "FUSE_SOVEREIGN_PLANE", "WORK_PLANE", "PORTFOLIO_V2"),
        Disposition.EXTEND, "https://www.kimi.com/en/help/agent/agent-swarm", "2026-09-23",
    ),
    FrontierGene(
        "AF-CHN-KIMI-002", "China", "Moonshot AI", "Kimi Code K2.8 / K3",
        "CONTEXT_CONTINUITY", "ultra_long_context_with_externalized_working_set",
        ("MEMORY_CONTINUUM", "PORTABLE_STATE", "SOL62"),
        Disposition.COMPOSE, "https://www.kimi.com/code/docs/en/kimi-code/whats-new.html", "2026-09-11",
    ),
    FrontierGene(
        "AF-CHN-KIMI-003", "China", "Moonshot AI", "Kimi Code Remote Control",
        "CROSS_DEVICE_CONTINUITY", "remote_session_takeover_without_mission_restart",
        ("CARRIER_FEDERATION", "SOL62", "FUSE_MOBILE"),
        Disposition.EXTEND, "https://www.kimi.com/code/docs/en/kimi-code/whats-new.html", "2026-09-09",
    ),
    FrontierGene(
        "AF-CHN-KIMI-004", "China", "Moonshot AI", "Kimi K2.8 / K3",
        "ADAPTIVE_REASONING", "task_risk_scaled_thinking_effort",
        ("SOL62", "PORTFOLIO_V2", "THROUGHPUT_INTELLIGENCE"),
        Disposition.EXTEND, "https://www.kimi.com/code/docs/en/kimi-code/whats-new.html", "2026-09-11",
    ),
    FrontierGene(
        "AF-CHN-SEED-001", "China", "ByteDance Seed", "Seed2.1",
        "REAL_WORLD_EVALUATION", "live_workflow_over_static_benchmark_evaluation",
        ("CFBE", "PROOFOS", "REALITY_JUDGE"),
        Disposition.EXTEND, "https://seed.bytedance.com/en/blog/seed2-1-officially-released-advancing-ai-productivity", "2026-06-23",
    ),
    FrontierGene(
        "AF-CHN-SEED-002", "China", "ByteDance Seed", "Seed2.1",
        "SOFTWARE_ENGINEERING", "requirement_to_code_debug_validate_end_to_end",
        ("FUSE_FORGE", "CODEFORGE", "PROOFOS"),
        Disposition.EXTEND, "https://seed.bytedance.com/en/seed2_1", "2026-06-23",
    ),
    FrontierGene(
        "AF-CHN-SEED-003", "China", "ByteDance Seed", "Seed2.0 Lite",
        "MULTIMODAL_AGENT", "unified_video_image_audio_text_plus_gui_agent",
        ("FUSE_VISION", "CREATIVE_CAPABILITY_BUS", "COMPUTER_USE"),
        Disposition.EXTEND, "https://seed.bytedance.com/en/seed2", "2026-04-30",
    ),
    FrontierGene(
        "AF-CHN-QWEN-001", "China", "Alibaba Qwen", "Qwen Code",
        "SOFTWARE_ENGINEERING", "terminal_agent_bugfix_refactor_complex_task_loop",
        ("FUSE_FORGE", "CODEFORGE", "TERMINAL_EXECUTION"),
        Disposition.EXTEND, "https://qwenlm.github.io/qwen-code-docs/en/blog/quickstart/thinks-like-a-programmer/", "2026-01-30",
    ),
    FrontierGene(
        "AF-CHN-QODER-001", "China", "Alibaba Cloud", "Qoder CN",
        "SOVEREIGN_ENTERPRISE_DEV", "multi_model_private_vpc_coding_plane",
        ("CAPABILITY_REGISTRY", "PRIVATE_PROVIDER_CELLS", "FUSE_FORGE"),
        Disposition.REUSE, "https://www.alibabacloud.com/help/en/lingma/introduction-of-lingma", "2026-08-26",
    ),
    FrontierGene(
        "AF-CHN-BAIDU-001", "China", "Baidu", "Comate",
        "SPEC_AND_PLAN", "clarify_plan_align_then_execute",
        ("FORMATION", "ALPHA_OMEGA", "MISSION_IR"),
        Disposition.REUSE, "https://developer.baidu.com/article/detail.html?id=6240252", "2026-03-17",
    ),
    FrontierGene(
        "AF-CHN-BAIDU-002", "China", "Baidu", "Comate Explore Subagent",
        "DEEP_RETRIEVAL", "web_search_fetch_skill_mcp_exploration",
        ("EVIDENCEOPS", "RETRIEVAL", "MCP", "CFBE"),
        Disposition.EXTEND, "https://developer.baidu.com/article/detail.html?id=6240252", "2026-03-17",
    ),
    FrontierGene(
        "AF-CHN-DEEPSEEK-001", "China", "DeepSeek", "deepseek-harness",
        "SANDBOX_EXECUTION", "deny_first_subprocess_sandbox_then_scoped_escalation",
        ("SANDBOX_EXECUTION", "FDOF", "SICF"),
        Disposition.EXTEND, "https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/notes/implemented/feature/2026-07-06-sandbox.md", "2026-07-06",
    ),
    FrontierGene(
        "AF-CHN-DEEPSEEK-002", "China", "DeepSeek", "deepseek-harness Code Runtime",
        "TOOL_RUNTIME", "typed_optional_code_runtime_capability_seam",
        ("CAPABILITY_REGISTRY", "TOOL_ADAPTERS", "SANDBOX_EXECUTION"),
        Disposition.COMPOSE, "https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/code-runtime.md", "2026-09-17",
    ),
    FrontierGene(
        "AF-CHN-TENCENT-001", "China", "Tencent", "Hy3",
        "ADAPTIVE_REASONING", "hybrid_fast_and_slow_thinking_route",
        ("SOL62", "PORTFOLIO_V2", "ALPHA_OMEGA"),
        Disposition.EXTEND, "https://www.tencent.com/tencent-hunyuan-officially-releases-hy3-advancing-agent-capabilities-and-deeper-product-integration/", "2026-07-06",
    ),
    FrontierGene(
        "AF-CHN-TENCENT-002", "China", "Tencent", "Hy3",
        "INFERENCE_EFFICIENCY", "moe_active_parameter_cost_performance_optimization",
        ("PORTFOLIO_V2", "COST_GOVERNOR", "THROUGHPUT_INTELLIGENCE"),
        Disposition.EXTEND, "https://www.tencent.com/tencent-hunyuan-officially-releases-hy3-advancing-agent-capabilities-and-deeper-product-integration/", "2026-07-06",
    ),
    FrontierGene(
        "AF-JPN-SAKANA-001", "Japan", "Sakana AI", "Fugu Max / Fugu Ultra v2",
        "MODEL_ORCHESTRATION", "pareto_capability_cost_model_orchestration",
        ("PORTFOLIO_V2", "FUSE_ECOSYSTEM", "CAPABILITY_REGISTRY"),
        Disposition.EXTEND, "https://sakana.ai/fugu-max-release/", "2026-09-11",
    ),
    FrontierGene(
        "AF-JPN-SAKANA-002", "Japan", "Sakana AI", "Fugu",
        "COLLECTIVE_INTELLIGENCE", "dynamic_specialist_model_and_agent_synthesis",
        ("COGNITIVE_COUNCIL", "PORTFOLIO_V2", "ALPHA_OMEGA"),
        Disposition.EXTEND, "https://sakana.ai/nvidia-open-model-innovation/", "2026-07-16",
    ),
    FrontierGene(
        "AF-JPN-SAKANA-003", "Japan", "Sakana AI", "RSI Lab / AI Scientist",
        "AUTONOMOUS_RESEARCH", "experiment_falsify_learn_recursive_improvement",
        ("OMEGA_SCIENTIST", "FORMATION", "CFBE", "PROOFOS"),
        Disposition.EXTEND, "https://sakana.ai/rsi-lab/", "2026-09-19",
    ),
    FrontierGene(
        "AF-JPN-NEC-001", "Japan", "NEC", "cotomi Agent / cotomi Act",
        "BROWSER_AUTOMATION", "demonstration_to_safe_replayable_browser_workflow",
        ("COMPUTER_USE", "FUSE_WORKSPACE", "PROOFOS"),
        Disposition.BUILD_MINIMUM, "https://jpn.nec.com/press/202608/20260818_01.html", "2026-08-18",
    ),
    FrontierGene(
        "AF-JPN-NEC-002", "Japan", "NEC", "cotomi Agent",
        "CROSS_SYSTEM_AUTOMATION", "unstructured_input_to_multi_system_web_execution",
        ("COMPUTER_USE", "WORK_PLANE", "CAPABILITY_REGISTRY"),
        Disposition.EXTEND, "https://jpn.nec.com/press/202608/20260818_01.html", "2026-08-18",
    ),
    FrontierGene(
        "AF-JPN-NTT-001", "Japan", "NTT", "tsuzumi 2",
        "LOCAL_PRIVATE_MULTIMODAL", "compact_single_gpu_private_document_vision",
        ("LOCAL_LLM", "FUSE_VISION", "PRIVATE_PROVIDER_CELLS"),
        Disposition.HARVEST, "https://group.ntt/en/newsrelease/2026/05/19/260519a.html", "2026-05-19",
    ),
    FrontierGene(
        "AF-JPN-SB-001", "Japan", "SB Intuitions / SoftBank", "Sarashina3 / Cloud PF Type A",
        "SOVEREIGN_DEPLOYMENT", "data_operation_and_technology_sovereignty_cell",
        ("PRIVATE_PROVIDER_CELLS", "SECURITY", "CAPABILITY_REGISTRY"),
        Disposition.REUSE, "https://www.sbintuitions.co.jp/en/news/press/20260416_01/", "2026-04-16",
    ),
    FrontierGene(
        "AF-JPN-SB-002", "Japan", "SB Intuitions", "Sarashina3 Series",
        "SPECIALIST_MODEL_PORTFOLIO", "guard_embedding_rerank_generation_specialists",
        ("CAPABILITY_REGISTRY", "RETRIEVAL", "REALITY_GUARD", "PORTFOLIO_V2"),
        Disposition.EXTEND, "https://www.sbintuitions.co.jp/en/news/press/20260630_01/", "2026-06-30",
    ),
    FrontierGene(
        "AF-JPN-RAKUTEN-001", "Japan", "Rakuten", "Rakuten AI 3.0",
        "REGIONAL_MODEL_SPECIALIZATION", "japanese_optimized_open_moe_code_and_document_model",
        ("MODEL_MARKET", "LOCAL_LLM", "CFBE"),
        Disposition.HARVEST, "https://global.rakuten.com/corp/news/press/2026/0317_01.html", "2026-03-17",
    ),
)


REQUIRED_BENCHMARK_DIMENSIONS: tuple[str, ...] = (
    "REPOSITORY_LEVEL_SOFTWARE_ENGINEERING",
    "LONG_HORIZON_TASK_COMPLETION",
    "TOOL_USE_RELIABILITY",
    "BROWSER_COMPUTER_USE",
    "MULTIMODAL_UNDERSTANDING",
    "SWARM_PARALLELISM",
    "CONTEXT_CONTINUITY",
    "DEEP_RETRIEVAL",
    "SPECIFICATION_AND_PLANNING",
    "TEST_DEBUG_VALIDATE_LOOP",
    "SANDBOX_AND_PRIVILEGE_CONTROL",
    "CRASH_RECOVERY_AND_RESUME",
    "CROSS_CARRIER_FAILOVER",
    "DURABLE_EXECUTION",
    "COST_PER_SUCCESSFUL_TASK",
    "LATENCY_TO_ACCEPTED_RESULT",
    "LOCAL_PRIVATE_OPERATION",
    "SOVEREIGN_DEPLOYMENT",
    "SECURITY_AND_SAFETY",
    "OBSERVABILITY_AND_PROVENANCE",
    "MEMORY_CURRENTNESS",
    "SELF_IMPROVEMENT_WITH_FALSIFICATION",
    "AUTONOMOUS_RESEARCH",
    "MODEL_ORCHESTRATION",
    "PROVIDER_PORTABILITY",
    "OWNER_INTERVENTION",
    "REGIONAL_LANGUAGE_LOCALIZATION",
    "ENTERPRISE_INTEGRATION",
    "FALSE_GREEN_RESISTANCE",
    "ENERGY_RESOURCE_EFFICIENCY",
    "VALUE_PER_COST",
    "TERMINAL_RESULT_DELIVERY",
)


def cohort_summary() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "count": len(ASIA_FRONTIER_COHORT),
        "countries": sorted({row.country for row in ASIA_FRONTIER_COHORT}),
        "organizations": sorted({row.organization for row in ASIA_FRONTIER_COHORT}),
        "dimensions": list(REQUIRED_BENCHMARK_DIMENSIONS),
        "truth_boundary": (
            "PUBLIC_MECHANISM_REFERENCE_NE_IMPLEMENTED_NE_MATCHED_BENCHMARK_PASS_"
            "NE_JUDGE_ACK_NE_SOURCE_ADMITTED_NE_LIVE_RUNTIME_NE_MARKET_SUPERIORITY"
        ),
    }


def compile_residual_plan(
    *,
    already_covered_mechanisms: Iterable[str] = (),
) -> tuple[dict[str, object], ...]:
    covered = {item.strip().lower() for item in already_covered_mechanisms if item.strip()}
    rows: list[dict[str, object]] = []
    for gene in ASIA_FRONTIER_COHORT:
        disposition = gene.disposition
        status = "RESIDUAL_CANDIDATE"
        if gene.mechanism.lower() in covered:
            disposition = Disposition.REUSE
            status = "OVERLAP_COLLAPSED"
        rows.append(
            {
                **gene.to_dict(),
                "effective_disposition": disposition.value,
                "status": status,
                "authority_granted": False,
                "market_superiority_proven": False,
            }
        )
    return tuple(rows)


def matched_frontier_verdict(
    results: Sequence[MatchedDimension],
    *,
    minimum_samples_per_dimension: int = 12,
    minimum_significant_wins: int = 8,
) -> dict[str, object]:
    by_dimension = {row.dimension: row for row in results}
    missing = [d for d in REQUIRED_BENCHMARK_DIMENSIONS if d not in by_dimension]
    under_sampled = [
        d
        for d, row in by_dimension.items()
        if d in REQUIRED_BENCHMARK_DIMENSIONS and row.matched_samples < minimum_samples_per_dimension
    ]
    regressions = [
        d
        for d, row in by_dimension.items()
        if d in REQUIRED_BENCHMARK_DIMENSIONS
        and (not row.candidate_noninferior or row.critical_regressions > 0)
    ]
    significant_wins = sum(
        max(0, row.candidate_significant_wins)
        for row in results
        if row.dimension in REQUIRED_BENCHMARK_DIMENSIONS
    )
    proven = (
        not missing
        and not under_sampled
        and not regressions
        and significant_wins >= minimum_significant_wins
    )
    return {
        "schema": BENCHMARK_SCHEMA,
        "status": "PROVEN_AGAINST_FROZEN_ASIA_FRONTIER_COMPOSITE" if proven else "UNPROVEN",
        "market_superiority_proven": proven,
        "missing_dimensions": missing,
        "under_sampled_dimensions": sorted(under_sampled),
        "regression_dimensions": sorted(regressions),
        "significant_wins": significant_wins,
        "minimum_significant_wins": minimum_significant_wins,
        "minimum_samples_per_dimension": minimum_samples_per_dimension,
        "truth_boundary": (
            "COMPOSITE_COURT_PASS_NE_UNIVERSAL_ALL_COMPANIES_FOREVER; "
            "new material releases require a new frozen cohort and rerun"
        ),
    }


def priority_waves() -> Mapping[str, tuple[str, ...]]:
    return {
        "P0": (
            "AF-CHN-KIMI-001",
            "AF-CHN-SEED-001",
            "AF-CHN-DEEPSEEK-001",
            "AF-JPN-SAKANA-001",
            "AF-JPN-NEC-001",
            "AF-JPN-SB-002",
        ),
        "P1": (
            "AF-CHN-KIMI-002",
            "AF-CHN-KIMI-004",
            "AF-CHN-SEED-002",
            "AF-CHN-QWEN-001",
            "AF-CHN-BAIDU-002",
            "AF-CHN-TENCENT-001",
            "AF-CHN-TENCENT-002",
            "AF-JPN-SAKANA-002",
            "AF-JPN-SAKANA-003",
            "AF-JPN-NEC-002",
            "AF-JPN-NTT-001",
        ),
        "P2": (
            "AF-CHN-KIMI-003",
            "AF-CHN-SEED-003",
            "AF-CHN-QODER-001",
            "AF-CHN-BAIDU-001",
            "AF-CHN-DEEPSEEK-002",
            "AF-JPN-SB-001",
            "AF-JPN-RAKUTEN-001",
        ),
    }
