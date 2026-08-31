from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import json
import os
from typing import Any

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import (
    compile_mission_result_identity,
    lookup_mission_result,
    record_mission_result,
)
from federation.bubbles_frontier_hyperperformance import DeterministicResultCache, WorkCell
from federation.idea_to_system_compiler import compile_idea_to_system


SCHEMA = "FEDERATION-MISSION-IR-RESULT-FABRIC-SHADOW-CERTIFICATION-1"
REFERENCE_SOURCE_MAIN = "8da9ddc38b46ffef535064a5d13f65ba130a1b1c"
OBJECTIVE = (
    "Audit the current Federation execution architecture for duplicated mission contracts, fragmented "
    "proof/context/authority semantics, and MissionIR reuse opportunities without performing provider mutations."
)
NOW = "2026-08-31T20:02:00+02:00"
FRESH_UNTIL = "2026-09-02T00:00:00+02:00"
EXPIRED_AT = "2026-08-31T00:00:00+02:00"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _mission():
    return compile_idea_to_system(
        OBJECTIVE,
        source_frontier=f"main@{REFERENCE_SOURCE_MAIN}",
        domain_hint="RESEARCH",
    ).mission_ir


def _nodes() -> tuple[BubblesWorkNode, ...]:
    return (
        BubblesWorkNode(
            "RF-SOURCE",
            "Source-bound deterministic plan",
            "SOURCE",
            "Compile the source-bound no-effect shadow plan.",
            priority=1,
        ),
        BubblesWorkNode(
            "RF-CONTROL",
            "Demand-paged control plan",
            "CONTROL",
            "Compile only the next control page after source binding.",
            dependencies=("RF-SOURCE",),
            priority=2,
        ),
    )


def _cells() -> tuple[WorkCell, ...]:
    return (
        WorkCell("cell-local-a", ("local-a", "deterministic", "region-local")),
        WorkCell("cell-local-b", ("local-b", "deterministic", "region-local-b")),
    )


def _input_identity() -> dict[str, object]:
    return {
        "work_graph": [asdict(item) for item in _nodes()],
        "cells": [asdict(item) for item in _cells()],
        "paged_state_refs": [
            "GitHub:main",
            "GEN2:MISSION_CAPSULES:CAPSULE-FED-AUDIT-001",
        ],
    }


def _policy_identity() -> dict[str, object]:
    return {
        "shard_width": 1,
        "failure_domain_exclusions": [],
        "provider_policy": "NO_PROVIDER_EFFECT",
        "result_reuse_effect_class": "NO_EFFECT",
    }


def _environment_identity() -> dict[str, object]:
    return {
        "runtime": "python-3.12",
        "execution_adapter": "FEDERATION-MISSION-EXECUTION-SHADOW-V1",
        "result_adapter": "FEDERATION-MISSION-RESULT-IDENTITY-V1",
        "mode": "HOSTED_ZERO_EFFECT_SHADOW",
    }


def build_receipt(*, certification_source_sha: str) -> dict[str, Any]:
    mission = _mission()
    cache = DeterministicResultCache()
    proof_refs = (
        f"source:{REFERENCE_SOURCE_MAIN}",
        "proof:mission-execution-shadow",
    )
    exact = compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(),
        policy_identity=_policy_identity(),
        environment_identity=_environment_identity(),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=FRESH_UNTIL,
    )

    first = lookup_mission_result(cache, exact, now=NOW)
    compiler_invocations = 0
    if first.state != "MISS":
        raise AssertionError(first)

    compiler_invocations += 1
    shadow = shadow_compile_mission_execution(mission, _nodes(), _cells())
    result_payload = _stable_json(asdict(shadow))
    result_sha = sha256(result_payload.encode("utf-8")).hexdigest()
    recorded = record_mission_result(
        cache,
        exact,
        result_ref=f"memory://mission-shadow/{result_sha}",
        result_sha256=result_sha,
        proof_refs=proof_refs,
        recorded_at=NOW,
        now=NOW,
    )
    replay = lookup_mission_result(cache, exact, now=NOW)

    changed_input = compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity={**_input_identity(), "paged_state_revision": "changed"},
        policy_identity=_policy_identity(),
        environment_identity=_environment_identity(),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=FRESH_UNTIL,
    )
    input_miss = lookup_mission_result(cache, changed_input, now=NOW)

    changed_policy = compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(),
        policy_identity={**_policy_identity(), "shard_width": 2},
        environment_identity=_environment_identity(),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=FRESH_UNTIL,
    )
    policy_miss = lookup_mission_result(cache, changed_policy, now=NOW)

    changed_environment = compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(),
        policy_identity=_policy_identity(),
        environment_identity={**_environment_identity(), "adapter_build": "changed"},
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=FRESH_UNTIL,
    )
    environment_miss = lookup_mission_result(cache, changed_environment, now=NOW)

    moved_source = replace(
        mission,
        source_frontier="main@ffffffffffffffffffffffffffffffffffffffff",
    ).normalized()
    changed_source = compile_mission_result_identity(
        moved_source,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(),
        policy_identity=_policy_identity(),
        environment_identity=_environment_identity(),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=FRESH_UNTIL,
    )
    source_miss = lookup_mission_result(cache, changed_source, now=NOW)

    expired = compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(),
        policy_identity=_policy_identity(),
        environment_identity=_environment_identity(),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=EXPIRED_AT,
    )
    freshness_hold = lookup_mission_result(cache, expired, now=NOW)

    semantic_pass = all(
        (
            first.state == "MISS" and first.reuse is False,
            recorded.state == "RECORDED",
            replay.state == "HIT" and replay.reuse is True,
            replay.cache_key == exact.cache_key,
            replay.result_sha256 == result_sha,
            replay.proof_refs == tuple(sorted(proof_refs)),
            input_miss.state == "MISS",
            policy_miss.state == "MISS",
            environment_miss.state == "MISS",
            source_miss.state == "MISS",
            freshness_hold.state == "HOLD_FRESHNESS_EXPIRED",
            compiler_invocations == 1,
            shadow.provider_effect_authorized is False,
            shadow.financial_effect_authorized is False,
            shadow.publication_authorized is False,
        )
    )
    receipt = {
        "schema": SCHEMA,
        "state": "HOSTED_SHADOW_RESULT_FABRIC_PASS" if semantic_pass else "HOSTED_SHADOW_RESULT_FABRIC_FAIL",
        "certification_source_sha": certification_source_sha,
        "reference_source_main": REFERENCE_SOURCE_MAIN,
        "mission_id": mission.mission_id,
        "mission_ir_sha256": mission.digest(),
        "result_identity": exact.canonical_mapping(),
        "initial_lookup_state": first.state,
        "record_state": recorded.state,
        "replay_lookup_state": replay.state,
        "replay_reuse": replay.reuse,
        "compiler_invocations": compiler_invocations,
        "replay_recompute_avoided": replay.reuse and compiler_invocations == 1,
        "compiler_output_chars_not_regenerated": len(result_payload) if replay.reuse else 0,
        "result_sha256": result_sha,
        "proof_refs_preserved": list(replay.proof_refs),
        "invalidation": {
            "input_change": input_miss.state,
            "policy_change": policy_miss.state,
            "environment_change": environment_miss.state,
            "source_change": source_miss.state,
            "freshness_expiry": freshness_hold.state,
        },
        "semantic_pass": semantic_pass,
        "cache_scope": "IN_PROCESS_SHADOW_ONLY",
        "persistent_cache_proven": False,
        "provider_cache_proven": False,
        "serving_route_changed": False,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
        "publication_authorized": False,
        "external_effects": 0,
        "stable_promotion_allowed": False,
        "truth_boundary": (
            "This hosted shadow proves deterministic MissionIR step identity can reuse an exact in-process NO_EFFECT "
            "execution-plan result while source/input/policy/environment changes miss and freshness expiry holds. "
            "It does not prove durable/distributed cache persistence, provider-result caching, production latency gains, "
            "or serving cutover. The reported character count is compiler output not regenerated on exact replay, not "
            "a claim that equivalent model-context payload was avoided."
        ),
    }
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def main() -> int:
    print(
        json.dumps(
            build_receipt(certification_source_sha=os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
