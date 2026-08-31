from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence

from federation.mission_ir import ContextBudgetIR, MissionIR


_SCHEMA = "FEDERATION-IDEA-TO-SYSTEM-PLAN-V1"
_STRATEGIES = frozenset({"REUSE", "EXTEND", "DISCOVER_THEN_BUILD_SMALLEST"})
_STABLE_STATES = frozenset(
    {
        "VERIFIED",
        "VERIFIED_CURRENT",
        "CURRENT_STABLE",
        "SOURCE_VERIFIED",
        "OPERATIONAL_VERIFIED",
        "ALREADY_STRONG",
    }
)

_INTENT_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "SOFTWARE_BUILD": ("app", "api", "code", "software", "platform", "tool", "system", "algorithm", "build"),
    "AUTOMATION": ("automate", "automation", "workflow", "trigger", "agent", "bot", "orchestrate"),
    "RESEARCH": ("research", "investigate", "benchmark", "compare", "find", "search", "study", "audit"),
    "DATA": ("data", "database", "dataset", "analytics", "reporting", "reconcile", "spreadsheet"),
    "CREATIVE": ("design", "image", "video", "poster", "brand", "creative", "fashion", "presentation"),
    "DOCUMENT": ("document", "report", "proposal", "letter", "brief", "submission", "pdf", "docx"),
}

_CLASS_CAPABILITIES: Mapping[str, tuple[str, ...]] = {
    "SOFTWARE_BUILD": (
        "CODE_ARCHAEOLOGY",
        "CODE_SANDBOX",
        "SCAFFOLD_BUILD",
        "TEST_EVALUATION",
        "SUPPLY_CHAIN_GATE",
        "PRODUCTIZATION",
    ),
    "AUTOMATION": (
        "WORKFLOW_ORCHESTRATION",
        "EVENT_TRIGGERING",
        "DURABLE_REPLAY",
        "FAILURE_RECOVERY",
        "TOOL_GUARDRAILS",
    ),
    "RESEARCH": (
        "SOURCE_DISCOVERY",
        "PROVENANCE",
        "HYPOTHESIS_FALSIFICATION",
        "SYNTHESIS",
    ),
    "DATA": (
        "DATA_DISCOVERY",
        "DATA_INTEGRATION",
        "SCHEMA_ADAPTER",
        "DATA_QUALITY",
    ),
    "CREATIVE": (
        "ASSET_DISCOVERY",
        "CREATIVE_GENERATION",
        "VISUAL_QA",
        "RIGHTS_GATE",
    ),
    "DOCUMENT": (
        "SOURCE_GROUNDING",
        "DOCUMENT_COMPILATION",
        "RENDER_QA",
        "ACCESSIBILITY_QA",
    ),
    "GENERAL": ("SPECIALIST_ROUTING", "RESULT_SYNTHESIS"),
}

_CORE_CAPABILITIES = (
    "INTENT_COMPILATION",
    "UNKNOWN_MAPPING",
    "ACCEPTANCE_SYNTHESIS",
    "CAPABILITY_DISCOVERY",
    "RESOURCE_DISCOVERY",
    "AUTHORITY_COMPILATION",
    "SEMANTIC_READBACK",
    "TRACE_RECEIPT",
    "VALUE_EVALUATION",
)

_DELIVERABLES: Mapping[str, tuple[str, ...]] = {
    "SOFTWARE_BUILD": ("CODE", "TESTS", "RUNBOOK"),
    "AUTOMATION": ("WORKFLOW", "TRIGGERS", "RECOVERY_PLAN"),
    "RESEARCH": ("SOURCE_SET", "EVIDENCE_MATRIX", "SYNTHESIS"),
    "DATA": ("DATA_CONTRACT", "PIPELINE_OR_QUERY", "QUALITY_RECEIPT"),
    "CREATIVE": ("CREATIVE_ARTIFACT", "QA_RECEIPT"),
    "DOCUMENT": ("DOCUMENT_ARTIFACT", "SOURCE_TRACE", "RENDER_RECEIPT"),
    "GENERAL": ("RESULT", "PROOF_RECEIPT"),
}

_HIGH_CONSEQUENCE_TERMS = (
    "pay ",
    "purchase",
    "trade ",
    "transfer money",
    "delete ",
    "terminate ",
    "fire ",
    "sign ",
    "submit ",
    "send email",
    "send message",
    "publish",
    "deploy to production",
    "production deploy",
)

_BOUNDED_EFFECT_TERMS = (
    "build",
    "create",
    "write",
    "edit",
    "update",
    "generate",
    "save",
    "commit",
    "open pull request",
)

_READ_TERMS = (
    "research",
    "investigate",
    "benchmark",
    "compare",
    "review",
    "audit",
    "find",
    "search",
    "analyze",
    "analyse",
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _clean(value: str) -> str:
    return " ".join(str(value).strip().split())


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.lower()))


def _norm_tag(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    capability_id: str
    name: str
    tags: tuple[str, ...]
    evidence_state: str = "CANDIDATE"
    reusable: bool = True
    provider_live: bool = False
    cost_class: str = "UNKNOWN"

    def normalized_tags(self) -> frozenset[str]:
        values = {_norm_tag(self.name), *(_norm_tag(tag) for tag in self.tags)}
        return frozenset(value for value in values if value)


@dataclass(frozen=True, slots=True)
class IdeaIntent:
    objective: str
    intent_classes: tuple[str, ...]
    deliverables: tuple[str, ...]
    constraints: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    success_signals: tuple[str, ...]
    required_capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    requirement: str
    strategy: str
    candidate_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.strategy not in _STRATEGIES:
            raise ValueError("IDEA_SYSTEM_STRATEGY_INVALID")


@dataclass(frozen=True, slots=True)
class IdeaSystemPlan:
    mission_ir: MissionIR
    intent: IdeaIntent
    capability_decisions: tuple[CapabilityDecision, ...]
    workflow_pattern: str
    autonomous_steps: tuple[str, ...]
    owner_questions: tuple[str, ...] = field(default_factory=tuple)

    def canonical_mapping(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "mission_ir": self.mission_ir.canonical_mapping(),
            "intent": asdict(self.intent),
            "capability_decisions": [asdict(item) for item in self.capability_decisions],
            "workflow_pattern": self.workflow_pattern,
            "autonomous_steps": list(self.autonomous_steps),
            "owner_questions": list(self.owner_questions),
            "truth_boundary": {
                "capability_match_is_runtime_proof": False,
                "build_plan_grants_provider_authority": False,
                "generated_code_is_deployed_by_plan": False,
                "market_parity_is_claimed": False,
            },
        }

    def digest(self) -> str:
        return sha256(_stable_json(self.canonical_mapping()).encode("utf-8")).hexdigest()


def infer_intent(idea: str) -> IdeaIntent:
    objective = _clean(idea)
    if not objective:
        raise ValueError("IDEA_REQUIRED")
    lower = objective.lower()
    words = _tokens(objective)

    classes = []
    for intent_class, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in lower or keyword in words for keyword in keywords):
            classes.append(intent_class)
    if not classes:
        classes.append("GENERAL")

    deliverables = sorted({item for cls in classes for item in _DELIVERABLES.get(cls, ())})
    requirements = set(_CORE_CAPABILITIES)
    for cls in classes:
        requirements.update(_CLASS_CAPABILITIES.get(cls, ()))

    constraint_fragments = []
    for fragment in re.split(r"[.;\n]+", objective):
        cleaned = _clean(fragment)
        low = cleaned.lower()
        if any(marker in low for marker in ("must ", "must not", "without ", "only ", "never ", "do not", "don't ", "under ")):
            constraint_fragments.append(cleaned)

    unknowns = []
    assumptions = []
    if not any(marker in lower for marker in ("for users", "for customers", "for staff", "for team", "for my ", "for the ")):
        unknowns.append("TARGET_USER_OR_AUDIENCE")
        assumptions.append("Use the smallest reasonable audience scope until evidence requires expansion.")
    if "SOFTWARE_BUILD" in classes and not any(marker in lower for marker in ("deploy", "host", "cloud", "local", "desktop", "web", "mobile")):
        unknowns.append("TARGET_RUNTIME")
        assumptions.append("Keep build provider-neutral and deployment-gated.")
    if not any(marker in lower for marker in ("success", "acceptance", "done when", "must pass", "target ")):
        unknowns.append("EXPLICIT_ACCEPTANCE_THRESHOLD")
        assumptions.append("Use semantic correctness, no regression, provenance and user-value metrics as provisional gates.")

    success_signals = (
        "SEMANTIC_OUTCOME_MATCH",
        "ZERO_CRITICAL_CONTROL_OMISSIONS",
        "PROOF_COMPLETE",
        "NO_REGRESSION",
        "OWNER_BURDEN_NOT_WORSE",
    )
    return IdeaIntent(
        objective=objective,
        intent_classes=tuple(sorted(classes)),
        deliverables=tuple(deliverables),
        constraints=tuple(sorted(set(constraint_fragments))),
        assumptions=tuple(assumptions),
        unknowns=tuple(unknowns),
        success_signals=success_signals,
        required_capabilities=tuple(sorted(requirements)),
    )


def capability_gap_plan(
    requirements: Iterable[str],
    capabilities: Sequence[CapabilityRecord],
) -> tuple[CapabilityDecision, ...]:
    records = tuple(capabilities)
    decisions = []
    for requirement in sorted({_norm_tag(item) for item in requirements if _norm_tag(item)}):
        matches = tuple(record for record in records if requirement in record.normalized_tags())
        stable = tuple(
            record
            for record in matches
            if record.reusable and _norm_tag(record.evidence_state) in _STABLE_STATES
        )
        reusable = tuple(record for record in matches if record.reusable)

        if stable:
            strategy = "REUSE"
            chosen = stable
            reason = "A reusable proof-qualified capability already satisfies the requirement."
        elif reusable:
            strategy = "EXTEND"
            chosen = reusable
            reason = "A related reusable capability exists but still needs qualification or extension."
        else:
            strategy = "DISCOVER_THEN_BUILD_SMALLEST"
            chosen = ()
            reason = "No reusable capability was supplied; search current assets/standards first, then form only the smallest missing component."

        decisions.append(
            CapabilityDecision(
                requirement=requirement,
                strategy=strategy,
                candidate_ids=tuple(sorted(record.capability_id for record in chosen)),
                reason=reason,
            )
        )
    return tuple(decisions)


def _effect_class(objective: str) -> str:
    lower = f"{objective.lower()} "
    if any(term in lower for term in _HIGH_CONSEQUENCE_TERMS):
        return "CONSEQUENTIAL_EFFECT"
    if any(term in lower for term in _BOUNDED_EFFECT_TERMS):
        return "BOUNDED_EFFECT"
    if any(term in lower for term in _READ_TERMS):
        return "READ_ONLY"
    return "NO_EFFECT"


def _workflow_pattern(intent_classes: tuple[str, ...]) -> str:
    classes = set(intent_classes)
    if {"SOFTWARE_BUILD", "RESEARCH"} <= classes:
        return "MANAGER_RESEARCH_BUILD_WITH_PARALLEL_EVAL"
    if "AUTOMATION" in classes and "SOFTWARE_BUILD" in classes:
        return "MANAGER_WITH_SPECIALIST_TOOLS_AND_DURABLE_WORKFLOW"
    if "CREATIVE" in classes:
        return "MANAGER_WITH_PROVIDER_GATED_CREATIVE_EFFECT"
    if len(classes) > 1:
        return "MANAGER_WITH_SPECIALIST_TOOLS"
    return "SEQUENTIAL_WITH_CHECKPOINTS"


def compile_idea_to_system(
    idea: str,
    capabilities: Sequence[CapabilityRecord] = (),
    *,
    source_frontier: str,
    domain_hint: str | None = None,
) -> IdeaSystemPlan:
    intent = infer_intent(idea)
    decisions = capability_gap_plan(intent.required_capabilities, capabilities)
    effect_class = _effect_class(intent.objective)
    mission_id = f"IDEA-{sha256(intent.objective.encode('utf-8')).hexdigest()[:16].upper()}"
    domain = _norm_tag(domain_hint or intent.intent_classes[0])
    proof_requirements = (
        "ACCEPTANCE_CRITERIA",
        "NO_REGRESSION",
        "SEMANTIC_READBACK",
        "SOURCE_PROVENANCE",
        "TRACE_RECEIPT",
    )
    if effect_class not in {"NO_EFFECT", "READ_ONLY"}:
        proof_requirements += ("ROLLBACK_RECEIPT",)

    authority_requirements = ()
    if effect_class not in {"NO_EFFECT", "READ_ONLY"}:
        authority_requirements = ("TARGET_EFFECT_AUTHORITY",)

    outcome_contract = (
        f"Produce {', '.join(intent.deliverables)} for the stated objective. "
        "Complete only when semantic acceptance, proof, no-regression and value gates pass."
    )
    mission = MissionIR(
        mission_id=mission_id,
        objective=intent.objective,
        domain=domain,
        outcome_contract=outcome_contract,
        source_frontier=_clean(source_frontier),
        privacy_class="UNKNOWN",
        rights_state="UNKNOWN",
        effect_class=effect_class,
        owner_approval_required=effect_class == "CONSEQUENTIAL_EFFECT",
        rollback_required=effect_class not in {"NO_EFFECT", "READ_ONLY"},
        authority_requirements=authority_requirements,
        proof_requirements=proof_requirements,
        value_metrics=(
            "completion_quality",
            "latency_ms",
            "owner_interventions",
            "recovery_success",
            "tool_round_trips",
        ),
        context_budget=ContextBudgetIR(),
        metadata={
            "idea_compiler_schema": _SCHEMA,
            "unknown_count": str(len(intent.unknowns)),
            "capability_requirement_count": str(len(intent.required_capabilities)),
        },
    )
    mission.validate()

    owner_questions = ()
    if effect_class == "CONSEQUENTIAL_EFFECT":
        owner_questions = (
            "Confirm the exact consequential target/effect immediately before execution if authority is not already provider-proven.",
        )

    steps = (
        "COMPILE_INTENT_AND_UNKNOWNS",
        "SYNTHESIZE_ACCEPTANCE_AND_VALUE_GATES",
        "DIFF_REQUIRED_CAPABILITIES_AGAINST_CURRENT_REGISTRY",
        "REUSE_OR_EXTEND_PROVEN_CAPABILITIES",
        "DISCOVER_CURRENT_RESOURCES_FOR_UNSATISFIED_GAPS",
        "BUILD_ONLY_SMALLEST_REMAINING_GAPS",
        "COMPILE_DYNAMIC_WORKFLOW_AND_FAILURE_DOMAINS",
        "RUN_SANDBOX_TESTS_AND_ADVERSARIAL_EVALS",
        "EXECUTE_ONLY_AUTHORIZED_EFFECTS",
        "SEMANTIC_READBACK_AND_ROLLBACK_CHECK",
        "MEASURE_USER_VALUE_AND_RELIABILITY",
        "PROMOTE_HOLD_QUARANTINE_OR_RETIRE_CAPABILITIES",
    )
    return IdeaSystemPlan(
        mission_ir=mission,
        intent=intent,
        capability_decisions=decisions,
        workflow_pattern=_workflow_pattern(intent.intent_classes),
        autonomous_steps=steps,
        owner_questions=owner_questions,
    )
