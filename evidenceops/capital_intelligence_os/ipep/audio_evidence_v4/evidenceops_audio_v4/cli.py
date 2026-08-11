from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger import EvidenceLedger
from .legacy import import_legacy_whisper_run
from .pipeline import AudioEvidenceCompletionPipeline
from .providers import CommandTranslationAdapter, WhisperCppConfig, WhisperCppUnitAdapter


def print_json(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidenceops-audio-v4",
        description="Governed audio evidence collection, transcription, translation, review and retrieval.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an evidence workspace")
    init.add_argument("workspace")
    init.add_argument("--matter", required=True)
    init.add_argument("--case-wall", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--confidentiality", default="PRIVATE_EVIDENCE")

    collect = sub.add_parser("collect", help="Collect and preserve a source recording")
    collect.add_argument("workspace")
    collect.add_argument("source")
    collect.add_argument("--item-id", required=True)
    collect.add_argument("--actor", required=True)
    collect.add_argument("--captured-at")
    collect.add_argument("--captured-by")
    collect.add_argument("--device")
    collect.add_argument("--location")

    units = sub.add_parser("prepare-units", help="Normalize and split a source into fixed windows")
    units.add_argument("workspace")
    units.add_argument("--source-item-id", required=True)
    units.add_argument("--actor", required=True)
    units.add_argument("--unit-seconds", type=float, default=60.0)

    transcribe = sub.add_parser("transcribe", help="Run local whisper.cpp with per-unit receipts")
    transcribe.add_argument("workspace")
    transcribe.add_argument("unit_plan")
    transcribe.add_argument("--actor", required=True)
    transcribe.add_argument("--binary", required=True)
    transcribe.add_argument("--model", required=True)
    transcribe.add_argument("--vad-model")
    transcribe.add_argument("--language", default="auto")

    legacy = sub.add_parser("import-legacy", help="Import an existing structured whisper run with explicit limitations")
    legacy.add_argument("workspace")
    legacy.add_argument("job_manifest")
    legacy.add_argument("structured_transcript")
    legacy.add_argument("--source-item-id", required=True)
    legacy.add_argument("--source-language", default="en")
    legacy.add_argument("--actor", required=True)

    translate = sub.add_parser("translate", help="Run a provider-neutral JSON translation command")
    translate.add_argument("workspace")
    translate.add_argument("--command", required=True)
    translate.add_argument("--target-language", required=True)
    translate.add_argument("--actor", required=True)

    index = sub.add_parser("index", help="Build the searchable evidence index")
    index.add_argument("workspace")

    search = sub.add_parser("search", help="Search transcript and translations")
    search.add_argument("workspace")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--language")
    search.add_argument("--verified-only", action="store_true")

    audit = sub.add_parser("audit", help="Audit custody, unit accounting and certification state")
    audit.add_argument("workspace")

    seal = sub.add_parser("seal", help="Seal the current workspace state")
    seal.add_argument("workspace")
    seal.add_argument("--actor", required=True)
    seal.add_argument("--note", default="")
    return parser


def load_pipeline(workspace: str) -> AudioEvidenceCompletionPipeline:
    ledger = EvidenceLedger(workspace)
    if not ledger.workspace_manifest_path.exists():
        raise SystemExit(f"workspace is not initialized: {workspace}")
    return AudioEvidenceCompletionPipeline(ledger)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        pipeline = AudioEvidenceCompletionPipeline.create(
            args.workspace,
            matter=args.matter,
            case_wall=args.case_wall,
            owner=args.owner,
            confidentiality=args.confidentiality,
        )
        print_json(pipeline.ledger.read_workspace_manifest())
        return 0
    pipeline = load_pipeline(args.workspace)
    if args.command == "collect":
        print_json(
            pipeline.collect_source(
                args.source,
                source_item_id=args.item_id,
                actor=args.actor,
                capture_metadata={
                    "captured_at": args.captured_at,
                    "captured_by": args.captured_by,
                    "device": args.device,
                    "location": args.location,
                },
            )
        )
    elif args.command == "prepare-units":
        plan = pipeline.prepare_units(
            source_item_id=args.source_item_id,
            actor=args.actor,
            unit_seconds=args.unit_seconds,
        )
        print_json({"unit_count": len(plan), "units": plan})
    elif args.command == "transcribe":
        plan = json.loads(Path(args.unit_plan).read_text(encoding="utf-8"))
        units = plan.get("units", plan)
        adapter = WhisperCppUnitAdapter(
            WhisperCppConfig(
                binary=args.binary,
                model=args.model,
                vad_model=args.vad_model,
                language=args.language,
            )
        )
        print_json(pipeline.automated_transcribe(units=units, adapter=adapter, actor=args.actor))
    elif args.command == "import-legacy":
        print_json(
            import_legacy_whisper_run(
                pipeline.ledger,
                job_manifest_path=args.job_manifest,
                structured_transcript_path=args.structured_transcript,
                actor=args.actor,
                source_item_id=args.source_item_id,
                source_language=args.source_language,
            )
        )
    elif args.command == "translate":
        adapter = CommandTranslationAdapter(args.command)
        print_json(
            pipeline.automated_translate(
                adapter=adapter,
                target_language=args.target_language,
                actor=args.actor,
            )
        )
    elif args.command == "index":
        print_json(pipeline.build_search_index())
    elif args.command == "search":
        print_json(
            pipeline.search(
                args.query,
                limit=args.limit,
                language=args.language,
                verified_only=args.verified_only,
            )
        )
    elif args.command == "audit":
        print_json(pipeline.audit())
    elif args.command == "seal":
        print_json(pipeline.ledger.seal_snapshot(actor=args.actor, note=args.note))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
