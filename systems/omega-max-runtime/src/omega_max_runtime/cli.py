import argparse
import json
from pathlib import Path

from .runtime import DriftSentinel, QueueConsumer


def main():
    parser = argparse.ArgumentParser(prog="omega-max-runtime")
    parser.add_argument("--repo-root", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("process")
    drift = commands.add_parser("drift")
    drift.add_argument("--desired", required=True)
    drift.add_argument("--actual", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root)
    if args.command == "process":
        output = QueueConsumer(root).process_queue()
    else:
        output = DriftSentinel(root).inspect(args.desired, args.actual)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
