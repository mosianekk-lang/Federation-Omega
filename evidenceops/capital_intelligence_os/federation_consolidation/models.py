from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class Authority(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"

@dataclass(frozen=True)
class ConsolidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: dict[str, Any]
