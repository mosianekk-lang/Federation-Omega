from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .anchor import HttpCasTrustedAnchorStore
from .compiler import IntentCompiler
from .reconciler import Reconciler
from .resolver import CapabilityResolver
from .runtime import FabricRuntime
from .store import FabricStore
from .twin import EstateTwin


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def open_store(path: str) -> FabricStore:
    encoded = os.environ.get("CFBE_ACF_INTEGRITY_KEY_HEX")
    if not encoded:
        return FabricStore(path)
    try:
        key = bytes.fromhex(encoded)
    except ValueError as exc:
        raise ValueError("CFBE_ACF_INTEGRITY_KEY_HEX must be valid hex") from exc
    authority_id = os.environ.get("CFBE_ACF_INTEGRITY_AUTHORITY_ID", "")
    anchor_url = os.environ.get("CFBE_ACF_ANCHOR_URL", "")
    anchor_token = os.environ.get("CFBE_ACF_ANCHOR_BEARER_TOKEN", "")
    expected_store_id = os.environ.get("CFBE_ACF_EXPECTED_STORE_ID", "")
    if not anchor_url or not anchor_token or not expected_store_id:
        raise ValueError(
            "CFBE_ACF_ANCHOR_URL, CFBE_ACF_ANCHOR_BEARER_TOKEN and "
            "CFBE_ACF_EXPECTED_STORE_ID are required when integrity signing is enabled"
        )
    return FabricStore(
        path,
        integrity_key=key,
        integrity_authority_id=authority_id,
        anchor_store=HttpCasTrustedAnchorStore(anchor_url, bearer_token=anchor_token),
        expected_store_id=expected_store_id,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cfbe-acf")
    root.add_argument("--db", default="acf-state.sqlite")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("snapshot")
    plan = sub.add_parser("plan")
    plan.add_argument("intent")
    plan.add_argument("providers")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("desired")
    backup = sub.add_parser("backup")
    backup.add_argument("destination")
    sub.add_parser("health")
    sub.add_parser("readback")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    store = open_store(args.db)
    if args.command == "init":
        if store.integrity_configured:
            store.provision_integrity()
        else:
            store.initialize()
        emit(store.integrity_check())
    elif args.command == "ingest":
        emit(EstateTwin(store).ingest(load_json(args.snapshot)))
    elif args.command == "plan":
        intent = IntentCompiler().compile(load_json(args.intent))
        emit(
            CapabilityResolver().resolve(
                intent,
                load_json(args.providers)["providers"],
                verified_proof_stages=store.verified_provider_stages(
                    mission_id=intent["mission_id"],
                    mission_version=intent["mission_version"],
                    action_id=intent["proof_action_id"],
                ),
            )
        )
    elif args.command == "reconcile":
        emit(Reconciler(store).plan(load_json(args.desired)))
    elif args.command == "backup":
        emit(store.backup(args.destination))
    elif args.command == "health":
        emit(FabricRuntime(store).health())
    elif args.command == "readback":
        emit(EstateTwin(store).public_readback())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
