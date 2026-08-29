from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from .version_tree_store import FileVersionTreeStore


CHECKPOINT_BEFORE_REFS = "IMMUTABLE_OBJECTS_WRITTEN_BEFORE_REFS"
CHECKPOINT_AFTER_REFS = "REFS_REPLACED_BEFORE_POST_WRITE_READBACK"
_ALLOWED_CHECKPOINTS = {CHECKPOINT_BEFORE_REFS, CHECKPOINT_AFTER_REFS}
_CONFIRMATION = "SOVARA_LOCAL_CRASH_DRILL_ONLY"


def _write_marker(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    with path.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def prepare_crash_checkpoint(
    *,
    root: str | Path,
    asset_id: str,
    checkpoint: str,
    marker: str | Path,
    expected_head: str,
    content: bytes,
) -> dict[str, Any]:
    """Prepare one local crash checkpoint and then return marker metadata.

    This function intentionally stops before the normal post-mutation restart readback.
    The CLI worker calls it and then blocks so a parent test can terminate the process
    abruptly. It performs local filesystem writes only and never contacts a provider.
    """

    if checkpoint not in _ALLOWED_CHECKPOINTS:
        raise ValueError(f"unsupported crash checkpoint: {checkpoint}")

    store = FileVersionTreeStore(root, asset_id)
    tree, prior_receipt = store.load()
    observed_head = tree.branch_heads().get("main")
    if observed_head != expected_head:
        raise RuntimeError(
            f"main head mismatch before drill: expected {expected_head}, observed {observed_head}"
        )

    _, _, refs_before_sha256 = store._read_refs()
    node = tree.commit(
        branch="main",
        expected_head=expected_head,
        content=content,
        metadata={"source": "SOVARA_PROCESS_CRASH_DRILL", "synthetic": True},
    )
    store._persist_immutable_objects(tree)

    refs_replaced = False
    if checkpoint == CHECKPOINT_AFTER_REFS:
        refs = store._refs_document(
            tree=tree,
            generation=prior_receipt.generation + 1,
            previous_refs_sha256=refs_before_sha256,
        )
        store._replace_refs_guarded(
            refs,
            expected_current_refs_sha256=refs_before_sha256,
        )
        refs_replaced = True

    payload = {
        "schema": "SOVARA_VERSION_TREE_PROCESS_CRASH_CHECKPOINT_V1",
        "checkpoint": checkpoint,
        "asset_id": asset_id,
        "expected_head_before": expected_head,
        "candidate_head_after": node.version_id,
        "candidate_content_sha256": node.content_sha256,
        "generation_before": prior_receipt.generation,
        "candidate_generation_after": prior_receipt.generation + 1,
        "refs_before_sha256": refs_before_sha256,
        "refs_replaced": refs_replaced,
        "local_filesystem_only": True,
        "external_effect_performed": False,
        "provider_effect_performed": False,
        "production_deployment_performed": False,
    }
    _write_marker(Path(marker), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--checkpoint", choices=sorted(_ALLOWED_CHECKPOINTS), required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--content", default="crash-drill-next-version")
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)

    if args.confirm != _CONFIRMATION:
        print("SOVARA_CRASH_DRILL_REFUSED: exact local-only confirmation required", file=sys.stderr)
        return 64

    payload = prepare_crash_checkpoint(
        root=args.root,
        asset_id=args.asset_id,
        checkpoint=args.checkpoint,
        marker=args.marker,
        expected_head=args.expected_head,
        content=args.content.encode("utf-8"),
    )
    print(json.dumps(payload, sort_keys=True), flush=True)
    print("SOVARA_CRASH_DRILL_READY_FOR_ABRUPT_TERMINATION", flush=True)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
