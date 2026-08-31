from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import compile_mission_result_identity
from benchmarking.cfbe_omega.mission_result_index_v1 import DurableMissionResultIndex
from federation.mission_ir import MissionIR

_SCHEMA = "FEDERATION-MISSION-RESULT-INDEX-CROSS-PROCESS-CANARY-V1"
_PROOF_REFS = ("proof:cross-process-hosted-synthetic", "source:mission-result-index-v1")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity(*, source: str, fresh_until: str):
    mission = MissionIR(
        mission_id="RESULT-INDEX-CROSS-PROCESS-1",
        objective="Prove one deterministic result survives process restart without recomputation.",
        domain="CFBE_RESULT_FABRIC",
        outcome_contract="Process B reuses the exact fresh result recorded by process A.",
        source_frontier=source,
        privacy_class="PUBLIC",
        rights_state="NOT_APPLICABLE",
        effect_class="READ_ONLY",
        authority_requirements=(),
        proof_requirements=("READBACK", "PROCESS_ISOLATION"),
    ).normalized()
    return compile_mission_result_identity(
        mission,
        step_id="cross-process-shadow-result",
        input_identity={"fixture": "public-safe-v1"},
        policy_identity={"policy": "result-fabric-v1"},
        environment_identity={"runtime": "python312", "process_isolation": True},
        proof_scope="MISSION_RESULT_INDEX_CROSS_PROCESS_HOSTED_SYNTHETIC",
        fresh_until=fresh_until,
    )


def _runtime_class() -> str:
    return "GITHUB_ACTIONS" if os.environ.get("GITHUB_ACTIONS") == "true" else "LOCAL_PROCESS"


def _read_compute_count(path: Path) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    count = payload.get("compute_count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("CROSS_PROCESS_CANARY_INVALID_COMPUTE_WITNESS")
    return count


def _write_compute_count(path: Path, count: int) -> None:
    path.write_text(_canonical({"compute_count": count}) + "\n", encoding="utf-8")


def _compute_once(witness_path: Path) -> tuple[str, int]:
    before = _read_compute_count(witness_path)
    after = before + 1
    _write_compute_count(witness_path, after)
    result_payload = {
        "schema": "PUBLIC-SYNTHETIC-DETERMINISTIC-RESULT-V1",
        "mission_id": "RESULT-INDEX-CROSS-PROCESS-1",
        "value": "deterministic-shadow-output-v1",
    }
    return _digest(result_payload), after


def _base_receipt(*, phase: str, source: str, cache_key: str, result_sha256: str, proof_refs: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema": _SCHEMA,
        "phase": phase,
        "evidence_class": "HOSTED_SYNTHETIC_PROCESS_ISOLATION",
        "runtime_class": _runtime_class(),
        "source_identity": source,
        "cache_key": cache_key,
        "result_sha256": result_sha256,
        "proof_refs": list(proof_refs),
        "payload_blob_persisted": False,
        "provider_effect_authorized": False,
        "authority_inherited": False,
        "external_effects": 0,
    }


def record_phase(*, state_dir: Path, source: str, fresh_until: str, now: str) -> dict[str, object]:
    state_dir.mkdir(parents=True, exist_ok=True)
    index_path = state_dir / "result-index.jsonl"
    compute_path = state_dir / "compute-witness.json"
    result_sha256, compute_count = _compute_once(compute_path)
    identity = _identity(source=source, fresh_until=fresh_until)
    index = DurableMissionResultIndex(index_path)
    decision = index.record(
        identity,
        result_ref="runtime-proof/cross-process-result.json",
        result_sha256=result_sha256,
        proof_refs=_PROOF_REFS,
        recorded_at=now,
        now=now,
    )
    receipt = _base_receipt(
        phase="PROCESS_A_RECORD",
        source=source,
        cache_key=identity.cache_key,
        result_sha256=result_sha256,
        proof_refs=tuple(decision.proof_refs),
    )
    receipt.update(
        {
            "lookup_state": decision.state,
            "reuse": decision.reuse,
            "process_compute_count": 1,
            "total_compute_count": compute_count,
            "index_record_count": index.verify()["record_count"],
        }
    )
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def lookup_phase(*, state_dir: Path, source: str, fresh_until: str, now: str) -> dict[str, object]:
    index_path = state_dir / "result-index.jsonl"
    compute_path = state_dir / "compute-witness.json"
    before = _read_compute_count(compute_path)
    identity = _identity(source=source, fresh_until=fresh_until)
    index = DurableMissionResultIndex(index_path)
    decision = index.lookup(identity, now=now)
    after = _read_compute_count(compute_path)
    if decision.state != "HIT" or not decision.reuse:
        raise ValueError(f"CROSS_PROCESS_CANARY_REUSE_FAILED:{decision.state}")
    if after != before:
        raise ValueError("CROSS_PROCESS_CANARY_UNEXPECTED_RECOMPUTATION")
    receipt = _base_receipt(
        phase="PROCESS_B_LOOKUP",
        source=source,
        cache_key=identity.cache_key,
        result_sha256=decision.result_sha256,
        proof_refs=tuple(decision.proof_refs),
    )
    receipt.update(
        {
            "lookup_state": decision.state,
            "reuse": decision.reuse,
            "process_compute_count": 0,
            "total_compute_count": after,
            "no_recomputation": True,
            "index_record_count": index.verify()["record_count"],
        }
    )
    receipt["receipt_sha256"] = _digest(receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hosted synthetic cross-process Result Index canary")
    parser.add_argument("phase", choices=("record", "lookup"))
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--fresh-until", required=True)
    parser.add_argument("--now", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    kwargs = {
        "state_dir": Path(args.state_dir),
        "source": args.source,
        "fresh_until": args.fresh_until,
        "now": args.now,
    }
    receipt = record_phase(**kwargs) if args.phase == "record" else lookup_phase(**kwargs)
    print(_canonical(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
