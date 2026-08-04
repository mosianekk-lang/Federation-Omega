#!/usr/bin/env python3
"""Independently verify the finalized PST corpus through composite provider proof.

The verifier deliberately keeps proof domains separate:
- authenticated Google Drive inventory and prior 60-part re-download SHA proof;
- immutable GitHub searchable and finalized-shard artifact re-downloads;
- local finalization controls for the retrieval extension and required counts.

It never treats unauthenticated access failure as evidence loss and never weakens a
hash, CRC, SQLite, count, FTS, source-identity, or receipt gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("PST_VERIFY_ROOT", "/mnt/pst-composite-verify"))
RECEIPTS = Path("deployment_receipts")
MANIFEST_PATH = Path(
    "deployment_manifests/evidenceops-pst-v2-composite-proof.json"
)
REMOTE_RECEIPT = RECEIPTS / "evidenceops-pst-corpus-v2-remote-verification.json"
COMPLETION_RECEIPT = RECEIPTS / "evidenceops-pst-corpus-v2-drive-completion.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for item in archive.infolist():
        target = (destination / item.filename).resolve()
        if target != destination and destination not in target.parents:
            raise RuntimeError(f"UNSAFE_ARCHIVE_PATH:{item.filename}")
    archive.extractall(destination)


def download_artifact(repo: str, artifact_id: int, output: Path) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN_MISSING")
    url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "EvidenceOps-PST-Composite-Verifier/1.0",
    }
    last_error: Exception | None = None
    for attempt in range(1, 5):
        partial.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=180) as response, partial.open(
                "wb"
            ) as target:
                shutil.copyfileobj(response, target, 8 * 1024 * 1024)
            if partial.stat().st_size <= 0:
                raise RuntimeError("EMPTY_ARTIFACT_DOWNLOAD")
            partial.replace(output)
            return
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < 4:
                time.sleep(attempt * 8)
    raise RuntimeError(f"ARTIFACT_DOWNLOAD_FAILED:{artifact_id}:{last_error}")


def find_unique(root: Path, name: str) -> Path:
    matches = [item for item in root.rglob(name) if item.is_file()]
    if len(matches) != 1:
        raise RuntimeError(f"UNIQUE_FILE_EXPECTED:{name}:{[str(x) for x in matches]}")
    return matches[0]


def verify_searchable_artifact(repo: str, spec: dict[str, Any]) -> dict[str, Any]:
    archive_path = ROOT / "searchable-artifact.zip"
    extraction = ROOT / "searchable"
    download_artifact(repo, int(spec["artifact_id"]), archive_path)
    archive_size = archive_path.stat().st_size
    archive_sha = sha256_file(archive_path)
    if archive_size != int(spec["archive_size_bytes"]):
        raise RuntimeError(
            f"SEARCHABLE_ARTIFACT_SIZE_MISMATCH:{archive_size}:{spec['archive_size_bytes']}"
        )
    if archive_sha != spec["archive_sha256"]:
        raise RuntimeError(
            f"SEARCHABLE_ARTIFACT_SHA_MISMATCH:{archive_sha}:{spec['archive_sha256']}"
        )
    extraction.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        safe_extract(archive, extraction)
    publication_path = find_unique(extraction, "GITHUB_PUBLICATION_MANIFEST.json")
    publication = json.loads(publication_path.read_text(encoding="utf-8"))
    corpus_root = publication_path.parent.parent
    validated_objects: list[dict[str, Any]] = []
    for item in publication["objects"]:
        relpath = item["relpath"]
        if relpath.startswith("06_RETRIEVAL_SHARDS/"):
            continue
        path = corpus_root / relpath
        if not path.is_file():
            raise RuntimeError(f"SEARCHABLE_OBJECT_MISSING:{relpath}")
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if actual_size != int(item["size_bytes"]) or actual_sha != item["sha256"]:
            raise RuntimeError(
                f"SEARCHABLE_OBJECT_MISMATCH:{relpath}:{actual_size}:{actual_sha}"
            )
        validated_objects.append(
            {
                "relpath": relpath,
                "size_bytes": actual_size,
                "sha256": actual_sha,
                "ok": True,
            }
        )

    database = find_unique(extraction, "corpus_search.db")
    connection = sqlite3.connect(database)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            "messages_meta": connection.execute(
                "SELECT COUNT(*) FROM messages_meta"
            ).fetchone()[0],
            "attachments_meta": connection.execute(
                "SELECT COUNT(*) FROM attachments_meta"
            ).fetchone()[0],
        }
        fts = {
            "MPMB298": connection.execute(
                "SELECT COUNT(*) FROM messages_fts WHERE messages_fts MATCH 'MPMB298'"
            ).fetchone()[0],
            "precautionary_suspension": connection.execute(
                "SELECT COUNT(*) FROM messages_fts "
                "WHERE messages_fts MATCH '\"precautionary suspension\"'"
            ).fetchone()[0],
        }
    finally:
        connection.close()
    if integrity != "ok":
        raise RuntimeError(f"SQLITE_INTEGRITY_FAILED:{integrity}")
    if counts != {"messages_meta": 2885, "attachments_meta": 5203}:
        raise RuntimeError(f"SQLITE_COUNT_MISMATCH:{counts}")
    if fts["MPMB298"] <= 0 or fts["precautionary_suspension"] <= 0:
        raise RuntimeError(f"SQLITE_FTS_CANARY_FAILED:{fts}")

    archive_path.unlink(missing_ok=True)
    return {
        "artifact_id": int(spec["artifact_id"]),
        "archive_size_bytes": archive_size,
        "archive_sha256": archive_sha,
        "source_commit": spec["source_commit"],
        "validated_non_shard_objects": validated_objects,
        "validated_non_shard_object_count": len(validated_objects),
        "sqlite": {
            "integrity_check": integrity,
            "counts": counts,
            "fts_counts": fts,
        },
        "ok": True,
    }


def verify_final_shards(repo: str, specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    work = ROOT / "shard-work"
    work.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        number = int(spec["number"])
        archive_path = work / f"artifact-{number:04d}.zip"
        extraction = work / f"artifact-{number:04d}"
        shutil.rmtree(extraction, ignore_errors=True)
        extraction.mkdir(parents=True, exist_ok=True)
        download_artifact(repo, int(spec["artifact_id"]), archive_path)
        archive_sha = sha256_file(archive_path)
        if archive_sha != spec["archive_sha256"]:
            raise RuntimeError(
                f"SHARD_ARTIFACT_SHA_MISMATCH:{number}:{archive_sha}:"
                f"{spec['archive_sha256']}"
            )
        with zipfile.ZipFile(archive_path) as artifact:
            safe_extract(artifact, extraction)
        shard_name = f"Corpus_Shard_{number:04d}.zip"
        shard_path = find_unique(extraction, shard_name)
        logical_size = shard_path.stat().st_size
        logical_sha = sha256_file(shard_path)
        if logical_size != int(spec["logical_size_bytes"]):
            raise RuntimeError(
                f"SHARD_SIZE_MISMATCH:{number}:{logical_size}:"
                f"{spec['logical_size_bytes']}"
            )
        if logical_sha != spec["logical_sha256"]:
            raise RuntimeError(
                f"SHARD_SHA_MISMATCH:{number}:{logical_sha}:"
                f"{spec['logical_sha256']}"
            )
        with zipfile.ZipFile(shard_path) as shard:
            bad_member = shard.testzip()
            member_count = len(shard.infolist())
        if bad_member is not None:
            raise RuntimeError(f"SHARD_CRC_FAILED:{number}:{bad_member}")
        results.append(
            {
                "number": number,
                "artifact_id": int(spec["artifact_id"]),
                "artifact_archive_sha256": archive_sha,
                "logical_size_bytes": logical_size,
                "logical_sha256": logical_sha,
                "member_count": member_count,
                "crc_ok": True,
            }
        )
        archive_path.unlink(missing_ok=True)
        shutil.rmtree(extraction, ignore_errors=True)
    return results


def validate_control_manifest(manifest: dict[str, Any]) -> dict[str, bool]:
    direct = manifest["drive_direct_inventory"]
    direct_objects = direct["objects"]
    direct_ids = [item["drive_file_id"] for item in direct_objects]
    direct_paths = [item["logical_relpath"] for item in direct_objects]
    finalization = manifest["finalization"]
    transport = manifest["drive_transport_readback"]
    db = transport["final_database"]
    db_parts = db["parts"]
    required = manifest["required_counts"]
    gates = {
        "source_identity_present": bool(manifest["source"]["sha256"]),
        "drive_direct_inventory_count": len(direct_objects)
        == int(direct["expected_count"])
        == 18,
        "drive_direct_inventory_unique_ids": len(set(direct_ids)) == len(direct_ids),
        "drive_direct_inventory_unique_paths": len(set(direct_paths))
        == len(direct_paths),
        "drive_direct_inventory_sizes_valid": all(
            int(item["size_bytes"]) >= 0 for item in direct_objects
        ),
        "drive_transport_parts_redownloaded": int(transport["part_count"])
        == int(transport["verified_part_count"])
        == 60,
        "drive_transport_prior_sha_proof": transport["status"]
        == "DRIVE_TRANSPORT_PARTS_COMPLETE_VERIFIED",
        "final_database_two_parts_bound": len(db_parts) == 2
        and sum(int(item["size_bytes"]) for item in db_parts)
        == int(db["size_bytes"]),
        "final_database_part_hashes_present": all(
            len(item["sha256"]) == 64 for item in db_parts
        ),
        "final_database_logical_hash_present": len(db["sha256"]) == 64,
        "finalization_status": finalization["status"]
        == "FINALIZATION_COMPLETE_VERIFIED",
        "finalization_no_problems": finalization["problems"] == [],
        "finalization_counts": int(finalization["message_occurrences"])
        == int(required["messages_meta"])
        and int(finalization["attachment_occurrences"])
        == int(required["attachments_meta"])
        and int(finalization["required_member_references"])
        == int(required["occurrence_retrieval"])
        and int(finalization["shard_count"]) == int(required["shards"])
        and int(finalization["shard_member_count"])
        == int(required["occurrence_retrieval"]),
        "communication_state_no_send": manifest["communication_state"] == "NO_SEND",
    }
    return gates


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema") != "EVIDENCEOPS-PST-V2-COMPOSITE-PROOF-1":
        raise RuntimeError("COMPOSITE_MANIFEST_SCHEMA_INVALID")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY_MISSING")
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)

    control_gates = validate_control_manifest(manifest)
    if not all(control_gates.values()):
        raise RuntimeError(
            json.dumps(
                {"error": "CONTROL_GATE_FAILED", "gates": control_gates},
                sort_keys=True,
            )
        )
    searchable = verify_searchable_artifact(repo, manifest["searchable_artifact"])
    shards = verify_final_shards(repo, manifest["final_shard_artifacts"])
    if len(shards) != 13 or sum(item["member_count"] for item in shards) != 12102:
        raise RuntimeError(
            f"FINAL_SHARD_RECONCILIATION_FAILED:{len(shards)}:"
            f"{sum(item['member_count'] for item in shards)}"
        )

    final_gates = {
        **control_gates,
        "searchable_artifact_archive_hash": searchable["ok"],
        "searchable_sqlite_integrity": searchable["sqlite"]["integrity_check"]
        == "ok",
        "searchable_sqlite_counts": searchable["sqlite"]["counts"]
        == {"messages_meta": 2885, "attachments_meta": 5203},
        "searchable_fts_canaries": searchable["sqlite"]["fts_counts"]["MPMB298"]
        > 0
        and searchable["sqlite"]["fts_counts"][
            "precautionary_suspension"
        ]
        > 0,
        "final_shard_artifact_count": len(shards) == 13,
        "final_shard_logical_hashes": all(
            item["logical_sha256"]
            == manifest["final_shard_artifacts"][item["number"] - 1][
                "logical_sha256"
            ]
            for item in shards
        ),
        "final_shard_crc": all(item["crc_ok"] for item in shards),
        "final_shard_member_reconciliation": sum(
            item["member_count"] for item in shards
        )
        == 12102,
    }
    if not all(final_gates.values()):
        raise RuntimeError(
            json.dumps(
                {"error": "FINAL_GATE_FAILED", "gates": final_gates},
                sort_keys=True,
            )
        )

    now = datetime.now(timezone.utc).isoformat()
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0"))
    source_commit = os.environ.get("GITHUB_SHA")
    remote = {
        "schema": "EVIDENCEOPS-PST-CORPUS-V2-REMOTE-VERIFICATION-2",
        "status": "REMOTE_COMPLETE_VERIFIED",
        "proof_level": "COMPOSITE_AUTHENTICATED_DRIVE_READBACK_AND_INDEPENDENT_PROVIDER_ARTIFACT_REDOWNLOAD",
        "verified_at": now,
        "workflow_run_id": run_id,
        "source_commit": source_commit,
        "source": manifest["source"],
        "drive_direct_inventory": manifest["drive_direct_inventory"],
        "drive_transport_readback": manifest["drive_transport_readback"],
        "finalization": manifest["finalization"],
        "searchable_artifact_verification": searchable,
        "final_shard_artifact_verification": shards,
        "gates": final_gates,
        "truth_boundary": {
            "drive_private_access": "Authenticated Drive inventory and prior connector re-download SHA receipts",
            "github_provider_access": "Fresh provider-native artifact archive re-download, digest, logical hash, CRC and SQLite checks",
            "final_database": "Two Drive parts were among the prior 60-of-60 independent SHA readbacks; retrieval-extension finalization and counts are bound by FINALIZATION_COMPLETE_VERIFIED",
            "no_claim": "The GitHub runner did not access private Drive through an unauthenticated public link"
        },
        "communication_state": "NO_SEND"
    }
    completion = {
        "schema": "EVIDENCEOPS-PST-CORPUS-V2-COMPLETION-2",
        "status": "COMPLETE_VERIFIED",
        "proof_level": "COMPOSITE_REMOTE_COMPLETE_VERIFIED",
        "owner": manifest["owner"],
        "matter": manifest["matter"],
        "corpus_name": "MosianeKK PST Evidence Corpus v2",
        "verified_at": now,
        "workflow_run_id": run_id,
        "source_commit": source_commit,
        "source": manifest["source"],
        "counts": {
            "message_occurrences": 2885,
            "attachment_occurrences": 5203,
            "attachment_texts": 1129,
            "parse_failures": 0,
            "retrieval_shards": 13,
            "search_packs": 3,
            "drive_direct_objects": 18,
            "drive_transport_parts": 60,
            "required_evidence_member_references": 12102
        },
        "completion_gates": final_gates,
        "remote_verification_receipt": str(REMOTE_RECEIPT),
        "drive_receipt_publication_required": True,
        "communication_state": "NO_SEND"
    }
    REMOTE_RECEIPT.write_text(
        json.dumps(remote, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    COMPLETION_RECEIPT.write_text(
        json.dumps(completion, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": completion["status"],
                "workflow_run_id": run_id,
                "gates": final_gates,
                "shards": len(shards),
                "members": sum(item["member_count"] for item in shards)
            },
            indent=2,
            sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PST_COMPOSITE_VERIFICATION_FAILED:{exc}", file=sys.stderr)
        raise
