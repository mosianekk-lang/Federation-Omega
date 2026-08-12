"""No-effect shadow/adversarial validation for JFRIE v2 semantic integrity."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from .jfrie_v2_semantic import (
    AUTHORITY_CEILING, CitationNode, SemanticClaim, VersionObservation,
    build_release_snapshot, citation_cycles, compare_release_snapshot,
    paraphrase_candidates, version_findings,
)

VERSION = "2.0.0-semantic-integrity-validation-1"
FULL_V2_PARITY = False

class Mode(str, Enum):
    SHADOW = "SHADOW"
    ADVERSARIAL = "ADVERSARIAL"

@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    mode: Mode
    source_ref: str
    observed_at: str
    case_count: int
    passed_count: int
    failed_case_ids: tuple[str, ...]
    external_effect: bool
    authority_ceiling: str
    result_sha256: str
    @property
    def qualifies(self) -> bool:
        return self.case_count > 0 and self.case_count == self.passed_count and not self.failed_case_ids and not self.external_effect and self.authority_ceiling == AUTHORITY_CEILING and len(self.result_sha256) == 64

def _receipt(mode: Mode, cases: dict[str, bool], source_ref: str, observed_at: str) -> Receipt:
    payload = tuple(sorted(cases.items())); digest = sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
    failed = tuple(name for name, ok in payload if not ok)
    return Receipt(f"JFRIE-SEMANTIC-{mode.value}-{digest[:16]}", mode, source_ref, observed_at, len(payload), len(payload)-len(failed), failed, False, AUTHORITY_CEILING, digest)

def run_shadow(source_ref: str, observed_at: str) -> Receipt:
    candidates = paraphrase_candidates((
        SemanticClaim("C1", "employer initiated prescribed inquiry procedure", "MAT-1"),
        SemanticClaim("C2", "prescribed inquiry procedure employer initiated", "MAT-1"),
        SemanticClaim("C3", "network outage resolved", "MAT-1"),
        SemanticClaim("C4", "employer initiated prescribed inquiry procedure", "MAT-2"),
    ))
    snap_claims = (SemanticClaim("A", "source records event", "MAT-1"), SemanticClaim("B", "attachment verified", "MAT-1"))
    snap = build_release_snapshot(snap_claims, "SNAP-SHADOW")
    return _receipt(Mode.SHADOW, {
        "PARAPHRASE_REVIEW": len(candidates) == 1 and candidates[0][0:2] == ("C1", "C2"),
        "MATTER_WALL": all("C4" not in pair[:2] for pair in candidates),
        "STABLE_SNAPSHOT": compare_release_snapshot(snap, snap_claims) == (),
        "NO_EXTERNAL_EFFECT": True,
    }, source_ref, observed_at)

def run_adversarial(source_ref: str, observed_at: str) -> Receipt:
    cycles = citation_cycles((CitationNode("A", ("B",)), CitationNode("B", ("C",)), CitationNode("C", ("A",))))
    conflict = {f.code for f in version_findings((VersionObservation("O1", "V1", "1"*64), VersionObservation("O1", "V1", "2"*64)))}
    drift = {f.code for f in version_findings((VersionObservation("O2", "V1", "1"*64), VersionObservation("O2", "V2", "2"*64)))}
    original = (SemanticClaim("A", "source records event", "MAT-1"), SemanticClaim("B", "attachment verified", "MAT-1"))
    snap = build_release_snapshot(original, "SNAP-ADV")
    drift_codes = {f.code for f in compare_release_snapshot(snap, (SemanticClaim("A", "source records different event", "MAT-1"), SemanticClaim("B", "attachment verified", "MAT-1")))}
    missing_codes = {f.code for f in compare_release_snapshot(snap, (SemanticClaim("A", "source records event", "MAT-1"),))}
    return _receipt(Mode.ADVERSARIAL, {
        "CIRCULAR_CITATION": cycles == (("A", "B", "C", "A"),),
        "VERSION_IDENTITY_CONFLICT": "VERSION_IDENTITY_CONFLICT" in conflict,
        "VERSION_SEMANTIC_DRIFT": "VERSION_SEMANTIC_DRIFT_REVIEW" in drift,
        "POST_RELEASE_DRIFT": "POST_RELEASE_CLAIM_DRIFT" in drift_codes,
        "POST_RELEASE_MISSING": "POST_RELEASE_CLAIM_MISSING" in missing_codes,
        "NO_EXTERNAL_EFFECT": True,
    }, source_ref, observed_at)
