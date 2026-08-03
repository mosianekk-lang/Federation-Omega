from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from runtime import digest, utc_now
from semantic_memory import MemoryRecord, SemanticMemory


def ts(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    memory = SemanticMemory(out / "semantic-runtime")
    memory.add(MemoryRecord("declared-cloud", "cloud runtime", "cloud runtime declared live", "registry://cloud", ts(100), True, 0.75, token_cost=3, workstreams=("ws-cloud",)))
    memory.add(MemoryRecord("proven-cloud", "cloud runtime", "cloud runtime control plane only", "proof://cloud", ts(990), True, 0.99, priority=100, supersedes=("declared-cloud",), token_cost=4, workstreams=("ws-cloud",)))
    memory.add(MemoryRecord("apps-claim", "apps authority", "apps script direct access verified", "claim://apps", ts(900), False, 0.35, contradicts=("apps-proof",), token_cost=2, workstreams=("ws-cloud",)))
    memory.add(MemoryRecord("apps-proof", "apps authority", "apps script owner consent required", "proof://apps", ts(995), True, 0.99, priority=100, contradicts=("apps-claim",), token_cost=2, workstreams=("ws-cloud",)))
    memory.add(MemoryRecord("irrelevant", "commercial", "customer revenue not proven", "proof://commercial", ts(995), True, 0.99, token_cost=2, workstreams=("ws-commercial",)))

    request = {
        "query": "cloud runtime apps authority",
        "now_epoch": 1000,
        "token_budget": 6,
        "workstream_id": "ws-cloud",
        "half_life_seconds": 200,
    }
    context = memory.rebuild_context(request)
    restarted = SemanticMemory(out / "semantic-runtime")
    rebuilt = restarted.rebuild_context(request)
    selected = [row["memory_id"] for row in context["selected"]]

    gates = {
        "retrieval_scoring": bool(context["selected"]) and context["selected"][0]["memory_id"] in {"proven-cloud", "apps-proof"},
        "freshness_decay": context["selected"][0]["retrieval_score"] > 0,
        "supersession_control": "declared-cloud" not in selected and "declared-cloud" in context["superseded_excluded"],
        "contradiction_awareness": bool(context["contradictions"]),
        "context_budget": context["tokens_used"] <= context["token_budget"],
        "workstream_filtering": "irrelevant" not in selected,
        "evidence_lineage": memory.verify_lineage() and restarted.verify_lineage(),
        "restart_rebuild": rebuilt["context_hash"] == context["context_hash"],
        "deterministic_context": [r["memory_id"] for r in rebuilt["selected"]] == selected,
    }
    receipt = {
        "status": "SEMANTIC_MEMORY_VERIFIED" if all(gates.values()) else "SEMANTIC_MEMORY_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "metrics": {
            "records": len(memory.records),
            "selected": len(selected),
            "tokens_used": context["tokens_used"],
            "contradiction_clusters": len(context["contradictions"]),
        },
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_semantic_memory": True,
            "external_vector_database_live": False,
            "cross_chat_live_memory_sync": False,
            "model_embedding_provider_live": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-semantic-memory-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "compiled-context.json").write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
