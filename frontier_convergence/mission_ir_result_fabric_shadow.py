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
        BubblesWorkNode("RF-SOURCE", "Source-bound deterministic plan", "SOURCE", "Compile the source-bound no-effect shadow plan.", priority=1),
        BubblesWorkNode("RF-CONTROL", "Demand-paged control plan", "CONTROL", "Compile only the next control page after source binding.", dependencies=("RF-SOURCE",), priority=2),
    )


def _cells() -> tuple[WorkCell, ...]:
    return (
        WorkCell("cell-local-a", ("local-a", "deterministic", "region-local")),
        WorkCell("cell-local-b", ("local-b", "deterministic", "region-local-b")),
    )


def _input_identity(extra: dict[str, object] | None = None) -> dict[str, object]:
    value = {
        "work_graph": [asdict(item) for item in _nodes()],
        "cells": [asdict(item) for item in _cells()],
        "paged_state_refs": ["GitHub:main", "GEN2:MISSION_CAPSULES:CAPSULE-FED-AUDIT-001"],
    }
    value.update(extra or {})
    return value


def _policy_identity(extra: dict[str, object] | None = None) -> dict[str, object]:
    value = {
        "shard_width": 1,
        "failure_domain_exclusions": [],
        "provider_policy": "NO_PROVIDER_EFFECT",
        "result_reuse_effect_class": "NO_EFFECT",
    }
    value.update(extra or {})
    return value


def _environment_identity(extra: dict[str, object] | None = None) -> dict[str, object]:
    value = {
        "runtime": "python-3.12",
        "execution_adapter": "FEDERATION-MISSION-EXECUTION-SHADOW-V1",
        "result_adapter": "FEDERATION-MISSION-RESULT-IDENTITY-V1",
        "mode": "HOSTED_ZERO_EFFECT_SHADOW",
    }
    value.update(extra or {})
    return value


def _identity(mission, *, input_extra=None, policy_extra=None, env_extra=None, fresh_until=FRESH_UNTIL):
    return compile_mission_result_identity(
        mission,
        step_id="COMPILE_SHADOW_EXECUTION_PLAN",
        input_identity=_input_identity(input_extra),
        policy_identity=_policy_identity(policy_extra),
        environment_identity=_environment_identity(env_extra),
        proof_scope="MISSION_EXECUTION_SHADOW_RECEIPT",
        fresh_until=fresh_until,
    )


def build_receipt(*, certification_source_sha: str) -> dict[str, Any]:
    mission = _mission()
    cache = DeterministicResultCache()
    proof_refs = (f"source:{REFERENCE_SOURCE_MAIN}", "proof:mission-execution-shadow")
    exact = _identity(mission)

    first = lookup_mission_result(cache, exact, now=NOW)
    if first.state != "MISS":
        raise AssertionError(first)

    compiler_invocations = 1
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

    input_miss = lookup_mission_result(cache, _identity(mission, input_extra={"paged_state_revision": "changed"}), now=NOW)
    policy_miss = lookup_mission_result(cache, _identity(mission, policy_extra={"shard_width": 2}), now=NOW)
    environment_miss = lookup_mission_result(cache, _identity(mission, env_extra={"adapter_build": "changed"}), now=NOW)
    moved_source = replace(mission, source_frontier="main@ffffffffffffffffffffffffffffffffffffffff").normalized()
    source_miss = lookup_mission_result(cache, _identity(moved_source), now=NOW)
    freshness_hold = lookup_mission_result(cache, _identity(mission, fresh_until=EXPIRED_AT), now=NOW)

    canonical_proof_refs = tuple(sorted(proof_refs))
    semantic_pass = all(
        (
            first.state == "MISS" and not first.reuse,
            recorded.state == "RECORDED",
            replay.state == "HIT" and replay.reuse,
            replay.cache_key == exact.cache_key,
            replay.result_sha256 == result_sha,
            replay.proof_refs == canonical_proof_refs,
            input_miss.state == "MISS",
            policy_miss.state == "MISS",
            environment_miss.state == "MISS",
            source_miss.state == "MISS",
            freshness_hold.state == "HOLD_FRESHNESS_EXPIRED",
            compiler_invocations == 1,
            not shadow.provider_effect_authorized,
            not shadow.financial_effect_authorized,
            not shadow.publication_authorized,
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
        "proof_refs_preserved": list(canonical_proof_refs),
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
            "Hosted shadow proves exact deterministic MissionIR-step reuse in the existing in-process NO_EFFECT cache. "
            "Source/input/policy/environment drift miss and freshness expiry holds. Proof refs are canonicalized and "
            "preserved. This does not prove durable/distributed cache persistence, provider-result caching, production "
            "latency gains or serving cutover; the character count is compiler output not regenerated on exact replay."
        ),
    }
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def main() -> int:
    print(json.dumps(build_receipt(certification_source_sha=os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
