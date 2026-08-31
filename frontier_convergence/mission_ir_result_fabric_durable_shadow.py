from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import (
    lookup_mission_result,
    record_mission_result,
)
from federation.durable_result_cache import SQLiteDeterministicResultCache
from frontier_convergence.mission_ir_result_fabric_shadow import (
    EXPIRED_AT,
    NOW,
    REFERENCE_SOURCE_MAIN,
    _cells,
    _identity,
    _mission,
    _nodes,
    _stable_json,
    build_receipt as build_in_process_receipt,
)

SCHEMA = "FEDERATION-MISSION-IR-RESULT-FABRIC-DURABLE-SHADOW-CERTIFICATION-1"


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def build_receipt(*, certification_source_sha: str) -> dict[str, Any]:
    incumbent = build_in_process_receipt(certification_source_sha=certification_source_sha)
    if not incumbent["semantic_pass"]:
        raise AssertionError("IN_PROCESS_RESULT_FABRIC_BASELINE_REQUIRED")

    mission = _mission()
    exact = _identity(mission)
    shadow = shadow_compile_mission_execution(mission, _nodes(), _cells())
    result_payload = _stable_json(asdict(shadow))
    result_sha = sha256(result_payload.encode("utf-8")).hexdigest()
    result_ref = f"shadow-result://mission-ir/{result_sha}"
    proof_refs = tuple(incumbent["proof_refs_preserved"])

    with tempfile.TemporaryDirectory(prefix="mission-result-fabric-") as temporary:
        db_path = Path(temporary) / "result-fabric.sqlite"
        first_cache = SQLiteDeterministicResultCache(db_path)
        durable_first = lookup_mission_result(first_cache, exact, now=NOW)
        durable_record = record_mission_result(
            first_cache,
            exact,
            result_ref=result_ref,
            result_sha256=result_sha,
            proof_refs=proof_refs,
            recorded_at=NOW,
            now=NOW,
        )
        pre_restart_verify = first_cache.verify()
        first_cache.close()

        reopened = SQLiteDeterministicResultCache(db_path)
        restart_hit = lookup_mission_result(reopened, exact, now=NOW)
        idempotent = record_mission_result(
            reopened,
            exact,
            result_ref=result_ref,
            result_sha256=result_sha,
            proof_refs=proof_refs,
            recorded_at=NOW,
            now=NOW,
        )
        input_miss = lookup_mission_result(
            reopened,
            _identity(mission, input_extra={"paged_state_revision": "durable-change"}),
            now=NOW,
        )
        policy_miss = lookup_mission_result(
            reopened,
            _identity(mission, policy_extra={"shard_width": 2}),
            now=NOW,
        )
        environment_miss = lookup_mission_result(
            reopened,
            _identity(mission, env_extra={"adapter_build": "durable-change"}),
            now=NOW,
        )
        moved_source = replace(
            mission,
            source_frontier="main@ffffffffffffffffffffffffffffffffffffffff",
        ).normalized()
        source_miss = lookup_mission_result(reopened, _identity(moved_source), now=NOW)
        freshness_hold = lookup_mission_result(
            reopened,
            _identity(mission, fresh_until=EXPIRED_AT),
            now=NOW,
        )

        conflict_blocked = False
        try:
            record_mission_result(
                reopened,
                exact,
                result_ref="shadow-result://conflicting-result",
                result_sha256="f" * 64,
                proof_refs=("proof:conflict",),
                recorded_at=NOW,
                now=NOW,
            )
        except ValueError as exc:
            conflict_blocked = str(exc) == "CACHE_RESULT_CONFLICT"
        if not conflict_blocked:
            raise AssertionError("DURABLE_CACHE_CONFLICT_MUST_FAIL_CLOSED")

        post_restart_verify = reopened.verify()
        reopened.close()

        tamper = sqlite3.connect(db_path)
        tamper.execute(
            "UPDATE result_fabric_cache_v1 SET result_ref=? WHERE cache_key=?",
            ("shadow-result://tampered", exact.cache_key),
        )
        tamper.commit()
        tamper.close()

        corrupted = SQLiteDeterministicResultCache(db_path)
        corruption_hold = lookup_mission_result(corrupted, exact, now=NOW)
        post_tamper_verify = corrupted.verify()
        corrupted.close()

    canonical_refs = tuple(sorted(proof_refs))
    durability_pass = all(
        (
            durable_first.state == "MISS" and not durable_first.reuse,
            durable_record.state == "RECORDED",
            pre_restart_verify["valid"] is True,
            pre_restart_verify["record_count"] == 1,
            restart_hit.state == "HIT" and restart_hit.reuse,
            restart_hit.cache_key == exact.cache_key,
            restart_hit.result_sha256 == result_sha,
            restart_hit.result_ref == result_ref,
            restart_hit.proof_refs == canonical_refs,
            idempotent.state == "IDEMPOTENT_RECORD",
            post_restart_verify["valid"] is True,
            post_restart_verify["record_count"] == 1,
            input_miss.state == "MISS",
            policy_miss.state == "MISS",
            environment_miss.state == "MISS",
            source_miss.state == "MISS",
            freshness_hold.state == "HOLD_FRESHNESS_EXPIRED",
            conflict_blocked,
            corruption_hold.state == "HOLD_CORRUPT_RECORD" and not corruption_hold.reuse,
            post_tamper_verify["valid"] is False,
            not shadow.provider_effect_authorized,
            not shadow.financial_effect_authorized,
            not shadow.publication_authorized,
        )
    )

    receipt = {
        "schema": SCHEMA,
        "state": (
            "HOSTED_SHADOW_RESULT_FABRIC_LOCAL_DURABILITY_PASS"
            if durability_pass
            else "HOSTED_SHADOW_RESULT_FABRIC_LOCAL_DURABILITY_FAIL"
        ),
        "certification_source_sha": certification_source_sha,
        "reference_source_main": REFERENCE_SOURCE_MAIN,
        "mission_id": mission.mission_id,
        "mission_ir_sha256": mission.digest(),
        "result_identity": exact.canonical_mapping(),
        "incumbent_receipt_sha256": incumbent["receipt_sha256"],
        "initial_durable_lookup_state": durable_first.state,
        "durable_record_state": durable_record.state,
        "restart_lookup_state": restart_hit.state,
        "restart_reuse": restart_hit.reuse,
        "idempotent_record_state": idempotent.state,
        "proof_refs_preserved": list(canonical_refs),
        "record_count_after_restart": post_restart_verify["record_count"],
        "invalidation_after_restart": {
            "input_change": input_miss.state,
            "policy_change": policy_miss.state,
            "environment_change": environment_miss.state,
            "source_change": source_miss.state,
            "freshness_expiry": freshness_hold.state,
        },
        "conflicting_same_key_result_blocked": conflict_blocked,
        "tamper_lookup_state": corruption_hold.state,
        "tamper_verify_valid": post_tamper_verify["valid"],
        "local_sqlite_close_reopen_proven": durability_pass,
        "persistent_cache_proven": durability_pass,
        "persistent_cache_scope": "LOCAL_SQLITE_CLOSE_REOPEN_HOSTED_SHADOW",
        "distributed_cache_proven": False,
        "cross_machine_cache_proven": False,
        "provider_cache_proven": False,
        "serving_route_changed": False,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
        "publication_authorized": False,
        "local_persistence_write_performed": True,
        "external_effects": 0,
        "stable_promotion_allowed": False,
        "semantic_pass": durability_pass,
        "truth_boundary": (
            "This court proves a local SQLite Result Fabric index survives close/reopen, preserves exact "
            "MissionIR result identity and proof references, remains idempotent, misses on source/input/policy/"
            "environment drift, holds on freshness expiry, rejects conflicting same-key records and detects "
            "direct row tamper. It does not prove distributed or cross-machine cache coherence, provider-result "
            "caching, serving cutover, production latency/cost improvement, or any provider/financial/publication effect."
        ),
    }
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def main() -> int:
    print(
        json.dumps(
            build_receipt(
                certification_source_sha=os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED")
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
