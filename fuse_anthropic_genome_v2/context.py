from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ContextPlan:
    actions: Tuple[str, ...]


class ContextPressureController:
    """Compose context controls by the source of pressure, not one universal tactic."""
    @staticmethod
    def plan(*, tool_count: int, tool_result_tokens: int,
             conversation_tokens: int, stable_toolset: bool,
             repetitive_fanout: bool, memory_available: bool) -> ContextPlan:
        if min(tool_count, tool_result_tokens, conversation_tokens) < 0:
            raise ValueError("counts must be nonnegative")
        actions = []
        if stable_toolset and tool_count > 0:
            actions.append("PROMPT_CACHE")
        if tool_count >= 20:
            actions.append("TOOL_SEARCH")
        if repetitive_fanout:
            actions.append("PROGRAMMATIC_TOOL_CALLING")
        if tool_result_tokens >= 20000:
            actions.append("CLEAR_STALE_TOOL_RESULTS")
        if conversation_tokens >= 100000:
            actions.append("SERVER_COMPACTION")
            if memory_available:
                actions.insert(0, "MEMORY_OFFLOAD_BEFORE_COMPACTION")
        return ContextPlan(tuple(dict.fromkeys(actions)))
