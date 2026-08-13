from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from bootstrap_service import (
    DeltaRequest,
    SolvedRequest,
    SpawnRequest,
    already_solved as already_solved_impl,
    bootstrap as bootstrap_impl,
    health as health_impl,
    manifest,
    publish_delta as publish_delta_impl,
    state,
)

mcp = FastMCP(
    "Federation Respawn Memory",
    instructions=(
        "Recover canonical Federation context before rebuilding prior work. "
        "Use bootstrap_spawn at the beginning of Bubbles/Lex/Federation work; "
        "use already_solved before designing a solution that may already exist. "
        "Never infer provider-side completion from repository state."
    ),
    stateless_http=True,
    json_response=True,
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

WRITE_NONDESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


@mcp.tool(annotations=READ_ONLY)
def federation_health() -> Dict[str, Any]:
    """Use this when you need proof that the Federation respawn service is alive and know how many systems it recognizes."""
    return health_impl()


@mcp.tool(annotations=READ_ONLY)
def bootstrap_spawn(
    system: str,
    matter: Optional[str] = None,
    chat_ref: Optional[str] = None,
    objective: Optional[str] = None,
    terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Use this at the start of a Bubbles, Lex Advocate, or Federation-system spawn to recover prior canonical context before doing new work."""
    return bootstrap_impl(
        SpawnRequest(
            system=system,
            matter=matter,
            chat_ref=chat_ref,
            objective=objective,
            terms=terms or [],
        )
    )


@mcp.tool(annotations=READ_ONLY)
def already_solved(
    problem: str,
    system: Optional[str] = None,
    matter: Optional[str] = None,
    terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Use this before substantial design or troubleshooting to find prior solutions, reusable patterns, bibliography entries, and deltas."""
    return already_solved_impl(
        SolvedRequest(
            problem=problem,
            system=system,
            matter=matter,
            terms=terms or [],
        )
    )


@mcp.tool(name="search", annotations=READ_ONLY)
def search_federation(query: str) -> Dict[str, Any]:
    """Use this to search the Federation respawn memory for systems, prior work, patterns, conflicts, and deltas relevant to a query."""
    query_l = query.strip().lower()
    if not query_l:
        return {"results": []}

    results: List[Dict[str, Any]] = []
    m = manifest()
    for system in m.get("registered_systems", []):
        if query_l in system.lower():
            results.append({
                "type": "system",
                "id": f"system:{system}",
                "title": system,
                "text": f"Registered Federation system: {system}",
            })

    s = state()
    for bucket in ("patterns", "bibliography", "deltas", "conflicts"):
        for item in s.get(bucket, []):
            hay = json.dumps(item, ensure_ascii=False).lower()
            if query_l in hay:
                item_id = (
                    item.get("pattern_id")
                    or item.get("entry_id")
                    or item.get("delta_id")
                    or item.get("conflict_id")
                    or "unknown"
                )
                results.append({
                    "type": bucket.rstrip("s"),
                    "id": f"{bucket}:{item_id}",
                    "title": item.get("work_summary") or item.get("pattern") or item.get("summary") or str(item_id),
                    "text": json.dumps(item, ensure_ascii=False),
                })
    return {"results": results[:50]}


@mcp.tool(name="fetch", annotations=READ_ONLY)
def fetch_federation(id: str) -> Dict[str, Any]:
    """Use this after search to fetch one exact Federation memory item by the returned id."""
    if id.startswith("system:"):
        name = id.split(":", 1)[1]
        m = manifest()
        if name not in m.get("registered_systems", []):
            raise ValueError(f"Unknown system: {name}")
        return {
            "id": id,
            "type": "system",
            "system": name,
            "domain_authority": {
                domain: names
                for domain, names in m.get("domain_authority", {}).items()
                if name in names
            },
            "bootstrap_order": m.get("bootstrap_order", []),
            "proof_rule": m.get("proof_rule"),
        }

    prefix, _, item_id = id.partition(":")
    bucket_map = {
        "pattern": "patterns",
        "bibliography": "bibliography",
        "delta": "deltas",
        "conflict": "conflicts",
        "patterns": "patterns",
        "deltas": "deltas",
        "conflicts": "conflicts",
    }
    bucket = bucket_map.get(prefix)
    if not bucket:
        raise ValueError(f"Unsupported id: {id}")
    id_fields = {
        "patterns": "pattern_id",
        "bibliography": "entry_id",
        "deltas": "delta_id",
        "conflicts": "conflict_id",
    }
    field = id_fields[bucket]
    for item in state().get(bucket, []):
        if str(item.get(field)) == item_id:
            return {"id": id, "type": prefix, "item": item}
    raise ValueError(f"Not found: {id}")


@mcp.tool(annotations=WRITE_NONDESTRUCTIVE)
def publish_delta(
    source_system: str,
    summary: str,
    matter: Optional[str] = None,
    chat_ref: Optional[str] = None,
    problem_signature: Optional[str] = None,
    reusable_pattern: Optional[str] = None,
    affected_systems: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    status: str = "VERIFIED",
    supersedes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Use this only after meaningful new work is complete to publish a local runtime delta and bibliography entry. Provider-side Bible writes require a configured adapter and separate proof."""
    return publish_delta_impl(
        DeltaRequest(
            source_system=source_system,
            matter=matter,
            chat_ref=chat_ref,
            summary=summary,
            problem_signature=problem_signature,
            reusable_pattern=reusable_pattern,
            affected_systems=affected_systems or [],
            evidence_refs=evidence_refs or [],
            status=status,
            supersedes=supersedes or [],
        )
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
