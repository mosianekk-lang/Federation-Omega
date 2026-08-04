#!/usr/bin/env python3
"""Prepare and verify connector-safe Drive transport for EvidenceOps PST Corpus v2.

Logical corpus objects are preserved exactly. Files larger than the configured
transport ceiling are split into independently hashable parts, with a
reconstruction manifest. This is transport chunking, not evidentiary mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

PUBLISH_ROOTS = ("00_CONTROL", "04_INDEX", "05_SEARCH_PACKS", "06_RETRIEVAL_SHARDS", "07_LOGS")
BLOCK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(BLOCK), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_stream(source: BinaryIO, target: BinaryIO, limit: int | None = None) -> int:
    written = 0
    while True:
        amount = BLOCK if limit is None else min(BLOCK, limit - written)
        if amount <= 0:
            break
        data = source.read(amount)
        if not data:
            break
        target.write(data)
        written += len(data)
    return written


def prepare(corpus: Path, output: Path, max_mib: int) -> dict:
    max_bytes = max_mib * 1024 * 1024
    if max_bytes < 8 * 1024 * 1024:
        raise ValueError("max transport size must be at least 8 MiB")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    logical: list[dict] = []
    upload_objects: list[dict] = []

    for root_name in PUBLISH_ROOTS:
        root = corpus / root_name
        if not root.exists():
            continue
        for source in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = source.relative_to(corpus).as_posix()
            logical_row = {
                "logical_relpath": rel,
                "size_bytes": source.stat().st_size,
                "sha256": sha256_file(source),
                "transport": "direct" if source.stat().st_size <= max_bytes else "multipart",
                "parts": [],
            }
            if source.stat().st_size <= max_bytes:
                target = output / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                part_row = {
                    "transport_relpath": rel,
                    "size_bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "part_number": 1,
                    "part_count": 1,
                }
                logical_row["parts"].append(part_row)
                upload_objects.append(part_row | {"logical_relpath": rel})
            else:
                parts_dir = output / "98_TRANSPORT_PARTS" / (rel + ".parts")
                parts_dir.mkdir(parents=True, exist_ok=True)
                part_number = 0
                with source.open("rb") as src:
                    remaining = source.stat().st_size
                    while remaining:
                        part_number += 1
                        target = parts_dir / f"part-{part_number:05d}.bin"
                        with target.open("wb") as dst:
                            written = copy_stream(src, dst, min(max_bytes, remaining))
                        if written <= 0:
                            raise RuntimeError(f"zero-byte split write for {rel}")
                        remaining -= written
                        part_row = {
                            "transport_relpath": target.relative_to(output).as_posix(),
                            "size_bytes": target.stat().st_size,
                            "sha256": sha256_file(target),
                            "part_number": part_number,
                            "part_count": 0,
                        }
                        logical_row["parts"].append(part_row)
                count = len(logical_row["parts"])
                for part in logical_row["parts"]:
                    part["part_count"] = count
                    upload_objects.append(part | {"logical_relpath": rel})
            logical.append(logical_row)

    manifest = {
        "schema": "EVIDENCEOPS-PST-DRIVE-TRANSPORT-1",
        "status": "PREPARED",
        "max_transport_bytes": max_bytes,
        "corpus_name": corpus.name,
        "logical_object_count": len(logical),
        "upload_object_count": len(upload_objects),
        "logical_total_bytes": sum(x["size_bytes"] for x in logical),
        "upload_total_bytes": sum(x["size_bytes"] for x in upload_objects),
        "logical_objects": logical,
        "upload_objects": upload_objects,
    }
    write_json(output / "00_CONTROL" / "DRIVE_TRANSPORT_MANIFEST.json", manifest)
    manifest_file = output / "00_CONTROL" / "DRIVE_TRANSPORT_MANIFEST.json"
    upload_objects.append({
        "logical_relpath": "00_CONTROL/DRIVE_TRANSPORT_MANIFEST.json",
        "transport_relpath": "00_CONTROL/DRIVE_TRANSPORT_MANIFEST.json",
        "size_bytes": manifest_file.stat().st_size,
        "sha256": sha256_file(manifest_file),
        "part_number": 1,
        "part_count": 1,
    })
    plan = {
        "schema": "EVIDENCEOPS-PST-DRIVE-UPLOAD-PLAN-1",
        "corpus_name": corpus.name,
        "root_folders": list(PUBLISH_ROOTS) + ["98_TRANSPORT_PARTS"],
        "objects": upload_objects,
        "completion_gate": "Every uploaded object re-downloaded and hash-verified; logical objects reconstructed and validated.",
    }
    write_json(output / "00_CONTROL" / "DRIVE_UPLOAD_PLAN.json", plan)
    return {"manifest": manifest, "plan": plan}


def reconstruct(output: Path, row: dict, destination: Path) -> Path:
    target = destination / row["logical_relpath"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as dst:
        for part in sorted(row["parts"], key=lambda x: x["part_number"]):
            path = output / part["transport_relpath"]
            if path.stat().st_size != part["size_bytes"] or sha256_file(path) != part["sha256"]:
                raise RuntimeError(f"transport part mismatch: {part['transport_relpath']}")
            with path.open("rb") as src:
                copy_stream(src, dst)
    if target.stat().st_size != row["size_bytes"] or sha256_file(target) != row["sha256"]:
        raise RuntimeError(f"logical reconstruction mismatch: {row['logical_relpath']}")
    return target


def validate_logical(path: Path) -> dict:
    result = {"relpath": path.as_posix(), "validation": "hash-only"}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
        if bad:
            raise RuntimeError(f"zip CRC failed: {path}: {bad}")
        result["validation"] = "zip-crc-ok"
    elif path.name == "corpus_search.db":
        db = sqlite3.connect(path)
        try:
            status = db.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            db.close()
        if status != "ok":
            raise RuntimeError(f"SQLite integrity failed: {path}: {status}")
        result["validation"] = "sqlite-integrity-ok"
    return result


def verify(output: Path) -> dict:
    manifest = json.loads((output / "00_CONTROL" / "DRIVE_TRANSPORT_MANIFEST.json").read_text(encoding="utf-8"))
    checks = []
    with tempfile.TemporaryDirectory(prefix="evidenceops-pst-reconstruct-") as tmp:
        destination = Path(tmp)
        for row in manifest["logical_objects"]:
            logical = reconstruct(output, row, destination)
            checks.append(validate_logical(logical))
    report = {
        "schema": "EVIDENCEOPS-PST-DRIVE-TRANSPORT-VERIFICATION-1",
        "status": "TRANSPORT_COMPLETE_VERIFIED",
        "logical_object_count": len(checks),
        "checks": checks,
    }
    write_json(output / "00_CONTROL" / "DRIVE_TRANSPORT_LOCAL_VERIFICATION.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--corpus", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--max-mib", type=int, default=90)
    v = sub.add_parser("verify")
    v.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(Path(args.corpus), Path(args.output), args.max_mib) if args.command == "prepare" else verify(Path(args.output))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
