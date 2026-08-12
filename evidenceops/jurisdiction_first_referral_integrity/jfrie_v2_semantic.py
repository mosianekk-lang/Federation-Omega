"""Bounded deterministic semantic-integrity controls for JFRIE v2/EACIA.

A1_INTERNAL only. Signals are review/release controls, not legal merits, truth,
credibility, admissibility, intent, provider execution, or full C001-C100 parity.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json, re, unicodedata
from typing import Iterable, Sequence

VERSION = "2.0.0-semantic-integrity-slice-1"
FULL_V2_PARITY = False
AUTHORITY_CEILING = "A1_INTERNAL"

@dataclass(frozen=True)
class SemanticClaim:
    claim_id: str
    text: str
    matter_id: str

@dataclass(frozen=True)
class CitationNode:
    source_id: str
    cites: tuple[str, ...] = ()

@dataclass(frozen=True)
class VersionObservation:
    object_id: str
    version_id: str
    semantic_sha256: str

@dataclass(frozen=True)
class ReleaseSnapshot:
    snapshot_id: str
    claim_hashes: tuple[tuple[str, str], ...]
    snapshot_sha256: str

@dataclass(frozen=True)
class Finding:
    code: str
    object_ids: tuple[str, ...]

_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)

def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_WORD_RE.sub(" ", value).replace("_", " ").split())

def semantic_sha(text: str) -> str:
    return sha256(normalize_text(text).encode("utf-8")).hexdigest()

def fingerprint(claim: SemanticClaim) -> str:
    payload = {"claim_id": claim.claim_id, "matter_id": claim.matter_id, "text": normalize_text(claim.text)}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def paraphrase_candidates(claims: Sequence[SemanticClaim], threshold: float = 0.60) -> tuple[tuple[str, str, float], ...]:
    """Same-matter lexical-semantic review candidates only; never equivalence proof."""
    if not 0 <= threshold <= 1: raise ValueError("threshold out of range")
    out = []
    for i, left in enumerate(claims):
        for right in claims[i + 1:]:
            if left.matter_id != right.matter_id: continue
            lt, rt = normalize_text(left.text).split(), normalize_text(right.text).split()
            lb = [f"{lt[n]} {lt[n+1]}" for n in range(max(0, len(lt)-1))]
            rb = [f"{rt[n]} {rt[n+1]}" for n in range(max(0, len(rt)-1))]
            score = round(0.70 * _jaccard(lt, rt) + 0.30 * _jaccard(lb, rb), 6)
            if score >= threshold: out.append((left.claim_id, right.claim_id, score))
    return tuple(sorted(out, key=lambda x: (-x[2], x[0], x[1])))

def citation_cycles(nodes: Sequence[CitationNode]) -> tuple[tuple[str, ...], ...]:
    graph = {n.source_id: n.cites for n in nodes}; cycles = set()
    def canon(path):
        body = path[:-1]; rots = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        best = min(rots); return best + (best[0],)
    def walk(start, current, path, active):
        for nxt in graph.get(current, ()):
            if nxt not in graph: continue
            if nxt == start: cycles.add(canon(path + [start])); continue
            if nxt in active:
                j = path.index(nxt); cycles.add(canon(path[j:] + [nxt])); continue
            walk(start, nxt, path + [nxt], active | {nxt})
    for node in sorted(graph): walk(node, node, [node], {node})
    return tuple(sorted(cycles))

def version_findings(items: Sequence[VersionObservation]) -> tuple[Finding, ...]:
    grouped = {}; out = []
    for item in items:
        if len(item.semantic_sha256) != 64: raise ValueError("invalid semantic sha")
        int(item.semantic_sha256, 16)
        grouped.setdefault(item.object_id, []).append(item)
    for object_id, rows in sorted(grouped.items()):
        versions = {}
        for row in rows: versions.setdefault(row.version_id, set()).add(row.semantic_sha256)
        for version_id, hashes in sorted(versions.items()):
            if len(hashes) > 1: out.append(Finding("VERSION_IDENTITY_CONFLICT", (object_id, version_id)))
        if len(versions) > 1 and len({r.semantic_sha256 for r in rows}) > 1:
            out.append(Finding("VERSION_SEMANTIC_DRIFT_REVIEW", (object_id,)))
    return tuple(out)

def build_release_snapshot(claims: Sequence[SemanticClaim], snapshot_id: str) -> ReleaseSnapshot:
    hashes = tuple(sorted((c.claim_id, semantic_sha(c.text)) for c in claims))
    digest = sha256(json.dumps({"snapshot_id": snapshot_id, "claim_hashes": hashes, "authority": AUTHORITY_CEILING}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ReleaseSnapshot(snapshot_id, hashes, digest)

def compare_release_snapshot(snapshot: ReleaseSnapshot, current: Sequence[SemanticClaim]) -> tuple[Finding, ...]:
    old = dict(snapshot.claim_hashes); now = {c.claim_id: semantic_sha(c.text) for c in current}; out = []
    for claim_id, old_hash in sorted(old.items()):
        if claim_id not in now: out.append(Finding("POST_RELEASE_CLAIM_MISSING", (snapshot.snapshot_id, claim_id)))
        elif now[claim_id] != old_hash: out.append(Finding("POST_RELEASE_CLAIM_DRIFT", (snapshot.snapshot_id, claim_id)))
    return tuple(out)
