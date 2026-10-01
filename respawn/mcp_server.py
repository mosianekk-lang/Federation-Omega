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
from chatgpt_context import (
    compact_bootstrap_result,
    get_corpus_coverage_impl,
    get_current_state_impl,
    resume_mission_impl,
)

mcp = FastMCP(
    "Federation Respawn Memory",
    instructions=(
        "Recover canonical Federation context before rebuilding prior work. "
        "Use bootstrap_spawn at the beginning of FUSE/Federation work; "
        "use resume_federation_mission for n/continue/proceed/restore requests; "
        "use get_current_federation_state before claiming a capability exists now; "
        "use get_federation_corpus_coverage before claiming complete/all-chat history; "
        "use already_solved before designing a solution that may already exist. "
        "Prefer thin task-specific context over full Bible dumps. "
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
    idempotentHint=True,
    openWorldHint=False,
)


@mcp.tool(annotations=READ_ONLY)
def federation_health() -> Dict[str, Any]:
    """Use this when you need proof that the Federation respawn service is alive and know how many systems it recognizes."""
    result = dict(health_impl())
    result["chatgpt_native_context"] = {
        "enabled": True,
        "contract": "FUSE_CHATGPT_THIN_SHIM_V1",
        "write_mode": "existing_governed_publish_delta_only",
    }
    return result


@mcp.tool(annotations=READ_ONLY)
def bootstrap_spawn(
    system: str,
    matter: Optional[str] = None,
    chat_ref: Optional[str] = None,
    objective: Optional[str] = None,
    terms: Optional[List[str]] = None,
    compact: bool = True,
    max_bible_chars: int = 12000,
) -> Dict[str, Any]:
    """Use this at the start of FUSE/Federation work to recover prior canonical context before doing new work. Compact mode is the ChatGPT default and returns a thin task-specific Bible excerpt rather than a full Bible dump."""
    result = bootstrap_impl(
        SpawnRequest(
            system=system,
            matter=matter,
            chat_ref=chat_ref,
            objective=objective,
            terms=terms or [],
        )
    )
    if not compact:
        return result
    return compact_bootstrap_result(
        result,
        terms=[system, matter or "", objective or "", *(terms or [])],
        max_bible_chars=max(2000, min(max_bible_chars, 50000)),
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


@mcp.tool(annotations=READ_ONLY)
def get_current_federation_state(
    query: str = "",
    system: Optional[str] = None,
    matter: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Use this before saying a FUSE/Federation capability exists NOW or is live/current. It separates strict current evidence from merely verified historical/source evidence and fails closed when currentness is unproven."""
    provider_projection: Dict[str, Any] = {}
    if system:
        try:
            raw = bootstrap_impl(
                SpawnRequest(system=system, matter=matter, objective=query or None, terms=[])
            )
            compacted = compact_bootstrap_result(
                raw,
                terms=[system, matter or "", query],
                max_bible_chars=6000,
            )
            provider = compacted.get("provider_context")
            if isinstance(provider, dict):
                provider_projection = provider
        except Exception as exc:
            provider_projection = {
                "available": False,
                "reason": f"provider_current_state_lookup_failed:{type(exc).__name__}",
            }
    return get_current_state_impl(
        query=query,
        system=system,
        matter=matter,
        limit=max(1, min(limit, 50)),
        provider_projection=provider_projection,
    )


@mcp.tool(annotations=READ_ONLY)
def resume_federation_mission(
    system: str,
    mission: str,
    matter: Optional[str] = None,
    chat_ref: Optional[str] = None,
    terms: Optional[List[str]] = None,
    max_bible_chars: int = 12000,
) -> Dict[str, Any]:
    """Use for n, continue, proceed, restore, resume, or equivalent FUSE/Federation requests. Returns a thin continuation packet with current-state proof, already-solved candidates, conflicts, coverage truth, provider projection, and the next evidence-bounded action."""
    return resume_mission_impl(
        system=system,
        mission=mission,
        matter=matter,
        chat_ref=chat_ref,
        terms=terms or [],
        max_bible_chars=max(2000, min(max_bible_chars, 50000)),
    )


@mcp.tool(annotations=READ_ONLY)
def get_federation_corpus_coverage() -> Dict[str, Any]:
    """Use before saying Total Recall/Federation has complete or all-chat ChatGPT history. Returns explicit corpus-coverage truth and fails closed when native account-wide totality is not proven."""
    return get_corpus_coverage_impl()


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
                singular = {
                    "patterns": "pattern",
                    "bibliography": "bibliography",
                    "deltas": "delta",
                    "conflicts": "conflict",
                }[bucket]
                results.append({
                    "type": singular,
                    "id": f"{singular}:{item_id}",
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
    idempotency_key: str,
    matter: Optional[str] = None,
    chat_ref: Optional[str] = None,
    problem_signature: Optional[str] = None,
    reusable_pattern: Optional[str] = None,
    affected_systems: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    status: str = "VERIFIED",
    supersedes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Use this only after meaningful new work is complete. The idempotency key prevents accidental duplicate publication. Provider Bible writes occur only when the provider adapter is configured and explicitly write-enabled."""
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
            idempotency_key=idempotency_key,
        )
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
