from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from typing import Dict, List

SHIM_MAX_BYTES = 4096


@dataclass
class ChatGovernorShim:
    governor: str
    governor_version: str
    project_id: str
    mission_id: str
    objective: str
    capsule_pointer: str
    verified_source_pointers: List[str]
    active_specialists: List[str]
    active_connectors: List[str]
    next_proof_gate: str
    matter_wall: str

    def payload(self) -> Dict:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
        d["shim_sha256"] = hashlib.sha256(raw).hexdigest()
        if len(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()) > SHIM_MAX_BYTES:
            raise ValueError("Governor shim exceeds 4 KiB; use pointers instead of hydrated history")
        return d
