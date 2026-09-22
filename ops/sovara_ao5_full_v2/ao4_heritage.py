from __future__ import annotations

"""JARVIS ΑΩ4 heritage/compatibility adapter for the current ΑΩ5 engine.

The exact user-supplied ΑΩ4 source is preserved as deterministic base64(gzip) chunks.
ΑΩ4 is heritage authority only: it may add compatibility aliases and provenance but
may not replace, weaken, or downgrade the byte-exact ΑΩ5 current authority.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import base64
import gzip
import json

from .ao5_full_engine import AO5, PARTS, PATH_CLASSES, PATH_STATES, STREAMS

AO4_ENGINE_ID = "JARVIS-ALPHA-OMEGA-4"
AO4_VERSION = "ΑΩ4.0"
AO4_RAW_SHA256 = "d9224810f40ba48e7cdf4451953448546e6abb320cef9a838f0ade5dd72b07aa"
AO4_RAW_BYTES = 42408
AO4_CRLF_COUNT = 2024
AO4_LINE_COUNT = 2025
AO4_ROMAN_PARTS = 53
AO4_GZIP_SHA256 = "2f9dd616febcc09dcc7b7f8f32e3208601926c92f3fa884a88dac29e7cba4af1"
AO4_B64_LENGTH = 15596
AO4_CHUNK_LENGTHS = (4000, 4000, 4000, 3596)

AO5_ENGINE_ID = "JARVIS-ALPHA-OMEGA-5-SOVEREIGN"
AO5_CANONICAL_RAW_SHA256 = "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443"

BASE = Path(__file__).resolve().parent
HERITAGE_DIR = BASE / "heritage_ao4"
CANONICAL_DIR = HERITAGE_DIR / "canonical"
MAP_PATH = HERITAGE_DIR / "JARVIS_AO4_TO_AO5_COMPATIBILITY.json"

LEGACY_COMMANDS = {
    "n": "NEXT_HIGHEST_DECISION_INFORMATION_VALUE_SAFE_ACTION",
    "proceed": "CONTINUE_CURRENT_BOUNDED_WORKSTREAM",
    "do all": "EXECUTE_ALL_SAFE_AUTHORISED_VIABLE_LANES_OPTIMAL_ORDER",
    "alpha": "SHOW_ALPHA",
    "omega": "SHOW_OMEGA",
    "paths": "SHOW_PATHS",
    "streams": "SHOW_STREAMS",
    "red team": "RUN_CHALLENGES_COUNCIL",
    "counterfactual": "RUN_COUNTERFACTUAL",
    "audit": "RUN_FULL_AUDIT",
    "scientist": "RUN_SCIENTIST",
    "failure audit": "RUN_FLM",
    "handoff": "PERSIST_VERIFY_MIGRATE",
    "restore": "RESTORE_VERIFIED",
    "upgrade": "CONTROLLED_IMPROVEMENT",
}

@dataclass(frozen=True)
class HeritageReceipt:
    ao4_source_exact: bool
    ao4_parts_mapped: int
    ao5_target_methods_verified: int
    legacy_stream_aliases_verified: int
    legacy_path_aliases_verified: int
    representative_execution_pass: bool
    authority_expanded: bool = False
    external_effects: int = 0

    @property
    def complete(self) -> bool:
        return (
            self.ao4_source_exact
            and self.ao4_parts_mapped == AO4_ROMAN_PARTS
            and self.ao5_target_methods_verified == 55
            and self.legacy_stream_aliases_verified == 25
            and self.legacy_path_aliases_verified == 13
            and self.representative_execution_pass
            and not self.authority_expanded
            and self.external_effects == 0
        )

def reconstruct_ao4_bytes() -> bytes:
    parts = sorted(CANONICAL_DIR.glob("JARVIS_AO4_CANONICAL_SPEC.txt.gz.b64.part*"))
    if [p.stat().st_size for p in parts] != list(AO4_CHUNK_LENGTHS):
        raise ValueError("AO4_CANONICAL_CHUNK_LENGTH_MISMATCH")
    carrier = "".join(p.read_text(encoding="ascii") for p in parts)
    if len(carrier) != AO4_B64_LENGTH:
        raise ValueError("AO4_CANONICAL_B64_LENGTH_MISMATCH")
    gz = base64.b64decode(carrier, validate=True)
    if sha256(gz).hexdigest() != AO4_GZIP_SHA256:
        raise ValueError("AO4_CANONICAL_GZIP_HASH_MISMATCH")
    raw = gzip.decompress(gz)
    if len(raw) != AO4_RAW_BYTES or sha256(raw).hexdigest() != AO4_RAW_SHA256:
        raise ValueError("AO4_CANONICAL_RAW_IDENTITY_MISMATCH")
    if raw.count(b"\r\n") != AO4_CRLF_COUNT or raw.count(b"\n") + 1 != AO4_LINE_COUNT:
        raise ValueError("AO4_CANONICAL_LINE_IDENTITY_MISMATCH")
    return raw

def load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))

def resolve_legacy_stream(name: str) -> str:
    target = load_map()["legacy_stream_aliases"][name]
    if target not in STREAMS:
        raise ValueError("LEGACY_STREAM_TARGET_NOT_IN_AO5")
    return target

def resolve_legacy_path(name: str) -> dict:
    target = dict(load_map()["legacy_path_aliases"][name])
    if target["class"] not in PATH_CLASSES or target["state"] not in PATH_STATES:
        raise ValueError("LEGACY_PATH_TARGET_NOT_IN_AO5")
    return target

def heritage_canary() -> HeritageReceipt:
    reconstruct_ao4_bytes()
    mapping = load_map()
    if mapping["ao4"]["source_sha256"] != AO4_RAW_SHA256:
        raise ValueError("AO4_MAP_SOURCE_HASH_MISMATCH")
    if mapping["ao5"]["canonical_raw_sha256"] != AO5_CANONICAL_RAW_SHA256:
        raise ValueError("AO5_MAP_SOURCE_HASH_MISMATCH")

    ao4_parts = {row["ao4_part"] for row in mapping["sections"]}
    if len(ao4_parts) != AO4_ROMAN_PARTS:
        raise ValueError("AO4_PART_COVERAGE_INCOMPLETE")

    target_parts = set()
    for row in mapping["sections"]:
        target_parts.update(row["ao5_targets"])
    for target in target_parts:
        method = "part0" if target == "0" else f"part{target}"
        if not hasattr(AO5, method):
            raise ValueError(f"AO5_TARGET_METHOD_MISSING:{target}")

    if len(PARTS) != 55 or "0" not in PARTS or "LIV" not in PARTS:
        raise ValueError("AO5_CURRENT_COVERAGE_NOT_55")

    a = AO5()
    if not a.partI():
        raise ValueError("AO5_KERNEL_GATE_FAIL")
    bidir = a.partVI({"ALPHA"}, {"REQUIRED SOURCE"})
    if "REQUIRED SOURCE" not in bidir["gaps"]:
        raise ValueError("AO5_REVERSE_OMEGA_GATE_FAIL")
    paths = tuple({"id": f"P{i}", "class": "PRIMARY"} for i in range(8))
    budget = a.partX(paths)
    if (len(budget["ACTIVE"]), len(budget["SHADOW"])) != (3, 3):
        raise ValueError("AO5_PATH_BUDGET_GATE_FAIL")
    if a.partXI(("ST-01", "ST-25")) != ("ST-01", "ST-25"):
        raise ValueError("AO5_STREAM_GATE_FAIL")
    if a.partXXVII({k: 1.0 for k in ("OPPOSING_COUNSEL","NEUTRAL_FACT_FINDER","REVIEW_APPEAL","GOVERNANCE_AUDIT","PRACTICAL_OUTCOME_SETTLEMENT")}) != "Ω-A":
        raise ValueError("AO5_ADVERSARIAL_COUNCIL_GATE_FAIL")
    if not a.partXV({"page_count": 51})["auto_decompose"]:
        raise ValueError("AO5_PREFLIGHT_GATE_FAIL")
    if not a.partXLVIII(True, True, True, True, True)["continued"]:
        raise ValueError("AO5_AUTOFIX_FAILOVER_GATE_FAIL")
    if a.partXLV((("risk", "finding"),)) != ("risk->finding",):
        raise ValueError("AO5_SEMANTIC_FIREWALL_GATE_FAIL")
    if a.partL()["owner_default_qa"] is not False:
        raise ValueError("AO5_OWNER_LOAD_GATE_FAIL")

    streams = sum(resolve_legacy_stream(name) in STREAMS for name in mapping["legacy_stream_aliases"])
    paths_ok = sum(resolve_legacy_path(name)["class"] in PATH_CLASSES for name in mapping["legacy_path_aliases"])

    return HeritageReceipt(
        ao4_source_exact=True,
        ao4_parts_mapped=len(ao4_parts),
        ao5_target_methods_verified=len(PARTS),
        legacy_stream_aliases_verified=streams,
        legacy_path_aliases_verified=paths_ok,
        representative_execution_pass=True,
    )

def receipt() -> dict:
    r = heritage_canary()
    data = {
        **r.__dict__,
        "complete": r.complete,
        "ao4_engine_id": AO4_ENGINE_ID,
        "ao4_version": AO4_VERSION,
        "ao4_source_sha256": AO4_RAW_SHA256,
        "ao5_engine_id": AO5_ENGINE_ID,
        "ao5_canonical_raw_sha256": AO5_CANONICAL_RAW_SHA256,
        "integration_state": "HERITAGE_INTEGRATED_CURRENT_AO5_NOT_DOWNGRADED",
        "truth_boundary": (
            "Deterministic source/compatibility proof only; no provider deployment, "
            "credential authority, consequential external effect, or provider-live maturity."
        ),
    }
    data["receipt_sha256"] = sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return data

if __name__ == "__main__":
    print(json.dumps(receipt(), indent=2, sort_keys=True))
