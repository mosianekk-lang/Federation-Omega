from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import (
    BibleRenderer,
    HybridRetrievalPlanner,
    InMemoryEventStore,
    MemoryDocument,
    MemoryEvent,
    ProjectionCompiler,
)

STREAM_ID = "workstream:cfbe-input-compiler"
WORKSTREAM_ID = "CFBE_INPUT_COMPILER"
LEGACY_CURRENT_STATE: dict[str, Any] = {
    "compiler_incumbent": "v2",
    "challenger": "v2.1",
    "challenger_state": "SOURCE_ADMITTED",
    "canonical_replacement": "NOT_PROMOTED",
    "observed_value_gate": "OPEN",
    "last_failed_pr": 895,
    "successful_pr": 900,
    "next_action": "shadow_migrate_into_bible_memory_fabric",
    "memory_fabric_main": "3ba78722e5922f6bafa287dc28578ac169a4c43c",
    "failure_class": "UNMAPPED_PROOFOS_PATH",
    "recovery_pr": 900,
    "current_source": "87b44caddecc1f092b4b7175d5f2531896ebbdab",
}


def _event(
    version: int,
    *,
    event_type: str,
    recorded_at: str,
    payload: dict[str, Any],
    source_refs: tuple[str, ...],
    directive_id: str | None = None,
    mission_id: str = "MISSION-CFBE-INPUT-COMPILER",
    supersedes: tuple[str, ...] = (),
) -> MemoryEvent:
    return MemoryEvent(
        event_id=f"cfbe-input-evt-{version:04d}",
        stream_id=STREAM_ID,
        stream_version=version,
        event_type=event_type,
        recorded_at=recorded_at,
        valid_at=recorded_at,
        idempotency_key=f"cfbe-input-idem-{version:04d}",
        truth_class="EVENT_TRUTH",
        privacy_class="PUBLIC_SAFE",
        payload=payload,
        source_refs=source_refs,
        directive_id=directive_id,
        mission_id=mission_id,
        workstream_id=WORKSTREAM_ID,
        supersedes=supersedes,
    )


def workstream_events() -> tuple[MemoryEvent, ...]:
    """Public-safe source-backed lifecycle for the input-compiler workstream."""
    return (
        _event(
            1,
            event_type="STATE_SET",
            recorded_at="2026-08-31T18:03:24Z",
            payload={
                "compiler_incumbent": "v2",
                "challenger": "NONE",
                "challenger_state": "NONE",
                "canonical_replacement": "NOT_PROMOTED",
                "observed_value_gate": "CLOSED",
            },
            source_refs=("github:pr/893", "github:commit/b4a530ea30fd2c38ddc31b48e8aca08e2a07cdd3"),
            directive_id="DIRECTIVE-INTENT-TO-MISSION-V2",
        ),
        _event(
            2,
            event_type="STATE_SET",
            recorded_at="2026-08-31T18:28:44Z",
            payload={"challenger": "v2.1", "challenger_state": "FIDELITY_CHALLENGE_OPEN"},
            source_refs=("github:pr/895",),
            directive_id="DIRECTIVE-CHALLENGE-V2-FIDELITY",
        ),
        _event(
            3,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T18:51:55Z",
            payload={
                "challenger_state": "SOURCE_CANDIDATE_AIRLOCK_BLOCKED",
                "last_failed_pr": 895,
                "failure_class": "UNMAPPED_PROOFOS_PATH",
            },
            source_refs=("github:pr/895",),
        ),
        _event(
            4,
            event_type="STATE_SET",
            recorded_at="2026-08-31T18:54:03Z",
            payload={"challenger_state": "RESTACKED_CURRENT_MAIN", "recovery_pr": 900},
            source_refs=("github:pr/900",),
        ),
        _event(
            5,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T18:55:02Z",
            payload={
                "challenger_state": "SOURCE_ADMITTED",
                "successful_pr": 900,
                "canonical_replacement": "NOT_PROMOTED",
                "observed_value_gate": "OPEN",
                "current_source": "87b44caddecc1f092b4b7175d5f2531896ebbdab",
            },
            source_refs=("github:pr/900", "github:commit/87b44caddecc1f092b4b7175d5f2531896ebbdab"),
            supersedes=("cfbe-input-evt-0003",),
        ),
        _event(
            6,
            event_type="NEXT_ACTION_SET",
            recorded_at="2026-08-31T18:55:03Z",
            payload={"next_action": "run_observed_owner_language_campaign"},
            source_refs=("github:pr/900",),
        ),
        _event(
            7,
            event_type="NEXT_ACTION_SET",
            recorded_at="2026-08-31T19:30:48Z",
            payload={
                "next_action": "shadow_migrate_into_bible_memory_fabric",
                "memory_fabric_main": "3ba78722e5922f6bafa287dc28578ac169a4c43c",
            },
            source_refs=("github:pr/907", "github:commit/3ba78722e5922f6bafa287dc28578ac169a4c43c"),
            directive_id="DIRECTIVE-CONTINUOUS-EVERGROWING-MEMORY",
        ),
    )


def build_store(events: tuple[MemoryEvent, ...] | None = None) -> InMemoryEventStore:
    store = InMemoryEventStore()
    for event in events or workstream_events():
        store.append(event, expected_version=store.version(event.stream_id))
    return store


def load_public_fidelity_cases(repo_root: str | Path = ".") -> tuple[dict[str, Any], ...]:
    path = Path(repo_root) / "benchmarking/cfbe_omega/input_compiler_fidelity_cases_v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("privacy") != "PUBLIC_SAFE_GENERALIZED_DIRECTIVES_ONLY":
        raise ValueError("FIDELITY_CORPUS_PRIVACY_CONTRACT_MISMATCH")
    return tuple(payload["cases"])


def directive_documents(cases: tuple[dict[str, Any], ...]) -> tuple[MemoryDocument, ...]:
    docs: list[MemoryDocument] = []
    for case in cases:
        prompt = str(case["prompt"])
        docs.append(
            MemoryDocument(
                memory_id=str(case["case_id"]),
                text=prompt,
                truth_class="VERIFIED",
                privacy_class="PUBLIC_SAFE",
                source_refs=("benchmarking/cfbe_omega/input_compiler_fidelity_cases_v1.json",),
                workstream_id=WORKSTREAM_ID,
                mission_id="MISSION-CFBE-INPUT-COMPILER",
                graph_keys=(str(case["expected_intent"]), str(case["expected_effect_class"])),
                lexical_terms=tuple(prompt.split()),
                token_cost=max(1, len(prompt.split())),
            )
        )
    return tuple(docs)


@dataclass(frozen=True, slots=True)
class PairResult:
    pair_id: str
    family: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ShadowCampaignReport:
    schema: str
    workstream_id: str
    pair_count: int
    pass_count: int
    hard_failure_count: int
    semantic_parity: bool
    owner_reconstruction_prompts_in_harness: int
    promotion_state: str
    pairs: tuple[PairResult, ...]


def run_shadow_campaign(repo_root: str | Path = ".") -> ShadowCampaignReport:
    """Run 18 directive-retrieval pairs plus 12 memory/recovery pairs."""
    events = workstream_events()
    store = build_store(events)
    compiler = ProjectionCompiler()
    current = compiler.project(store.stream(STREAM_ID))
    pairs: list[PairResult] = []

    cases = load_public_fidelity_cases(repo_root)
    docs = directive_documents(cases)
    planner = HybridRetrievalPlanner()
    prompt_to_ids: dict[str, set[str]] = {}
    for case in cases:
        prompt_to_ids.setdefault(str(case["prompt"]), set()).add(str(case["case_id"]))
    for case in cases:
        prompt = str(case["prompt"])
        selected = planner.select(
            docs,
            query=prompt,
            token_budget=max(12, len(prompt.split()) * 4),
            workstream_id=WORKSTREAM_ID,
        )
        top_id = selected[0].memory_id if selected else ""
        acceptable = prompt_to_ids[prompt]
        pairs.append(
            PairResult(
                pair_id=f"PAIR-DIRECTIVE-{case['case_id']}",
                family="DIRECTIVE_RETRIEVAL",
                passed=top_id in acceptable,
                detail=f"top={top_id}; acceptable={sorted(acceptable)}",
            )
        )

    parity = current.current == LEGACY_CURRENT_STATE
    pairs.append(PairResult("PAIR-STATE-CURRENT", "CURRENT_STATE", parity, f"projection={current.current}"))

    as_of_v2 = compiler.project(events, as_of_recorded_at="2026-08-31T18:03:24Z")
    pairs.append(
        PairResult(
            "PAIR-ASOF-V2",
            "AS_OF",
            as_of_v2.current.get("compiler_incumbent") == "v2" and as_of_v2.current.get("challenger") == "NONE",
            f"state={as_of_v2.current}",
        )
    )
    as_of_failed = compiler.project(events, as_of_recorded_at="2026-08-31T18:51:55Z")
    pairs.append(
        PairResult(
            "PAIR-ASOF-FAILED-895",
            "AS_OF",
            as_of_failed.current.get("challenger_state") == "SOURCE_CANDIDATE_AIRLOCK_BLOCKED"
            and as_of_failed.current.get("last_failed_pr") == 895,
            f"state={as_of_failed.current}",
        )
    )
    as_of_admitted = compiler.project(events, as_of_recorded_at="2026-08-31T18:55:02Z")
    pairs.append(
        PairResult(
            "PAIR-ASOF-ADMITTED-900",
            "AS_OF",
            as_of_admitted.current.get("challenger_state") == "SOURCE_ADMITTED"
            and as_of_admitted.current.get("successful_pr") == 900,
            f"state={as_of_admitted.current}",
        )
    )

    replay_store = build_store(events)
    replay = replay_store.append(events[-1], expected_version=0)
    pairs.append(PairResult("PAIR-IDEMPOTENT-REPLAY", "IDEMPOTENCY", replay.state == "IDEMPOTENT_REPLAY", f"state={replay.state}"))

    last = events[-1]
    mutated = MemoryEvent(
        event_id=last.event_id,
        stream_id=last.stream_id,
        stream_version=last.stream_version,
        event_type=last.event_type,
        recorded_at=last.recorded_at,
        valid_at=last.valid_at,
        idempotency_key=last.idempotency_key,
        truth_class=last.truth_class,
        privacy_class=last.privacy_class,
        payload={"next_action": "MUTATED"},
        source_refs=last.source_refs,
        proof_refs=last.proof_refs,
        causal_parent_ids=last.causal_parent_ids,
        directive_id=last.directive_id,
        mission_id=last.mission_id,
        workstream_id=last.workstream_id,
        supersedes=last.supersedes,
        contradicts=last.contradicts,
        schema_version=last.schema_version,
    )
    mismatch_ok = False
    try:
        replay_store.append(mutated, expected_version=replay_store.version(STREAM_ID))
    except ValueError as exc:
        mismatch_ok = str(exc) == "MEMORY_IDEMPOTENCY_PARAMETER_MISMATCH"
    pairs.append(PairResult("PAIR-IDEMPOTENCY-MISMATCH", "IDEMPOTENCY", mismatch_ok, "mismatched replay rejected"))

    conflict_store = build_store(events[:1])
    conflict_ok = False
    try:
        conflict_store.append(events[1], expected_version=0)
    except ValueError as exc:
        conflict_ok = str(exc) == "MEMORY_STREAM_VERSION_CONFLICT"
    pairs.append(PairResult("PAIR-OPTIMISTIC-CONFLICT", "CONCURRENCY", conflict_ok, "stale expected version rejected"))

    privacy_ok = False
    private_global = MemoryEvent(
        event_id="privacy-test",
        stream_id="privacy",
        stream_version=1,
        event_type="STATE_SET",
        recorded_at="2026-08-31T19:31:00Z",
        valid_at="2026-08-31T19:31:00Z",
        idempotency_key="privacy-test",
        truth_class="SHADOW",
        privacy_class="GLOBAL",
        payload={"secret": "not-allowed"},
    )
    try:
        private_global.validate()
    except ValueError as exc:
        privacy_ok = str(exc) == "GLOBAL_MEMORY_SENSITIVE_PAYLOAD_REJECTED"
    pairs.append(PairResult("PAIR-PRIVACY-GLOBAL-REJECT", "PRIVACY", privacy_ok, "sensitive global payload rejected"))

    rendered = BibleRenderer().render(
        current,
        doctrine_ref="CFBE-OMEGA-INPUT-COMPILER",
        memory_refs=("github:pr/893", "github:pr/895", "github:pr/900", "github:pr/907"),
    )
    render_ok = rendered["current_state"] == LEGACY_CURRENT_STATE and rendered["projection_hash"] == current.projection_hash
    pairs.append(PairResult("PAIR-BIBLE-RENDER", "BIBLE_RENDER", render_ok, f"schema={rendered['schema']}"))

    reverse = compiler.project(tuple(reversed(events)))
    pairs.append(
        PairResult(
            "PAIR-REPLAY-ORDER-INDEPENDENT",
            "REPLAY",
            reverse.projection_hash == current.projection_hash,
            f"current={current.projection_hash}; reverse={reverse.projection_hash}",
        )
    )

    supersession_ok = "cfbe-input-evt-0003" in current.superseded_event_ids
    pairs.append(
        PairResult(
            "PAIR-SUPERSESSION-PRESERVED",
            "SUPERSESSION",
            supersession_ok,
            f"superseded={current.superseded_event_ids}",
        )
    )

    tight = planner.select(docs, query="deploy production", token_budget=4, workstream_id=WORKSTREAM_ID)
    budget_used = sum(doc.token_cost for doc in tight)
    pairs.append(
        PairResult(
            "PAIR-TIGHT-CONTEXT-BUDGET",
            "CONTEXT_BUDGET",
            budget_used <= 4,
            f"selected={[doc.memory_id for doc in tight]}; tokens={budget_used}",
        )
    )

    if len(pairs) != 30:
        raise AssertionError(f"SHADOW_PAIR_COUNT_EXPECTED_30_GOT_{len(pairs)}")
    failures = tuple(pair for pair in pairs if not pair.passed)
    return ShadowCampaignReport(
        schema="CFBE-BIBLE-MEMORY-SHADOW-CAMPAIGN-V1",
        workstream_id=WORKSTREAM_ID,
        pair_count=len(pairs),
        pass_count=len(pairs) - len(failures),
        hard_failure_count=len(failures),
        semantic_parity=parity,
        owner_reconstruction_prompts_in_harness=0,
        promotion_state="SHADOW_ENGINEERING_PASS" if not failures else "SHADOW_ENGINEERING_HOLD",
        pairs=tuple(pairs),
    )
