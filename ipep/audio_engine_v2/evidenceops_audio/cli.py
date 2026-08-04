from __future__ import annotations

import argparse
import json
from .core import EvidenceOpsAudioEngine, load_manifest


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="evidenceops-audio")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--workspace", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("preflight")
    verify = sub.add_parser("verify-chunk")
    verify.add_argument("--sequence", type=int, required=True)
    verify.add_argument("--audio", required=True)
    transcribe = sub.add_parser("transcribe-chunk")
    transcribe.add_argument("--sequence", type=int, required=True)
    transcribe.add_argument("--audio", required=True)
    transcribe.add_argument("--provider")
    sub.add_parser("resume-plan")
    sub.add_parser("assemble")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest)
    engine = EvidenceOpsAudioEngine(args.workspace, manifest)
    if args.command == "validate":
        emit(manifest.validate())
    elif args.command == "preflight":
        emit(engine.preflight())
    elif args.command == "verify-chunk":
        chunk = next(c for c in manifest.chunks if c.sequence == args.sequence)
        emit(engine.verify_chunk(chunk, args.audio))
    elif args.command == "transcribe-chunk":
        emit(engine.transcribe_chunk(args.sequence, args.audio, args.provider))
    elif args.command == "resume-plan":
        emit(engine.build_resume_plan())
    elif args.command == "assemble":
        emit(engine.assemble_transcript())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
