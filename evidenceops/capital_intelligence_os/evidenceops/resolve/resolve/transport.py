from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import BinaryIO


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_exact(source: BinaryIO, target: BinaryIO, limit: int, block: int = 1024 * 1024) -> int:
    written = 0
    while written < limit:
        chunk = source.read(min(block, limit - written))
        if not chunk:
            break
        target.write(chunk)
        written += len(chunk)
    return written


def segment_file(source: Path, output_dir: Path, part_size: int) -> dict:
    if part_size <= 0:
        raise ValueError("part_size must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_size = source.stat().st_size
    part_count = max(1, (source_size + part_size - 1) // part_size)
    parts = []
    with source.open("rb") as handle:
        for index in range(1, part_count + 1):
            name = f"{source.name}.part-{index:05d}-of-{part_count:05d}.bin"
            target = output_dir / name
            with target.open("wb") as out:
                written = _copy_exact(handle, out, part_size)
            parts.append({
                "index": index,
                "name": name,
                "size": written,
                "sha256": sha256_file(target),
            })
    manifest = {
        "schema": "RESOLVE-TRANSPORT-1",
        "logical_name": source.name,
        "logical_size": source_size,
        "logical_sha256": sha256_file(source),
        "part_size": part_size,
        "part_count": part_count,
        "parts": parts,
    }
    (output_dir / f"{source.name}.transport.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def reconstruct(manifest_path: Path, parts_dir: Path, output_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as out:
        for part in sorted(manifest["parts"], key=lambda row: row["index"]):
            path = parts_dir / part["name"]
            actual_hash = sha256_file(path)
            if actual_hash != part["sha256"]:
                raise ValueError(f"Part hash mismatch: {part['name']}")
            if path.stat().st_size != part["size"]:
                raise ValueError(f"Part size mismatch: {part['name']}")
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    out.write(chunk)
    actual_size = output_path.stat().st_size
    actual_hash = sha256_file(output_path)
    if actual_size != manifest["logical_size"]:
        raise ValueError("Reconstructed size mismatch")
    if actual_hash != manifest["logical_sha256"]:
        raise ValueError("Reconstructed SHA-256 mismatch")
    return {"path": str(output_path), "size": actual_size, "sha256": actual_hash}
