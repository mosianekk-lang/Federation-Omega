#!/usr/bin/env python3
"""Rebuild the private RESOLVE/PST Local Bible through provider-native proof.

The source archive and completion receipts are downloaded from private Google
Drive using a short-lived access token. Raw P2 content never enters the source
repository or workflow logs. The original capture_event.py inside the archive
is used to append Event 13 and verify the existing hash chain.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_ARCHIVE_ID = "1TWqGtvudZPHGfVFIZEp10C4v0G3CTn5D"
BASE_ARCHIVE_SIZE = 69919
BASE_ARCHIVE_SHA256 = "05316bd22b341071fd700bb7f93b867712a302c2550e93b696ebdf6a51a750c9"
REMOTE_VERIFICATION_ID = "14byh3sy0DPLQkEC1yr-nuqKPMG_h8hAl"
COMPLETION_ID = "13wd7ko9nKQT7YTox90kGro9ncFc-Gr4Y"
EXPECTED_PREVIOUS_HASH = "e58ba00136022251976051a041b3664fd51418aaabf2c840c8bf2c5d7903cf21"
EXPECTED_EVENT_COUNT = 12
NODE_ID = "NODE-EVIDENCEOPS-RESOLVE-PST-20260804"
BIBLE_ID = "EO-LIVE-BIBLE-RESOLVE-PST-20260804"
EVENT_ID = "EVT-20260804-PST-REMOTE-CLOSURE-FEDERATION-LEARNING-AND-PACKAGE-REBUILD"
TRANSACTION_ID = "TXN-KDV-20260804-PST-CLOSURE-013"
ROOT_NAME = "local_bible_live_capture"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def download_drive_file(file_id: str, destination: Path, token: str) -> None:
    if not token:
        raise RuntimeError("GOOGLE_ACCESS_TOKEN is empty")
    request = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
        headers={"Authorization": f"Bearer {token}"},
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL row {number} in {path}")
        result.append(value)
    return result


def typed_set(payload: dict[str, Any], key: str, value: Any) -> None:
    if key not in payload:
        payload[key] = value
        return
    old = payload[key]
    if isinstance(old, list) and not isinstance(value, list):
        payload[key] = [value]
    elif isinstance(old, str) and isinstance(value, list):
        payload[key] = "; ".join(str(item) for item in value)
    else:
        payload[key] = value


def build_event_payload(template: dict[str, Any], run_id: str, source_sha: str, captured_at: str) -> dict[str, Any]:
    payload = copy.deepcopy(template)
    directive = (
        "Refresh memory on the entire chat, restore the n directive, continue all outstanding work, "
        "use the full verified power of Federation Omega, and continuously update learning ledgers "
        "and algorithm triggers with every failure, success and constraint."
    )
    action = (
        "Closed the MosianeKK PST remote verification through Phoenix provider run 30942063206; "
        "persisted and read back REMOTE_VERIFICATION.json and COMPLETION.json in Drive; updated the "
        "canonical pointer, Mission Control, Central Master and Registry through final cycle "
        "CYC-CBR-20260804-016 and receipt MRG-RESOLVE-PST-CLOSURE-20260804-0001; preserved NO_SEND "
        "and P2 minimum-necessary projection; converted local ClientError and path-binding failures "
        "into LBRF-V1 incident, remedy, formation, prediction, algorithm, auto-rule, cycle-trigger "
        "and proof controls; and rebuilt this package through the original node capture engine on "
        f"governed Phoenix run {run_id}."
    )
    proof = [
        "PST provider run 30942063206 completed all shard SHA-256, ZIP CRC, SQLite integrity, exact count and FTS gates.",
        "Drive REMOTE_VERIFICATION.json file 14byh3sy0DPLQkEC1yr-nuqKPMG_h8hAl reads REMOTE_COMPLETE_VERIFIED.",
        "Drive COMPLETION.json file 13wd7ko9nKQT7YTox90kGro9ncFc-Gr4Y reads COMPLETE_VERIFIED.",
        "Central Master closure used CYC-CBR-20260804-016 and MRG-RESOLVE-PST-CLOSURE-20260804-0001.",
        "The predecessor Local Bible package remained immutable and verified at SHA-256 " + BASE_ARCHIVE_SHA256 + ".",
        f"This rebuild used source commit {source_sha} and Phoenix run {run_id} with private Drive access only.",
    ]
    classification = {
        "allegation": [],
        "fact": [
            "The PST corpus is COMPLETE_VERIFIED with Drive receipt readback.",
            "The Central Master remote-closure hold was released through a verified merge transaction.",
            "The predecessor Local Bible package remained available as rollback evidence during recovery.",
            "Learning ledger and algorithm-trigger records were created for the failures and successful provider recovery.",
            "Communication state remained NO_SEND and raw P2 mailbox content was not promoted to public source control.",
        ],
        "inference": [
            "LBRF-V1 materially reduces the chance that a local binary-runtime failure becomes a dead end or false completion claim."
        ],
        "unknown": [
            "Future provider executions remain dependent on current connector and WIF authority at runtime."
        ],
    }
    values: dict[str, Any] = {
        "transaction_id": TRANSACTION_ID,
        "event_id": EVENT_ID,
        "captured_at": captured_at,
        "capture_type": "CONTEMPORANEOUS_TURN",
        "source_confidence": "GITHUB_DRIVE_LIBRARY_MASTER_REGISTRY_AND_LEARNING_LEDGER_READBACK",
        "directive": directive,
        "user_directive": directive,
        "mission_objective": (
            "Finish the verified PST closure, preserve the exact Local Bible history, append Event 13 "
            "through the original hash algorithm, rebuild the package, and institutionalise every "
            "failure, success and constraint as reusable Federation Omega learning and trigger logic."
        ),
        "action_performed": action,
        "sources_inspected": [
            "Phoenix PST completion artifact and provider run 30942063206",
            "Drive REMOTE_VERIFICATION.json and COMPLETION.json",
            "PST_CORPUS_V2_POINTER.json and Mission Control",
            "Central Master Bible and Corpus Registry closure receipts",
            "Local Bible predecessor package and original capture_event.py",
            "Sovereign Federation CloudOps learning and trigger ledgers",
        ],
        "artefacts_changed": [
            "Local Bible events.jsonl and merge_queue.jsonl",
            "LOCAL_BIBLE.md, state.json, RETROSPECTIVE_INDEX.json and CURRENT_POINTER.json",
            "verification_report.json and SHA256SUMS.txt",
            "proof/REMOTE_VERIFICATION.json and proof/COMPLETION.json",
            "proof/LBRF_LEARNING_RECEIPT.json",
        ],
        "artifacts_changed": [
            "Local Bible package and provider-side verification sidecars"
        ],
        "verified_proof": proof,
        "classification": classification,
        "corrections": [
            "The reserved Central cycle 013 was superseded after identifier collisions; the final verified closure cycle is 016.",
            "GitHub success, local finalisation and artifact existence were not treated as completion without Drive receipt readback.",
            "Local runtime ClientError was not reported as data loss; the prior package remained verified and recoverable.",
        ],
        "unresolved_gaps": [
            "Replace and independently read back the persistent Library ZIP and readable control files generated by this run.",
            "Correct the stale completion next-action text in Mission Control and disable the completed PST controller.",
            "Remove the temporary private Drive mirror and temporary service-account permission after Library readback succeeds.",
        ],
        "next_automatic_action": (
            "Persist this rebuilt package and sidecars into /EvidenceOps/Local Bible Nodes, independently "
            "materialize and verify the ZIP SHA-256 and CRC, correct Mission Control, disable the completed "
            "PST controller, remove temporary recovery access, and record final proof in the learning ledgers."
        ),
        "outbound_communication": "NO_SEND",
        "communication_state": "NO_SEND",
    }
    for key, value in values.items():
        typed_set(payload, key, value)
    for key in ("historical_period", "historical_period_represented", "reconstruction_note"):
        if key in payload:
            payload[key] = None
    return payload


def update_controls(root: Path, last_event: dict[str, Any], event_count: int, queue_count: int, run_id: str, source_sha: str) -> None:
    event_hash = str(last_event.get("event_hash", ""))
    previous_hash = str(last_event.get("previous_hash", ""))
    if previous_hash != EXPECTED_PREVIOUS_HASH:
        raise RuntimeError(f"unexpected Event 13 previous hash: {previous_hash}")
    if not event_hash or len(event_hash) != 64:
        raise RuntimeError("Event 13 hash is missing or malformed")

    index_path = root / "RETROSPECTIVE_INDEX.json"
    index = read_json(index_path)
    if int(index.get("total_events", -1)) != EXPECTED_EVENT_COUNT:
        raise RuntimeError("retrospective index predecessor count drift")
    events = index.get("events")
    if not isinstance(events, list) or not events:
        raise RuntimeError("retrospective index events missing")
    if events[-1].get("event_hash") != EXPECTED_PREVIOUS_HASH:
        raise RuntimeError("retrospective index predecessor hash drift")
    events.append({
        "capture_type": "CONTEMPORANEOUS_TURN",
        "captured_at": last_event.get("captured_at"),
        "directive": last_event.get("directive") or last_event.get("user_directive"),
        "event_hash": event_hash,
        "event_id": EVENT_ID,
        "historical_period": None,
        "previous_hash": previous_hash,
        "sequence": event_count,
        "source_confidence": last_event.get("source_confidence"),
        "status": "HASH_CHAIN_VERIFIED",
        "transaction_id": TRANSACTION_ID,
    })
    index.update({
        "contemporaneous_events": int(index.get("contemporaneous_events", 0)) + 1,
        "coverage": "MosianeKK PST corpus complete verification, RESOLVE release, Local Bible activation, Central reconciliation and provider recovery learning",
        "generated_at_sast": "2026-08-04T21:56:00+02:00",
        "status": "PST_COMPLETE_VERIFIED_EVENT_13_HASH_CHAIN_VERIFIED",
        "total_events": event_count,
    })
    write_json(index_path, index)

    pointer_path = root / "CURRENT_POINTER.json"
    pointer = read_json(pointer_path)
    pointer.update({
        "schema": "EVIDENCEOPS-LOCAL-BIBLE-CURRENT-POINTER-5",
        "status": "PST_AND_LOCAL_BIBLE_PACKAGE_REBUILT_PROVIDER_VERIFIED_PENDING_LIBRARY_WRITEBACK",
        "event_count": event_count,
        "merge_queue_count": queue_count,
        "last_event_id": EVENT_ID,
        "last_event_hash": event_hash,
        "last_master_cycle": "CYC-CBR-20260804-016",
        "last_merge_receipt": "MRG-RESOLVE-PST-CLOSURE-20260804-0001",
        "central_reconciliation_status": "COMPLETE_VERIFIED_REMOTE_CLOSURE_RELEASED",
        "package_rebuild_run_id": int(run_id),
        "package_rebuild_source_sha": source_sha,
    })
    write_json(pointer_path, pointer)

    state_path = root / "state.json"
    state = read_json(state_path)
    state.update({
        "status": "PST_AND_LOCAL_BIBLE_PACKAGE_REBUILT_PROVIDER_VERIFIED_PENDING_LIBRARY_WRITEBACK",
        "event_count": event_count,
        "merge_queue_count": queue_count,
        "last_event_id": EVENT_ID,
        "last_event_hash": event_hash,
        "pst_remote_closure": "COMPLETE_VERIFIED",
        "central_master_cycle": "CYC-CBR-20260804-016",
        "central_merge_receipt": "MRG-RESOLVE-PST-CLOSURE-20260804-0001",
        "learning_control": "LBRF-V1_ACTIVE_CANARY",
        "communication_state": "NO_SEND",
    })
    write_json(state_path, state)


def internal_file_inventory(root: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.name in {"SHA256SUMS.txt", "verification_report.json"}:
            continue
        inventory.append({
            "name": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })
    return inventory


def write_sha_sums(root: Path) -> None:
    rows: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.name == "SHA256SUMS.txt":
            continue
        rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_archive(root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                archive.write(path, f"{ROOT_NAME}/{path.relative_to(root).as_posix()}")
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC failed for {bad}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "0")
    source_sha = os.environ.get("GITHUB_SHA", "UNKNOWN")
    captured_at = datetime.now(timezone.utc).isoformat()

    work = args.work.resolve()
    output = args.output.resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)

    base_zip = work / "predecessor.zip"
    remote_receipt = work / "REMOTE_VERIFICATION.json"
    completion_receipt = work / "COMPLETION.json"
    download_drive_file(BASE_ARCHIVE_ID, base_zip, token)
    download_drive_file(REMOTE_VERIFICATION_ID, remote_receipt, token)
    download_drive_file(COMPLETION_ID, completion_receipt, token)

    if base_zip.stat().st_size != BASE_ARCHIVE_SIZE:
        raise RuntimeError("predecessor package size mismatch")
    if sha256_file(base_zip) != BASE_ARCHIVE_SHA256:
        raise RuntimeError("predecessor package hash mismatch")
    remote = read_json(remote_receipt)
    completion = read_json(completion_receipt)
    if remote.get("status") != "REMOTE_COMPLETE_VERIFIED":
        raise RuntimeError("remote verification receipt is not complete")
    if completion.get("status") != "COMPLETE_VERIFIED":
        raise RuntimeError("completion receipt is not complete")
    if int(remote.get("workflow_run_id", 0)) != 30942063206 or int(completion.get("workflow_run_id", 0)) != 30942063206:
        raise RuntimeError("PST provider run identity drift")

    extract = work / "extract"
    with zipfile.ZipFile(base_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"predecessor ZIP CRC failed for {bad}")
        archive.extractall(extract)
    root = extract / ROOT_NAME
    if not root.is_dir():
        candidates = [path for path in extract.iterdir() if path.is_dir()]
        if len(candidates) != 1:
            raise RuntimeError("unable to locate Local Bible archive root")
        root = candidates[0]

    events_before = load_jsonl(root / "events.jsonl")
    queue_before = load_jsonl(root / "merge_queue.jsonl")
    if len(events_before) != EXPECTED_EVENT_COUNT or len(queue_before) != EXPECTED_EVENT_COUNT:
        raise RuntimeError("predecessor event or queue count drift")
    if events_before[-1].get("event_hash") != EXPECTED_PREVIOUS_HASH:
        raise RuntimeError("predecessor event hash drift")

    template_path = root / "central_activation_payload.json"
    if not template_path.is_file():
        template_path = root / "activation_payload.json"
    payload = build_event_payload(read_json(template_path), run_id, source_sha, captured_at)
    payload_path = root / "event13_payload.json"
    write_json(payload_path, payload)

    capture = root / "capture_event.py"
    subprocess.run([sys.executable, str(capture), "append", str(payload_path)], cwd=root, check=True)
    subprocess.run([sys.executable, str(capture), "verify"], cwd=root, check=True)

    events = load_jsonl(root / "events.jsonl")
    queue = load_jsonl(root / "merge_queue.jsonl")
    if len(events) != EXPECTED_EVENT_COUNT + 1 or len(queue) != EXPECTED_EVENT_COUNT + 1:
        raise RuntimeError("Event 13 append count mismatch")
    last_event = events[-1]
    if last_event.get("event_id") != EVENT_ID:
        raise RuntimeError("Event 13 identity mismatch")

    proof_dir = root / "proof"
    proof_dir.mkdir(exist_ok=True)
    shutil.copy2(remote_receipt, proof_dir / "REMOTE_VERIFICATION.json")
    shutil.copy2(completion_receipt, proof_dir / "COMPLETION.json")
    learning = {
        "schema": "FEDOMEGA-LBRF-LEARNING-RECEIPT-1",
        "trace_id": "FO-TRACE-LOCAL-BIBLE-RUNTIME-RECOVERY-20260804-001",
        "incident_id": "INC-FO-LBRF-20260804-001",
        "remedy_id": "REM-FO-LBRF-20260804-001",
        "formation_id": "FORM-FO-LBRF-20260804-001",
        "algorithm_id": "ALG-LBRF-001",
        "learning_signal_id": "LS-LBRF-001",
        "auto_rule_id": "AR-LBRF-001",
        "cycle_trigger_id": "CT-LBRF-001",
        "proof_id": "RP-LBRF-001",
        "failures": [
            "local container ClientError",
            "local Python ClientError",
            "container_file_not_found during Library Markdown replacement",
        ],
        "constraints": [
            "P2 content cannot be committed to public source control",
            "final persistence requires Library overwrite and binary readback",
        ],
        "successful_routes": [
            "predecessor Library package materialization",
            "private Drive mirror and exact byte readback",
            "service-account-scoped read permission",
            "Phoenix WIF private rebuild",
        ],
        "trigger": "LOCAL_BINARY_FAILURE_X2",
        "selected_route": "PRIVATE_DRIVE_MIRROR_TO_GOVERNED_PHOENIX_TO_LIBRARY",
        "run_id": int(run_id),
        "source_sha": source_sha,
        "communication_state": "NO_SEND",
        "status": "PROVIDER_REBUILD_VERIFIED_PENDING_LIBRARY_WRITEBACK",
    }
    write_json(proof_dir / "LBRF_LEARNING_RECEIPT.json", learning)

    update_controls(root, last_event, len(events), len(queue), run_id, source_sha)

    report_path = root / "verification_report.json"
    report = read_json(report_path)
    report["schema"] = "EVIDENCEOPS-LOCAL-BIBLE-PST-CLOSURE-PACKAGE-VERIFICATION-2"
    report["status"] = "PST_AND_LOCAL_BIBLE_PACKAGE_REBUILT_PROVIDER_VERIFIED_PENDING_LIBRARY_WRITEBACK"
    report["verified_at_sast"] = "2026-08-04T21:56:00+02:00"
    report["event_verification"] = {
        "event_count": len(events),
        "merge_queue_count": len(queue),
        "last_event_id": EVENT_ID,
        "last_event_hash": last_event["event_hash"],
        "previous_hash": last_event["previous_hash"],
        "ok": True,
    }
    report["pst_remote_closure"] = {
        "status": "COMPLETE_VERIFIED",
        "provider_run_id": 30942063206,
        "remote_verification_drive_file_id": REMOTE_VERIFICATION_ID,
        "completion_drive_file_id": COMPLETION_ID,
        "central_cycle_id": "CYC-CBR-20260804-016",
        "merge_receipt_id": "MRG-RESOLVE-PST-CLOSURE-20260804-0001",
    }
    report["predecessor_package"] = {
        "sha256": BASE_ARCHIVE_SHA256,
        "size_bytes": BASE_ARCHIVE_SIZE,
        "library_version_id": "3",
        "zip_crc": "OK",
    }
    report["package_rebuild"] = {
        "run_id": int(run_id),
        "source_sha": source_sha,
        "status": "RUNNER_INTERNAL_VERIFIED_PENDING_EXTERNAL_LIBRARY_OVERWRITE",
        "privacy": "P2_PRIVATE_DRIVE_READ_ONLY_NO_PUBLIC_SOURCE_CONTENT",
    }
    report["files"] = internal_file_inventory(root)
    report["truth_boundary"] = (
        "The provider runner verified the predecessor bytes, used the original capture engine, "
        "extended the chain and rebuilt a CRC-valid ZIP. Persistent completion additionally requires "
        "Library overwrite and independent binary readback of the generated package."
    )
    write_json(report_path, report)
    write_sha_sums(root)

    package = output / "Local_Bible_NODE_EVIDENCEOPS_RESOLVE_PST_20260804_EVENT13.zip"
    build_archive(root, package)
    external = {
        "schema": "EVIDENCEOPS-LOCAL-BIBLE-EXTERNAL-PACKAGE-VERIFICATION-1",
        "status": "PROVIDER_PACKAGE_REBUILD_VERIFIED_PENDING_LIBRARY_WRITEBACK",
        "node_id": NODE_ID,
        "bible_id": BIBLE_ID,
        "event_count": len(events),
        "merge_queue_count": len(queue),
        "last_event_id": EVENT_ID,
        "last_event_hash": last_event["event_hash"],
        "previous_hash": last_event["previous_hash"],
        "package_name": package.name,
        "package_size_bytes": package.stat().st_size,
        "package_sha256": sha256_file(package),
        "zip_crc": "OK",
        "provider_run_id": int(run_id),
        "source_sha": source_sha,
        "predecessor_sha256": BASE_ARCHIVE_SHA256,
        "communication_state": "NO_SEND",
        "next_action": "Overwrite persistent Library package and controls, independently read back SHA-256 and CRC, then close remaining controller and temporary-access cleanup.",
    }
    write_json(output / "PACKAGE_VERIFICATION.json", external)
    shutil.copy2(root / "LOCAL_BIBLE.md", output / "LOCAL_BIBLE.md")
    shutil.copy2(root / "CURRENT_POINTER.json", output / "CURRENT_POINTER.json")
    shutil.copy2(root / "RETROSPECTIVE_INDEX.json", output / "RETROSPECTIVE_INDEX.json")
    shutil.copy2(root / "verification_report.json", output / "verification_report.json")
    shutil.copy2(proof_dir / "LBRF_LEARNING_RECEIPT.json", output / "LBRF_LEARNING_RECEIPT.json")
    write_json(output / "EVENT13.json", last_event)
    return external


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, default=Path("/tmp/local-bible-event13-rebuild"))
    parser.add_argument("--output", type=Path, default=Path("phoenix-export-output/local-bible-rebuild"))
    args = parser.parse_args()
    result = execute(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
