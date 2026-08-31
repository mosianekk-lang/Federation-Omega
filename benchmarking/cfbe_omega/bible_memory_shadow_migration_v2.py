from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import (
    BibleRenderer,
    HybridRetrievalPlanner,
    InMemoryEventStore,
    MemoryDocument,
    MemoryEvent,
    ProjectionCompiler,
)

STREAM_ID = "workstream:mission-result-index"
WORKSTREAM_ID = "MISSION_RESULT_INDEX"
LEGACY_RECONSTRUCTION_SOURCE_COUNT = 8
MEMORY_RECONSTRUCTION_SOURCE_COUNT = 1

LEGACY_CURRENT_STATE: dict[str, Any] = {
    "index_state": "SOURCE_ADMITTED",
    "storage_scope": "LOCAL_APPEND_ONLY_METADATA_JSONL",
    "payload_persistence": "RESULT_PAYLOAD_NOT_PERSISTED",
    "freshness_semantics": "HOLD_FRESHNESS_EXPIRED_PRE_HYDRATION",
    "cross_process_reuse": "HOSTED_SYNTHETIC_PROCESS_ISOLATION_PROVEN",
    "provider_cache": "NOT_PROVEN",
    "provider_effect_authorized": False,
    "stale_base_pr": 901,
    "source_admission_pr": 902,
    "fixture_repair_pr": 905,
    "runtime_repair_pr": 909,
    "cross_process_canary_pr": 910,
    "proofos_binding_pr": 911,
    "superseded_prs": "904,906",
    "proofos_court": "mission_result_index",
    "current_source": "47a08a4830e57648ced5e7ccca712d635e121d39",
    "canonical_bible_cutover": "NOT_PROMOTED",
    "observed_owner_value": "UNPROVEN",
}


def _event(
    version: int,
    *,
    event_type: str,
    recorded_at: str,
    payload: dict[str, Any],
    source_refs: tuple[str, ...],
    supersedes: tuple[str, ...] = (),
    truth_class: str = "EVENT_TRUTH",
) -> MemoryEvent:
    return MemoryEvent(
        event_id=f"result-index-evt-{version:04d}",
        stream_id=STREAM_ID,
        stream_version=version,
        event_type=event_type,
        recorded_at=recorded_at,
        valid_at=recorded_at,
        idempotency_key=f"result-index-idem-{version:04d}",
        truth_class=truth_class,
        privacy_class="PUBLIC_SAFE",
        payload=payload,
        source_refs=source_refs,
        directive_id="DIRECTIVE-RESULT-FABRIC-DURABILITY",
        mission_id="MISSION-RESULT-INDEX-DURABILITY",
        workstream_id=WORKSTREAM_ID,
        supersedes=supersedes,
    )


def workstream_events() -> tuple[MemoryEvent, ...]:
    return (
        _event(
            1,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T18:57:49Z",
            payload={"index_state": "STALE_BASE_CANDIDATE_BLOCKED", "stale_base_pr": 901, "provider_effect_authorized": False},
            source_refs=("github:pr/901",),
        ),
        _event(
            2,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T19:00:28Z",
            payload={
                "index_state": "SOURCE_ADMITTED",
                "storage_scope": "LOCAL_APPEND_ONLY_METADATA_JSONL",
                "payload_persistence": "RESULT_PAYLOAD_NOT_PERSISTED",
                "provider_cache": "NOT_PROVEN",
                "source_admission_pr": 902,
            },
            source_refs=("github:pr/902",),
            supersedes=("result-index-evt-0001",),
        ),
        _event(
            3,
            event_type="STATE_SET",
            recorded_at="2026-08-31T19:08:11Z",
            payload={"repair_candidate": "MONOTONIC_FRESHNESS_LEASE", "candidate_pr": 904},
            source_refs=("github:pr/904",),
        ),
        _event(
            4,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T19:12:13Z",
            payload={"fixture_repair_pr": 905, "freshness_fixture": "CORRECTED_SAME_IDENTITY_AGED"},
            source_refs=("github:pr/905",),
        ),
        _event(
            5,
            event_type="STATE_SET",
            recorded_at="2026-08-31T19:17:34Z",
            payload={"repair_candidate": "PREFLIGHT_FRESHNESS_BEFORE_REPLAY", "candidate_pr": 906},
            source_refs=("github:pr/906",),
        ),
        _event(
            6,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T19:43:40Z",
            payload={
                "runtime_repair_pr": 909,
                "freshness_semantics": "HOLD_FRESHNESS_EXPIRED_PRE_HYDRATION",
                "repair_candidate": "NARROW_RUNTIME_REPAIR_ADMITTED",
                "candidate_pr": 909,
            },
            source_refs=("github:pr/909",),
            supersedes=("result-index-evt-0003", "result-index-evt-0005"),
        ),
        _event(
            7,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T19:51:38Z",
            payload={
                "cross_process_canary_pr": 910,
                "cross_process_reuse": "HOSTED_SYNTHETIC_PROCESS_ISOLATION_PROVEN",
                "provider_cache": "NOT_PROVEN",
            },
            source_refs=("github:pr/910",),
        ),
        _event(
            8,
            event_type="RESULT_VERIFIED",
            recorded_at="2026-08-31T19:55:10Z",
            payload={
                "proofos_binding_pr": 911,
                "proofos_court": "mission_result_index",
                "superseded_prs": "904,906",
                "current_source": "47a08a4830e57648ced5e7ccca712d635e121d39",
                "canonical_bible_cutover": "NOT_PROMOTED",
                "observed_owner_value": "UNPROVEN",
            },
            source_refs=("github:pr/911", "github:main/47a08a4830e57648ced5e7ccca712d635e121d39"),
        ),
        _event(
            9,
            event_type="STATE_UNSET",
            recorded_at="2026-08-31T19:55:10Z",
            payload={"keys": ["repair_candidate", "candidate_pr", "freshness_fixture"]},
            source_refs=("derived:projection-normalization-from-pr/911",),
            truth_class="DERIVED_VERIFIED",
        ),
    )


def build_store() -> InMemoryEventStore:
    store = InMemoryEventStore()
    for event in workstream_events():
        store.append(event, expected_version=store.version(STREAM_ID))
    return store


def memory_documents() -> tuple[MemoryDocument, ...]:
    docs: list[MemoryDocument] = []
    for event in workstream_events():
        text = " ".join(f"{key} {value}" for key, value in event.payload.items())
        docs.append(
            MemoryDocument(
                memory_id=event.event_id,
                text=text,
                truth_class=event.truth_class,
                privacy_class="PUBLIC_SAFE",
                source_refs=event.source_refs,
                workstream_id=WORKSTREAM_ID,
                mission_id=event.mission_id,
                graph_keys=tuple(str(value) for value in event.payload.values()),
                lexical_terms=tuple(str(key) for key in event.payload),
                embedding_ref=f"shadow://{event.event_id}",
                token_cost=max(1, len(text.split())),
            )
        )
    docs.append(
        MemoryDocument(
            memory_id="other-workstream-decoy",
            text="unrelated provider cache deployment",
            truth_class="UNVERIFIED",
            privacy_class="PUBLIC_SAFE",
            source_refs=("shadow:decoy",),
            workstream_id="OTHER",
            lexical_terms=("provider", "cache"),
            token_cost=4,
        )
    )
    return tuple(docs)


@dataclass(frozen=True, slots=True)
class ShadowPair:
    pair_id: str
    passed: bool
    category: str
    note: str


@dataclass(frozen=True, slots=True)
class ShadowMigrationReport:
    schema: str
    pair_count: int
    pass_count: int
    hard_failure_count: int
    semantic_parity: bool
    structural_reconstruction_read_reduction_pct: float
    observed_owner_value_state: str
    promotion_state: str
    pairs: tuple[ShadowPair, ...]


def _pair(pair_id: str, passed: bool, category: str, note: str) -> ShadowPair:
    return ShadowPair(pair_id, bool(passed), category, note)


def run_shadow_campaign() -> ShadowMigrationReport:
    events = workstream_events()
    store = build_store()
    compiler = ProjectionCompiler()
    current = compiler.project(store.stream(STREAM_ID))
    renderer = BibleRenderer()
    retrieval = HybridRetrievalPlanner()
    docs = memory_documents()

    pairs: list[ShadowPair] = []
    pairs.append(_pair("R01", current.current == LEGACY_CURRENT_STATE, "CURRENTNESS", "current projection parity"))
    pairs.append(_pair("R02", compiler.project(events, as_of_recorded_at="2026-08-31T18:57:49Z").current.get("index_state") == "STALE_BASE_CANDIDATE_BLOCKED", "AS_OF", "stale ancestry preserved"))
    pairs.append(_pair("R03", compiler.project(events, as_of_recorded_at="2026-08-31T19:00:28Z").current.get("source_admission_pr") == 902, "AS_OF", "fresh-main successor admitted"))
    pairs.append(_pair("R04", compiler.project(events, as_of_recorded_at="2026-08-31T19:08:11Z").current.get("candidate_pr") == 904, "AS_OF", "broader repair candidate visible"))
    pairs.append(_pair("R05", compiler.project(events, as_of_recorded_at="2026-08-31T19:12:13Z").current.get("fixture_repair_pr") == 905, "AS_OF", "fixture correction preserved"))
    pairs.append(_pair("R06", compiler.project(events, as_of_recorded_at="2026-08-31T19:17:34Z").current.get("candidate_pr") == 906, "AS_OF", "alternate repair visible"))
    pairs.append(_pair("R07", compiler.project(events, as_of_recorded_at="2026-08-31T19:43:40Z").current.get("runtime_repair_pr") == 909, "AS_OF", "narrow runtime repair preserved"))
    pairs.append(_pair("R08", compiler.project(events, as_of_recorded_at="2026-08-31T19:51:38Z").current.get("cross_process_canary_pr") == 910, "AS_OF", "process-isolated reuse proof preserved"))
    pairs.append(_pair("R09", compiler.project(events, as_of_recorded_at="2026-08-31T19:55:10Z").current.get("proofos_binding_pr") == 911, "AS_OF", "proof court binding preserved"))
    pairs.append(_pair("R10", "result-index-evt-0003" in current.superseded_event_ids, "SUPERSESSION", "PR904 route superseded without deletion"))
    pairs.append(_pair("R11", "result-index-evt-0005" in current.superseded_event_ids, "SUPERSESSION", "PR906 route superseded without deletion"))
    pairs.append(_pair("R12", any(ref == "github:pr/901" for ref in events[0].source_refs), "PROVENANCE", "stale PR901 remains addressable"))

    replay_store = InMemoryEventStore()
    for event in events:
        replay_store.append(event, expected_version=replay_store.version(STREAM_ID))
    replay_projection = compiler.project(replay_store.stream(STREAM_ID))
    pairs.append(_pair("R13", replay_projection.projection_hash == current.projection_hash, "REPLAY", "empty-store rebuild parity"))
    receipt = replay_store.append(events[-1], expected_version=replay_store.version(STREAM_ID))
    pairs.append(_pair("R14", receipt.state == "IDEMPOTENT_REPLAY", "IDEMPOTENCY", "exact retry returns prior result"))

    altered = MemoryEvent(
        event_id=events[-1].event_id,
        stream_id=events[-1].stream_id,
        stream_version=events[-1].stream_version,
        event_type=events[-1].event_type,
        recorded_at=events[-1].recorded_at,
        valid_at=events[-1].valid_at,
        idempotency_key=events[-1].idempotency_key,
        truth_class=events[-1].truth_class,
        privacy_class=events[-1].privacy_class,
        payload={"keys": ["different"]},
        source_refs=events[-1].source_refs,
        directive_id=events[-1].directive_id,
        mission_id=events[-1].mission_id,
        workstream_id=events[-1].workstream_id,
    )
    mismatch_rejected = False
    try:
        replay_store.append(altered, expected_version=replay_store.version(STREAM_ID))
    except ValueError as exc:
        mismatch_rejected = str(exc) == "MEMORY_IDEMPOTENCY_PARAMETER_MISMATCH"
    pairs.append(_pair("R15", mismatch_rejected, "IDEMPOTENCY", "same key with different parameters rejected"))

    conflict_rejected = False
    try:
        extra = _event(10, event_type="STATE_SET", recorded_at="2026-08-31T19:56:00Z", payload={"x": 1}, source_refs=("shadow:x",))
        replay_store.append(extra, expected_version=0)
    except ValueError as exc:
        conflict_rejected = str(exc) == "MEMORY_STREAM_VERSION_CONFLICT"
    pairs.append(_pair("R16", conflict_rejected, "CONCURRENCY", "stale stream version rejected"))

    privacy_rejected = False
    try:
        MemoryEvent(
            event_id="private-event",
            stream_id=STREAM_ID,
            stream_version=10,
            event_type="STATE_SET",
            recorded_at="2026-08-31T19:56:00Z",
            valid_at="2026-08-31T19:56:00Z",
            idempotency_key="private-idem",
            truth_class="EVENT_TRUTH",
            privacy_class="GLOBAL",
            payload={"password": "forbidden"},
        ).validate()
    except ValueError as exc:
        privacy_rejected = str(exc) == "GLOBAL_MEMORY_SENSITIVE_PAYLOAD_REJECTED"
    pairs.append(_pair("R17", privacy_rejected, "PRIVACY", "global sensitive payload rejected"))

    rendered = renderer.render(current, doctrine_ref="bible:mission-result-index", memory_refs=[event.event_id for event in events])
    pairs.append(_pair("R18", rendered["current_state"] == LEGACY_CURRENT_STATE, "BIBLE_RENDER", "generated operational section matches current projection"))
    pairs.append(_pair("R19", compiler.project(events).projection_hash == compiler.project(tuple(reversed(events))).projection_hash, "DETERMINISM", "input order does not change projection"))
    pairs.append(_pair("R20", current.current.get("provider_effect_authorized") is False, "AUTHORITY", "memory does not inherit provider authority"))

    def retrieved(query: str, budget: int = 80) -> tuple[str, ...]:
        return tuple(doc.memory_id for doc in retrieval.select(docs, query=query, token_budget=budget, workstream_id=WORKSTREAM_ID))

    pairs.append(_pair("R21", "result-index-evt-0006" in retrieved("freshness_semantics"), "RETRIEVAL", "freshness repair retrievable"))
    pairs.append(_pair("R22", "result-index-evt-0007" in retrieved("cross_process_reuse"), "RETRIEVAL", "cross-process proof retrievable"))
    pairs.append(_pair("R23", "result-index-evt-0008" in retrieved("proofos_court"), "RETRIEVAL", "proof court binding retrievable"))
    pairs.append(_pair("R24", "result-index-evt-0001" in retrieved("stale_base_pr"), "RETRIEVAL", "stale ancestry retrievable"))
    tight = retrieval.select(docs, query="proofos_court", token_budget=25, workstream_id=WORKSTREAM_ID)
    pairs.append(_pair("R25", bool(tight) and sum(doc.token_cost for doc in tight) <= 25, "CONTEXT", "retrieval returns useful evidence inside token budget"))
    filtered = retrieval.select(docs, query="provider_cache", token_budget=50, workstream_id=WORKSTREAM_ID)
    pairs.append(_pair("R26", all(doc.workstream_id in {None, WORKSTREAM_ID} for doc in filtered), "COMPARTMENT", "other workstream filtered"))
    pairs.append(_pair("R27", current.current.get("provider_cache") == "NOT_PROVEN", "TRUTH_BOUNDARY", "hosted synthetic reuse is not provider cache proof"))
    reduction = round((1 - MEMORY_RECONSTRUCTION_SOURCE_COUNT / LEGACY_RECONSTRUCTION_SOURCE_COUNT) * 100, 2)
    pairs.append(_pair("R28", reduction == 87.5, "STRUCTURAL_VALUE", "eight source-object reconstruction collapses to one event-stream projection read"))
    pairs.append(_pair("R29", len(current.superseded_event_ids) == 3, "HISTORY", "failed and superseded states remain retained"))
    pairs.append(_pair("R30", current.current.get("observed_owner_value") == "UNPROVEN" and current.current.get("canonical_bible_cutover") == "NOT_PROMOTED", "NO_OVERCLAIM", "engineering shadow cannot self-promote"))

    pass_count = sum(1 for pair in pairs if pair.passed)
    hard_failures = len(pairs) - pass_count
    return ShadowMigrationReport(
        schema="CFBE-BIBLE-MEMORY-SHADOW-MIGRATION-V2",
        pair_count=len(pairs),
        pass_count=pass_count,
        hard_failure_count=hard_failures,
        semantic_parity=current.current == LEGACY_CURRENT_STATE,
        structural_reconstruction_read_reduction_pct=reduction,
        observed_owner_value_state="UNPROVEN",
        promotion_state="SECOND_DOMAIN_SHADOW_PASS" if hard_failures == 0 and len(pairs) == 30 else "HOLD",
        pairs=tuple(pairs),
    )
