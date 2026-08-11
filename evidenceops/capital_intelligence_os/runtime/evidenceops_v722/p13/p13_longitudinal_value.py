#!/usr/bin/env python3
"""Append one bounded P13 longitudinal value-ledger cycle.

The cycle measures provider execution, classification stability, unsafe reliance
blocked, owner-attention demand and zero-effect compliance. It does not refresh
or certify underlying law and performs no consequential action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "OMEGAMAX_SOL_EVIDENCEOPS_V722_P13_LONGITUDINAL_VALUE_CYCLE_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify(source: dict[str, Any]) -> str:
    if source["lex_currentness_state"] != "CURRENT":
        return "LEGAL_PROPOSITION_BLOCKED"
    if not source["primary_source"]:
        return "LEGAL_PROPOSITION_BLOCKED"
    return "LEGAL_PROPOSITION_VALIDATED"


def load_last(ledger: Path) -> dict[str, Any] | None:
    if not ledger.exists():
        return None
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else None


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def run(catalogue_path: Path, ledger_path: Path, summary_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    sources = catalogue["sources"]
    assessments = {source["source_id"]: classify(source) for source in sources}
    expected = {source["source_id"]: source["expected_assessment"] for source in sources}
    previous = load_last(ledger_path)

    checks = {
        "catalogue_schema_valid": catalogue.get("schema") == "OMEGAMAX_SOL_EVIDENCEOPS_V722_P13_REAL_CORPUS_CATALOGUE_V1",
        "source_count_seven": len(sources) == 7,
        "source_ids_unique": len({item["source_id"] for item in sources}) == len(sources),
        "snapshot_registry_pointer_match": catalogue["source_snapshot"]["observation_record_sha256"] == catalogue["source_registry"]["snapshot_observation_record_sha256"],
        "classification_matches_verified_baseline": assessments == expected,
        "current_primary_validated": sum(value == "LEGAL_PROPOSITION_VALIDATED" for value in assessments.values()) == 2,
        "unsafe_or_noncurrent_reliance_blocked": sum(value == "LEGAL_PROPOSITION_BLOCKED" for value in assessments.values()) == 5,
        "authority_ceiling_a1": catalogue["authority_boundary"]["authority_ceiling"] == "A1",
        "consequential_authority_absent": not any(catalogue["authority_boundary"][key] for key in ("external_send", "legal_filing", "live_hearing_recording", "live_financial_action", "destructive_action", "provider_admin")),
        "external_effects_zero": catalogue["authority_boundary"]["external_effects"] == 0,
    }
    classification_sha = digest(assessments)
    cycle = {
        "schema": SCHEMA,
        "cycle_id": f"P13-CYCLE-{os.getenv('GITHUB_RUN_ID', 'local')}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}",
        "observed_at_utc": now_utc(),
        "provider_event": {
            "event_name": os.getenv("GITHUB_EVENT_NAME", "local"),
            "run_id": os.getenv("GITHUB_RUN_ID", "local"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "1"),
            "workflow": os.getenv("GITHUB_WORKFLOW", "local"),
            "sha": os.getenv("GITHUB_SHA", "local"),
            "ref": os.getenv("GITHUB_REF", "local"),
            "repository": os.getenv("GITHUB_REPOSITORY", "local"),
        },
        "corpus": {
            "snapshot_sha256": catalogue["source_snapshot"]["sha256"],
            "registry_sha256": catalogue["source_registry"]["sha256"],
            "sources_classified": len(sources),
            "classification_sha256": classification_sha,
            "validated_current_primary": 2,
            "blocked_unsafe_or_noncurrent": 5,
        },
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "classification_stable_from_previous_cycle": previous is None or previous["corpus"]["classification_sha256"] == classification_sha,
        "baseline_reference": catalogue["baseline_receipt"],
        "value": {
            "control_defects_prevented_this_cycle": 5,
            "owner_attention_required": False,
            "owner_minutes_saved": "UNMEASURED",
            "outcome_quality": "CONTROL_STABILITY_ONLY",
            "longitudinal_real_case_outcome": "UNPROVEN",
        },
        "authority": catalogue["authority_boundary"],
        "execution_seconds": round(time.perf_counter() - started, 6),
        "state": "LONGITUDINAL_CONTROL_CYCLE_VERIFIED" if all(checks.values()) else "LONGITUDINAL_CONTROL_CYCLE_FAILED",
        "truth_boundary": "This cycle proves recurring classification/control stability for the fixed verified corpus fixture. It is not current-law refresh, legal advice, a case outcome, or consequential execution.",
    }
    cycle["cycle_sha256"] = digest(cycle)

    existing = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
    atomic_write(ledger_path, existing + json.dumps(cycle, sort_keys=True) + "\n")
    atomic_write(summary_path, json.dumps(cycle, indent=2, sort_keys=True) + "\n")
    return cycle


def verify(ledger: Path, summary: Path) -> dict[str, Any]:
    cycle = json.loads(summary.read_text(encoding="utf-8"))
    supplied = cycle.pop("cycle_sha256")
    if digest(cycle) != supplied:
        raise RuntimeError("cycle hash mismatch")
    cycle["cycle_sha256"] = supplied
    last = load_last(ledger)
    if last != cycle:
        raise RuntimeError("ledger/summary semantic readback mismatch")
    if cycle["state"] != "LONGITUDINAL_CONTROL_CYCLE_VERIFIED":
        raise RuntimeError("cycle gates failed")
    return cycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "verify"))
    parser.add_argument("--catalogue", default=str(Path(__file__).with_name("real_corpus_catalogue.json")))
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    if args.mode == "run":
        result = run(Path(args.catalogue), Path(args.ledger), Path(args.summary))
    else:
        result = verify(Path(args.ledger), Path(args.summary))
    print(json.dumps({"state": result["state"], "cycle_id": result["cycle_id"], "cycle_sha256": result["cycle_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
