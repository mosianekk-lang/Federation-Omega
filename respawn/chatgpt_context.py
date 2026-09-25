from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from bootstrap_service import SpawnRequest, bootstrap as bootstrap_impl, state

DEFAULT_CONTEXT_CHARS = 12_000
DEFAULT_LIST_LIMIT = 12

_STRICT_CURRENT = {
    "CURRENT",
    "LIVE",
    "ACTIVE_CURRENT",
    "ACTIVE_CURRENT_WITH_HOLDS",
    "CURRENT_READBACK_VERIFIED",
    "PROVIDER_READBACK_VERIFIED",
    "RESTORE_VERIFIED_FULL",
    "RESTORE_VERIFIED_BOUNDED",
    "SOURCE_ADMITTED_MAIN",
    "VERIFIED_CURRENT",
    "CURRENT_VERIFIED",
}
_SUPPORTING_VERIFIED = {
    "VERIFIED",
    "TESTED",
    "SOURCE_ADMITTED",
    "PROVIDER_WRITE_ACKNOWLEDGED",
    "VERIFIED_BOUNDED",
    "VERIFIED_BOUNDED_NO_EFFECT",
}
_NONCURRENT_MARKERS = (
    "SUPERSEDED",
    "HISTORICAL",
    "FAILED",
    "PROPOSED",
    "DESIGN",
    "DRAFT",
    "REJECTED",
    "QUARANTINED",
    "RETIRED",
)
_STATUS_KEYS = (
    "status",
    "state",
    "proof_state",
    "provider_proof_state",
    "restore_state",
    "current_state",
    "control_state",
)


def _normalise_status(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")


def _status_tokens(item: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in _STATUS_KEYS:
        value = item.get(key)
        if isinstance(value, (list, tuple, set)):
            out.extend(_normalise_status(v) for v in value if v is not None)
        elif value is not None:
            out.append(_normalise_status(value))
    return [x for x in out if x]


def _is_explicitly_noncurrent(tokens: Sequence[str], item: Dict[str, Any]) -> bool:
    if item.get("superseded_by") or item.get("supersededBy"):
        return True
    return any(any(marker in token for marker in _NONCURRENT_MARKERS) for token in tokens)


def _is_strict_current(tokens: Sequence[str], item: Dict[str, Any]) -> bool:
    if _is_explicitly_noncurrent(tokens, item):
        return False
    return any(token in _STRICT_CURRENT for token in tokens)


def _is_supporting_verified(tokens: Sequence[str], item: Dict[str, Any]) -> bool:
    if _is_explicitly_noncurrent(tokens, item):
        return False
    return any(token in _SUPPORTING_VERIFIED for token in tokens)


def _haystack(item: Dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True).lower()


def _matches(
    item: Dict[str, Any], *, query: str = "", system: Optional[str] = None, matter: Optional[str] = None
) -> bool:
    hay = _haystack(item)
    if system and system.lower() not in hay:
        return False
    if matter and matter.lower() not in hay:
        return False
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if len(t) >= 3]
    if terms and not any(term in hay for term in terms):
        return False
    return True


def _iter_memory_items(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for bucket in ("deltas", "bibliography", "patterns"):
        for item in data.get(bucket, []) or []:
            if isinstance(item, dict):
                enriched = dict(item)
                enriched.setdefault("_bucket", bucket)
                yield enriched


def _classify_current_state(
    data: Dict[str, Any], *, query: str = "", system: Optional[str] = None, matter: Optional[str] = None, limit: int = 20
) -> Dict[str, Any]:
    strict_current: List[Dict[str, Any]] = []
    supporting_verified: List[Dict[str, Any]] = []
    gated_or_historical: List[Dict[str, Any]] = []
    unclassified: List[Dict[str, Any]] = []

    for item in _iter_memory_items(data):
        if not _matches(item, query=query, system=system, matter=matter):
            continue
        tokens = _status_tokens(item)
        annotated = dict(item)
        annotated["_status_tokens"] = tokens
        if _is_explicitly_noncurrent(tokens, item):
            gated_or_historical.append(annotated)
        elif _is_strict_current(tokens, item):
            strict_current.append(annotated)
        elif _is_supporting_verified(tokens, item):
            supporting_verified.append(annotated)
        else:
            unclassified.append(annotated)

    return {
        "strict_current": strict_current[:limit],
        "supporting_verified": supporting_verified[:limit],
        "gated_or_historical": gated_or_historical[:limit],
        "unclassified": unclassified[:limit],
    }


def _relevant_excerpt(text: str, terms: Sequence[str], max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text

    lines = text.splitlines()
    needles = [t.lower().strip() for t in terms if t and len(t.strip()) >= 3]
    chosen: List[int] = []
    if needles:
        for idx, line in enumerate(lines):
            low = line.lower()
            if any(term in low for term in needles):
                chosen.extend(range(max(0, idx - 2), min(len(lines), idx + 3)))

    if not chosen:
        head = text[: max_chars // 2]
        tail = text[-max_chars // 2 :]
        return head + "\n\n[... FUSE CONTEXT COMPACTED ...]\n\n" + tail

    out: List[str] = []
    chars = 0
    seen = set()
    for idx in chosen:
        if idx in seen:
            continue
        seen.add(idx)
        line = lines[idx]
        additional = len(line) + 1
        if chars + additional > max_chars:
            break
        out.append(line)
        chars += additional
    if not out:
        return text[:max_chars]
    return "\n".join(out)


def compact_bootstrap_result(
    result: Dict[str, Any], *, terms: Sequence[str] = (), max_bible_chars: int = DEFAULT_CONTEXT_CHARS
) -> Dict[str, Any]:
    compact = dict(result)
    compact["already_solved_candidates"] = list(result.get("already_solved_candidates", []))[:DEFAULT_LIST_LIMIT]
    compact["recent_deltas"] = list(result.get("recent_deltas", []))[-DEFAULT_LIST_LIMIT:]
    compact["open_conflicts"] = list(result.get("open_conflicts", []))[:DEFAULT_LIST_LIMIT]

    provider = result.get("provider_context")
    if isinstance(provider, dict):
        provider = dict(provider)
        bible = provider.pop("canonical_bible_text", "")
        if isinstance(bible, str) and bible:
            excerpt = _relevant_excerpt(bible, terms, max_bible_chars)
            provider["canonical_bible_excerpt"] = excerpt
            provider["canonical_bible_original_chars"] = len(bible)
            provider["canonical_bible_excerpt_chars"] = len(excerpt)
            provider["canonical_bible_truncated"] = len(excerpt) < len(bible)
            provider["canonical_bible_excerpt_terms"] = [t for t in terms if t][:20]
        for key in ("recent_sync_events", "shared_learnings", "open_conflicts", "respawn_bibliography"):
            if isinstance(provider.get(key), list):
                provider[key] = provider[key][-DEFAULT_LIST_LIMIT:]
        compact["provider_context"] = provider

    compact["context_contract"] = {
        "mode": "CHATGPT_THIN_SHIM",
        "max_bible_chars": max_bible_chars,
        "rule": "Return the smallest sufficient context; retrieve deeper evidence only when needed.",
    }
    return compact


def get_corpus_coverage_impl() -> Dict[str, Any]:
    data = state()
    coverage = data.get("coverage")
    if not coverage:
        return {
            "coverage_state": "UNKNOWN",
            "full_account_history_proven": False,
            "native_chat_totality_proven": False,
            "bibliography_entries_seen": len(data.get("bibliography", []) or []),
            "note": (
                "No corpus coverage ledger is present in the Respawn runtime state. "
                "Do not claim complete/all-chat ChatGPT history from bibliography or memory alone."
            ),
        }
    if isinstance(coverage, list):
        coverage_obj: Dict[str, Any] = {"sources": coverage}
    elif isinstance(coverage, dict):
        coverage_obj = dict(coverage)
    else:
        coverage_obj = {"raw": coverage}

    explicit_full = bool(
        coverage_obj.get("full_account_history_proven")
        or coverage_obj.get("native_chat_totality_proven")
        or coverage_obj.get("complete_native_provider_coverage")
    )
    return {
        "coverage_state": coverage_obj.get("completeness_state")
        or coverage_obj.get("coverage_state")
        or "PARTIAL_OR_UNCLASSIFIED",
        "full_account_history_proven": explicit_full,
        "native_chat_totality_proven": bool(coverage_obj.get("native_chat_totality_proven", False)),
        "bibliography_entries_seen": len(data.get("bibliography", []) or []),
        "coverage": coverage_obj,
        "note": "A source/export may be complete for itself without proving account-wide native ChatGPT totality.",
    }


def get_current_state_impl(
    *, query: str = "", system: Optional[str] = None, matter: Optional[str] = None, limit: int = 20,
    provider_projection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    classified = _classify_current_state(state(), query=query, system=system, matter=matter, limit=limit)

    projection = provider_projection if isinstance(provider_projection, dict) else {}
    system_record = projection.get("system_record") if isinstance(projection, dict) else None
    provider_readback = bool(projection.get("provider_readback")) if isinstance(projection, dict) else False

    if classified["strict_current"]:
        proof = "CURRENT_PROVEN_STRICT_LOCAL_STATE"
    elif provider_readback and isinstance(system_record, dict) and system_record:
        proof = "CURRENT_PROVIDER_PROJECTION_AVAILABLE"
    elif classified["supporting_verified"]:
        proof = "VERIFIED_HISTORY_PRESENT_CURRENTNESS_UNPROVEN"
    else:
        proof = "CURRENT_STATE_UNPROVEN"

    return {
        "query": query,
        "system": system,
        "matter": matter,
        "current_state_proof": proof,
        "claimable_current": classified["strict_current"],
        "supporting_verified_not_current_by_itself": classified["supporting_verified"],
        "gated_or_historical": classified["gated_or_historical"],
        "unclassified": classified["unclassified"],
        "provider_current_projection": system_record if provider_readback else None,
        "provider_readback": provider_readback,
        "rule": (
            "Do not convert VERIFIED/TESTED/source-admitted historical evidence into a claim that a capability is current or live. "
            "Currentness and runtime/provider maturity require their own evidence."
        ),
    }


def _extract_next_action(*objects: Any) -> Optional[str]:
    preferred = ("next_action", "next action", "next", "current_next_action", "recommended_next_action")
    for obj in objects:
        if isinstance(obj, dict):
            lowered = {str(k).strip().lower().replace("_", " "): v for k, v in obj.items()}
            for key in preferred:
                value = lowered.get(key.replace("_", " "))
                if isinstance(value, str) and value.strip():
                    return value.strip()
        elif isinstance(obj, list):
            for item in reversed(obj):
                value = _extract_next_action(item)
                if value:
                    return value
    return None


def resume_mission_impl(
    *, system: str, mission: str, matter: Optional[str] = None, chat_ref: Optional[str] = None,
    terms: Optional[List[str]] = None, max_bible_chars: int = DEFAULT_CONTEXT_CHARS,
) -> Dict[str, Any]:
    terms = terms or []
    request = SpawnRequest(
        system=system,
        matter=matter,
        chat_ref=chat_ref,
        objective=mission,
        terms=terms,
    )
    raw = bootstrap_impl(request)
    search_terms = [mission, matter or "", system, *terms]
    compact = compact_bootstrap_result(raw, terms=search_terms, max_bible_chars=max_bible_chars)
    provider = compact.get("provider_context") if isinstance(compact.get("provider_context"), dict) else {}
    current = get_current_state_impl(
        query=mission,
        system=system,
        matter=matter,
        limit=8,
        provider_projection=provider,
    )
    coverage = get_corpus_coverage_impl()
    conflicts = compact.get("open_conflicts", []) or []
    solved = compact.get("already_solved_candidates", []) or []

    next_action = _extract_next_action(
        provider.get("system_record") if isinstance(provider, dict) else None,
        provider.get("recent_sync_events") if isinstance(provider, dict) else None,
        solved,
        compact.get("recent_deltas"),
    )
    if not next_action:
        if conflicts:
            next_action = (
                "Continue only unaffected lanes and reconcile the highest-authority relevant open conflict before any consequence that depends on it."
            )
        elif current["claimable_current"] or solved:
            next_action = (
                "Resume from the highest-authority verified/current evidence returned in this packet; do not restart already-solved work."
            )
        else:
            next_action = (
                "Establish a bounded verified checkpoint from canonical provider-visible evidence before claiming mission continuity."
            )

    if conflicts:
        mode = "RESUME_WITH_VISIBLE_CONFLICTS"
    elif current["claimable_current"] or solved or current["provider_readback"]:
        mode = "RESUME_FROM_EXISTING_EVIDENCE"
    else:
        mode = "RECONSTRUCT_BOUNDED"

    return {
        "mission": mission,
        "system": system,
        "matter": matter,
        "continuation_mode": mode,
        "current_state": current,
        "already_solved_candidates": solved[:8],
        "recent_deltas": (compact.get("recent_deltas") or [])[-8:],
        "open_conflicts": conflicts[:8],
        "provider_context": provider,
        "coverage": coverage,
        "hyper_intelligence_performance": compact.get("hyper_intelligence_performance", {}),
        "hyper_intelligence_performance_guard": compact.get("hyper_intelligence_performance_guard", {}),
        "next_executable_action": next_action,
        "proof_boundaries": [
            "Historical proposal/design does not prove current runtime capability.",
            "Repository/source admission does not prove provider deployment or external effect.",
            "Bibliography/search coverage does not prove full native ChatGPT account history.",
            "A native current provider projection outranks repeated historical summaries for present-state claims.",
            "Hyper-performance promotion requires matched empirical nonregression proof.",
        ],
        "generated_at": raw.get("generated_at"),
    }
