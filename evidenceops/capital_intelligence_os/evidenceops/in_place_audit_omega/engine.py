from __future__ import annotations
import hashlib, json, time, uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Set, Tuple

@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    source_id: str
    record_type: str
    timestamp: Optional[str]
    content: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Finding:
    finding_id: str
    control_id: str
    record_ids: List[str]
    title: str
    severity: str
    confidence: float
    status: str
    rationale: str
    evidence_hashes: List[str]
    impact_entities: List[str] = field(default_factory=list)
    remediation: List[str] = field(default_factory=list)

@dataclass
class AuditReceipt:
    audit_id: str
    source_id: str
    records_seen: int
    records_selected: int
    findings_count: int
    merkle_root: str
    state_hash: str
    maturity: str
    output_path: str

class SourceAdapter(Protocol):
    source_id: str
    def iter_records(self) -> Iterable[EvidenceRecord]: ...

def stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def merkle_root(hashes: List[str]) -> str:
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256((level[i] + level[i + 1]).encode()).hexdigest() for i in range(0, len(level), 2)]
    return level[0]

def risk_score(record: EvidenceRecord) -> float:
    score = 0.05
    text = " ".join(f"{k}={v}" for k, v in record.content.items()).lower()
    if any(k in text for k in ("password", "secret", "token", "api_key", "private_key")):
        score += 0.45
    if record.metadata.get("privileged") is True:
        score += 0.20
    if record.metadata.get("external") is True:
        score += 0.10
    if not record.timestamp:
        score += 0.05
    if record.content.get("status") in {"failed", "error", "rejected", "blocked"}:
        score += 0.20
    return min(score, 1.0)

class EvidenceGraph:
    def __init__(self):
        self.records: Dict[str, EvidenceRecord] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.reverse: Dict[str, Set[str]] = defaultdict(set)

    def add(self, record: EvidenceRecord):
        self.records[record.record_id] = record
        for ref in record.metadata.get("references", []) or []:
            ref = str(ref)
            self.edges[record.record_id].add(ref)
            self.reverse[ref].add(record.record_id)

    def orphans(self):
        return sorted((src, dst) for src, targets in self.edges.items() for dst in targets if dst not in self.records)

    def impact_closure(self, seeds: Iterable[str], max_depth: int = 5):
        seen = set(seeds)
        q = deque((s, 0) for s in seeds)
        while q:
            node, depth = q.popleft()
            if depth >= max_depth:
                continue
            for nxt in self.reverse.get(node, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append((nxt, depth + 1))
        return sorted(seen)

class InPlaceAuditOmega:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, adapter: SourceAdapter, audit_id: str, max_records: int = 1000, risk_threshold: float = 0.0) -> AuditReceipt:
        records = list(adapter.iter_records())
        ranked = sorted(((r, risk_score(r)) for r in records), key=lambda x: x[1], reverse=True)
        selected = [r for r, score in ranked[:max_records] if score >= risk_threshold]
        graph = EvidenceGraph()
        for record in records:
            graph.add(record)

        findings: List[Finding] = []
        claims: Dict[Tuple[str, str], List[Tuple[EvidenceRecord, Any]]] = defaultdict(list)
        for r in selected:
            evidence_hash = stable_hash({"content": r.content, "metadata": r.metadata})
            if r.metadata.get("approved") is False and r.content.get("status") == "executed":
                findings.append(Finding(f"F-{uuid.uuid4().hex[:12]}", "CTRL-AUTH-001", [r.record_id], "Execution without approval", "critical", 0.99, "OPEN", "Execution occurred although approval is false.", [evidence_hash], remediation=["Quarantine action", "Verify authority", "Inspect downstream effects"]))
            if r.content.get("status") == "complete" and not r.metadata.get("readback_receipt"):
                findings.append(Finding(f"F-{uuid.uuid4().hex[:12]}", "CTRL-PROOF-001", [r.record_id], "Completion without readback", "high", 0.98, "OPEN", "Completion is claimed without readback proof.", [evidence_hash], remediation=["Downgrade maturity", "Read back target", "Issue receipt"]))
            if {"password", "secret", "token", "api_key"} & {str(k).lower() for k in r.content}:
                findings.append(Finding(f"F-{uuid.uuid4().hex[:12]}", "CTRL-SECRET-001", [r.record_id], "Potential secret exposure", "critical", 0.95, "OPEN", "Credential-like field exists in source content.", [evidence_hash], remediation=["Move secret to vault", "Rotate credential", "Redact source"]))
            if r.content.get("subject") and r.content.get("predicate") and "value" in r.content:
                claims[(str(r.content["subject"]), str(r.content["predicate"]))].append((r, r.content["value"]))

        for (subject, predicate), items in claims.items():
            values = {json.dumps(v, sort_keys=True, default=str) for _, v in items}
            if len(values) > 1:
                findings.append(Finding(f"F-{uuid.uuid4().hex[:12]}", "CTRL-CONTRA-001", [r.record_id for r, _ in items], "Contradictory claims", "high", 0.90, "OPEN", f"Conflicting values exist for {subject}.{predicate}.", [stable_hash(r.content) for r, _ in items], remediation=["Resolve source authority", "Preserve both claims", "Create contradiction register"]))

        for src, missing in graph.orphans():
            findings.append(Finding(f"F-{uuid.uuid4().hex[:12]}", "CTRL-GRAPH-001", [src], "Broken evidence reference", "high", 0.99, "OPEN", f"{src} references missing record {missing}.", [stable_hash(graph.records[src].content)], remediation=["Restore record", "Correct reference", "Record provenance break"]))

        for finding in findings:
            finding.impact_entities = graph.impact_closure(finding.record_ids)

        record_hashes = [stable_hash({"id": r.record_id, "content": r.content, "metadata": r.metadata}) for r in selected]
        finding_hashes = [stable_hash(asdict(f)) for f in findings]
        root = merkle_root(record_hashes + finding_hashes)
        payload = {
            "audit_id": audit_id,
            "source_id": adapter.source_id,
            "records_seen": len(records),
            "records_selected": len(selected),
            "findings": [asdict(f) for f in findings],
            "merkle_root": root,
            "source_data_moved": False,
            "proof_model": "DERIVED_FINDINGS_AND_HASHES_ONLY",
        }
        path = self.output_dir / f"{audit_id}.json"
        serialised = json.dumps(payload, indent=2, sort_keys=True)
        path.write_text(serialised, encoding="utf-8")
        return AuditReceipt(audit_id, adapter.source_id, len(records), len(selected), len(findings), root, hashlib.sha256(serialised.encode()).hexdigest(), "LOCALLY_EXECUTED_AND_PROOF_BUNDLED", str(path))
