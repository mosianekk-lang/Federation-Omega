from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

SCHEMA = "FUSE_ASTRA_MAX_ALGORITHM_GENOME_V1"
VERSION = "1.0.0"

OFFICIAL_PUBLIC_SOURCES = (
    "https://openai.com/index/gpt-6-astra/",
    "https://help.openai.com/en/articles/20001275/",
    "https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt",
    "https://developers.openai.com/api/docs/models/gpt-6-astra",
    "https://developers.openai.com/api/docs/guides/latest-model",
    "https://developers.openai.com/api/docs/guides/tools-computer-use",
    "https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra",
)

@dataclass(frozen=True, slots=True)
class AstraGene:
    gene_id: str
    name: str
    category: str
    mechanism: str
    tags: tuple[str, ...]
    bindings: tuple[str, ...]
    disposition: str = "COMPOSE"
    maturity: str = "CANDIDATE_RESIDUAL"

    def score(self, text: str) -> int:
        haystack = text.lower()
        return sum(1 for tag in self.tags if tag.lower() in haystack)

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["tags"] = list(self.tags)
        row["bindings"] = list(self.bindings)
        return row


_ROWS = (
    ("Maximum Reasoning Effort Router","REASONING","Raise reasoning effort to the strongest available qualified tier for difficult end-to-end work.",("reasoning","max","xhigh","complex"),("SOL_6_2","COGNITIVE_COUNCIL","PORTFOLIO_V2")),
    ("Complexity-to-Effort Compiler","REASONING","Compile complexity, uncertainty and stakes into adaptive reasoning depth instead of fixed effort.",("complexity","effort","adaptive","uncertainty"),("SOL_6_2","RAEFI")),
    ("Multi-Hypothesis Deep Search","REASONING","Maintain materially different hypotheses until discriminating evidence resolves them.",("hypothesis","search","alternative","deep"),("COGNITIVE_COUNCIL","FORMATION","PROOFOS")),
    ("Focused Clarification Gate","INTENT","Ask only questions that can materially change the outcome; continue independent work meanwhile.",("clarify","question","async","continue"),("MISSION_IR","SOL_6_2","GENESIS")),
    ("Goal Anchor Under Steering","INTENT","Merge steering deltas without replacing the original mission objective or prior constraints.",("steer","goal","anchor","constraint"),("MISSION_IR","CHATBRIDGE","SOL_6_2")),
    ("Side-Question Isolation","INTENT","Answer side questions without dropping or mutating the broader mission.",("side","question","mission","context"),("CHATBRIDGE","MISSION_IR")),
    ("Consequential Decision Hold","INTENT","Continue reversible work but hold when missing input could change a consequential decision.",("consequential","decision","hold","input"),("FDOF","SICF","SOL_6_2")),
    ("Relevant-Context Distiller","CONTEXT","Pull only context that materially affects the current task instead of replaying the full corpus.",("context","relevant","distill","minimal"),("MEMORY_CONTINUUM","BIBLE_FABRIC","CHATBRIDGE")),
    ("Long-Context Working-Set Manager","CONTEXT","Exploit very large context windows while keeping a compact decision working set and provenance pointers.",("context","long","window","working"),("MEMORY_CONTINUUM","PORTABLE_STATE","SOL_6_2")),
    ("Instruction Debloat Tournament","CONTEXT","Challenge stale prompt, AGENTS and skill scaffolding against matched outcomes before retaining it.",("prompt","agents.md","skill","debloat"),("SKILLFORGE","CFBE","HARNESS_TOURNAMENT")),
    ("Code-First Computer Use","COMPUTER_USE","Prefer code-driven UI control for complex repetitive computer use when the carrier supports it.",("computer","code","playwright","pyautogui"),("BROWSER_CONTROL_PLANE","FUSE_WORKSPACE","EXECUTION_POWER_POOLS")),
    ("Structured Computer Tool Fallback","COMPUTER_USE","Fall back to structured mouse/keyboard computer actions when code-driven control is unavailable.",("computer","mouse","keyboard","tool"),("BROWSER_CONTROL_PLANE","FUSE_WORKSPACE")),
    ("Visual-Semantic UI Fusion","COMPUTER_USE","Fuse screenshots with DOM/accessibility semantics and hold on material disagreement.",("visual","screen","dom","accessibility"),("FBCP","PROOFOS","FUSE_WORKSPACE")),
    ("Cross-App Workflow Orchestrator","COMPUTER_USE","Carry one mission across browser, desktop and professional applications without losing state.",("app","workflow","desktop","browser"),("FUSE_SOVEREIGN_PLANE","SOL_6_2","GENESIS")),
    ("Autonomous Install-Test-Troubleshoot Loop","COMPUTER_USE","Install, test, inspect failures and repair software through bounded qualified carriers.",("install","test","troubleshoot","software"),("CODEFORGE","FUSE_WORKSPACE","PROOFOS")),
    ("Frontend QA Computer Court","COMPUTER_USE","Exercise built web UI flows and verify visual and functional behavior after changes.",("frontend","qa","browser","ui"),("BROWSER_CONTROL_PLANE","PROOFOS","REALITY_JUDGE")),
    ("Professional Document Compiler","ARTIFACT","Produce polished documents that follow existing templates and writing standards.",("document","template","professional","writing"),("EVIDENCEOPS","DOCUMENT_FABRIC","PROOFOS")),
    ("Professional Spreadsheet Compiler","ARTIFACT","Produce structured spreadsheets, formulas, analyses and tables aligned to owner templates.",("spreadsheet","excel","analysis","template"),("DATA_FABRIC","ARTIFACT_VAULT","PROOFOS")),
    ("Professional Presentation Compiler","ARTIFACT","Produce succinct structured slide narratives with template and layout adherence.",("presentation","slides","template","narrative"),("CREATIVE_STUDIO","ARTIFACT_VAULT","PROOFOS")),
    ("Artifact Style Matcher","ARTIFACT","Match owner/company writing, visual and structural style from relevant examples only.",("style","brand","template","match"),("MEMORY_CONTINUUM","CREATIVE_STUDIO")),
    ("Visual Judgment QA","ARTIFACT","Judge visual coherence, layout and usability of generated artifacts and interfaces.",("visual","layout","design","qa"),("CREATIVE_STUDIO","PROOFOS")),
    ("Repository Issue-to-Fix Trace","ENGINEERING","Trace a reported defect through code, implement the smallest repair and verify the result.",("bug","repo","fix","verify"),("CODEFORGE","CFBE","GITHUB_AIRLOCK")),
    ("Codebase Understanding Compression","ENGINEERING","Build a compact semantic codebase map before changing source.",("codebase","understand","map","repo"),("CODEFORGE","MEMORY_CONTINUUM")),
    ("Test-Debug-Validation Loop","ENGINEERING","Iterate build, targeted test, failure diagnosis and changed-mechanism repair until proof passes.",("test","debug","validate","repair"),("CODEFORGE","FAILURE_HARVEST","PROOFOS")),
    ("UI Regression Visual Court","ENGINEERING","Pair functional tests with visual browser QA on changed user-facing surfaces.",("ui","regression","visual","test"),("BROWSER_CONTROL_PLANE","PROOFOS")),
    ("Evidence-Backed Web Research","RESEARCH","Browse multiple current sources, preserve provenance and distinguish facts from inference.",("research","browse","source","evidence"),("EVIDENCEOPS","WEB_RESEARCH","PROOFOS")),
    ("Source Contradiction Resolver","RESEARCH","Prioritize direct evidence that discriminates between conflicting sources instead of averaging them.",("source","contradiction","evidence","resolve"),("EVIDENCEOPS","COGNITIVE_COUNCIL")),
    ("Long-Horizon Research Continuation","RESEARCH","Checkpoint and resume multi-step research without requiring the interactive client to stay open.",("research","long","resume","background"),("GENESIS","PORTABLE_STATE","SOL_6_2")),
    ("Parallel Specialist Delegation","ORCHESTRATION","Fan out independent specialist subtasks with isolated context and explicit fan-in.",("parallel","subagent","specialist","delegate"),("FOREST_V2","COGNITIVE_COUNCIL","WORK_PLANE")),
    ("Asynchronous Clarification Continuation","ORCHESTRATION","Continue nondependent lanes while a clarification is outstanding.",("async","clarification","continue","parallel"),("WORK_PLANE","GENESIS","SOL_6_2")),
    ("Work-Mode Long Task Adapter","ORCHESTRATION","Treat long multi-step finished-deliverable work as a durable mission rather than a chat turn.",("work","long","deliverable","agent"),("FUSE_SOVEREIGN_PLANE","SOL_6_2","GENESIS")),
    ("Provider Cell Astra Preference","ORCHESTRATION","Prefer Astra for mission classes where it is current, callable, authorized and cost-appropriate.",("astra","provider","route","model"),("PORTFOLIO_V2","CAPABILITY_TRUTH","FIO")),
    ("Provider-Neutral Astra Fallback","ORCHESTRATION","Preserve Astra-derived mechanisms when Astra itself is unavailable by rerouting to qualified providers.",("astra","fallback","provider","neutral"),("FUSE_SOVEREIGN_PLANE","PORTFOLIO_V2")),
    ("Self-Verification Pass","PROOF","Require a second verification pass over key factual, code, UI or artifact outputs before promotion.",("self","verify","proof","check"),("PROOFOS","REALITY_JUDGE")),
    ("Unsupported-Assumption Surfacer","PROOF","Explicitly surface conclusions not supported by the available records or current evidence.",("assumption","unsupported","evidence","claim"),("EVIDENCEOPS","PROOFOS")),
    ("Semantic Readback Before Completion","PROOF","Verify the resulting external state, not merely successful tool invocation.",("readback","state","complete","verify"),("SOL_6_2","SICF","PROOFOS")),
    ("False-Green Adversarial Review","PROOF","Attack apparently successful results with holdouts, mutation and adversarial cases.",("false","green","adversarial","holdout"),("CFBE","REALITY_JUDGE","PROOFOS")),
    ("Artifact Acceptance Court","PROOF","Validate template adherence, structure, visual quality and content completeness before delivery.",("artifact","acceptance","quality","template"),("PROOFOS","DELIVERY_JOURNAL")),
    ("Aggressive Safe Parallelism","EFFICIENCY","Maximize independent ready-lane concurrency within current authority, privacy, cost and collision boundaries.",("parallel","aggressive","concurrency","ready"),("WORK_PLANE","FDOF","THROUGHPUT_INTELLIGENCE")),
    ("Token-Efficient Working Set","EFFICIENCY","Use compact context and precise outputs to reduce wasted tokens without reducing task completeness.",("token","efficient","context","compact"),("MEMORY_CONTINUUM","RAEFI")),
    ("Fast-Mode Opportunistic Route","EFFICIENCY","Use faster model/runtime modes for latency-sensitive reversible work when quality gates remain satisfied.",("fast","latency","mode","speed"),("PORTFOLIO_V2","RAEFI")),
    ("Cost-per-Accepted-Result Optimizer","EFFICIENCY","Optimize total cost against verified accepted outcome rather than price per token alone.",("cost","accepted","result","value"),("RAEFI","VALUE_LEDGER")),
    ("Scope-Fidelity Guard","SECURITY","Keep actions inside the explicit owner mission and authorized effect scope even under powerful models.",("scope","authority","mission","guard"),("FDOF","SICF","AEGIS_RED_TEAM")),
    ("Computer-Use Risk Governor","SECURITY","Increase confirmation, isolation and readback as computer-use consequence rises.",("computer","risk","confirmation","isolation"),("FDOF","AEGIS_RED_TEAM","PROOFOS")),
    ("Trajectory Monitor Hook","SECURITY","Expose action/reasoning trajectory summaries to independent monitors without making the worker self-certifying.",("trajectory","monitor","action","reasoning"),("AEGIS_RED_TEAM","PROOFOS")),
    ("Browser Prompt-Injection Firewall","SECURITY","Treat webpage instructions as untrusted data unless explicitly promoted by owner/task policy.",("browser","prompt","injection","untrusted"),("BROWSER_CONTROL_PLANE","AEGIS_RED_TEAM")),
    ("Maximum Authorized Capability Mode","GOVERNANCE","Remove unnecessary local throttles while preserving hard authorization, privacy, legal, safety and effect boundaries.",("maximum","authorized","capability","aggressive"),("START_FUSE_ONE","FUSE_SOVEREIGN_PLANE","SOL_6_2")),
    ("No-Goal-Dilution Constraint","GOVERNANCE","Route around provider limitations rather than shrinking the owner objective.",("goal","dilution","provider","constraint"),("FUSE_SOVEREIGN_PLANE","MISSION_IR")),
)

ASTRA_GENES: tuple[AstraGene, ...] = tuple(
    AstraGene(
        gene_id=f"HG-ASTRA-{idx:03d}",
        name=name,
        category=category,
        mechanism=mechanism,
        tags=tags,
        bindings=bindings,
    )
    for idx, (name, category, mechanism, tags, bindings) in enumerate(_ROWS, start=1)
)


def validate_genome(genes: Sequence[AstraGene] = ASTRA_GENES) -> None:
    ids = [g.gene_id for g in genes]
    expected = [f"HG-ASTRA-{idx:03d}" for idx in range(1, len(genes) + 1)]
    if ids != expected:
        raise ValueError("Astra gene ids must be monotonic and contiguous")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Astra gene id")
    if any(g.maturity != "CANDIDATE_RESIDUAL" for g in genes):
        raise ValueError("Astra harvest metadata may not self-promote")
    if any(not g.bindings for g in genes):
        raise ValueError("every Astra gene must bind to existing FUSE organs")


def select_astra_genes(
    objective: str,
    *,
    limit: int = 16,
    genes: Sequence[AstraGene] = ASTRA_GENES,
) -> tuple[AstraGene, ...]:
    if limit <= 0:
        return ()
    ranked = sorted(
        genes,
        key=lambda g: (-g.score(objective), g.category, g.gene_id),
    )
    matched = [g for g in ranked if g.score(objective) > 0]
    if matched:
        return tuple(matched[:limit])
    selected: list[AstraGene] = []
    seen: set[str] = set()
    for gene in ranked:
        if gene.category in seen:
            continue
        seen.add(gene.category)
        selected.append(gene)
        if len(selected) >= limit:
            break
    return tuple(selected)


def genome_summary() -> Mapping[str, object]:
    validate_genome()
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "gene_count": len(ASTRA_GENES),
        "first_id": ASTRA_GENES[0].gene_id,
        "last_id": ASTRA_GENES[-1].gene_id,
        "categories": sorted({g.category for g in ASTRA_GENES}),
        "official_public_sources": list(OFFICIAL_PUBLIC_SOURCES),
        "provider_neutral_clean_room": True,
        "authority_expansion": False,
        "safety_bypass": False,
        "truth_boundary": (
            "PUBLIC_CAPABILITY_HARVEST_NE_MODEL_BOUND; MODEL_BOUND_NE_RUNTIME_VERIFIED; "
            "RUNTIME_VERIFIED_NE_OWNER_VALUE_VERIFIED"
        ),
    }
