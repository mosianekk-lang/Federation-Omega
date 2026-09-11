from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionLocus(str, Enum):
    CLIENT = "client"
    SERVER = "server"
    SELF_HOSTED = "self_hosted"


class Effort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


@dataclass(frozen=True)
class ToolSurface:
    name: str
    locus: ExecutionLocus
    native_schema: bool = False
    deferred: bool = False
    programmatic_callable: bool = False
    untrusted_output: bool = True


class ToolLocusRouter:
    @staticmethod
    def select(*, web_only: bool, desktop_required: bool, sensitive_data: bool) -> str:
        if desktop_required:
            return "computer_toolset"
        if web_only:
            return "browser_toolset"
        if sensitive_data:
            return "self_hosted_tool_runtime"
        return "typed_tool_runtime"


@dataclass(frozen=True)
class AdvisorDecision:
    use_advisor: bool
    reason: str
    max_uses: int


class AdvisorPolicy:
    @staticmethod
    def decide(*, complexity: float, uncertainty: float, failure_cost: float,
               executor_quality: float, cost_pressure: float = 0.0) -> AdvisorDecision:
        vals = (complexity, uncertainty, failure_cost, executor_quality, cost_pressure)
        if any(v < 0 or v > 1 for v in vals):
            raise ValueError("all scores must be in [0,1]")
        need = 0.35 * complexity + 0.30 * uncertainty + 0.25 * failure_cost + 0.10 * (1 - executor_quality)
        need -= 0.20 * cost_pressure
        if need >= 0.72:
            return AdvisorDecision(True, "high marginal value from independent higher-tier advice", 2)
        if need >= 0.55:
            return AdvisorDecision(True, "bounded advisor consultation", 1)
        return AdvisorDecision(False, "executor sufficient for current evidence/risk", 0)


class EffortGovernor:
    @staticmethod
    def choose(*, difficulty: float, uncertainty: float, long_horizon: bool,
               failure_cost: float, cost_pressure: float = 0.0) -> Effort:
        vals = (difficulty, uncertainty, failure_cost, cost_pressure)
        if any(v < 0 or v > 1 for v in vals):
            raise ValueError("all scores must be in [0,1]")
        score = 0.42*difficulty + 0.28*uncertainty + 0.30*failure_cost - 0.22*cost_pressure
        if long_horizon:
            score += 0.12
        if score >= 0.88:
            return Effort.MAX
        if score >= 0.72:
            return Effort.XHIGH
        if score >= 0.50:
            return Effort.HIGH
        if score >= 0.28:
            return Effort.MEDIUM
        return Effort.LOW


@dataclass(frozen=True)
class SandboxPlan:
    mode: str
    network_policy: str
    filesystem_policy: str
    secrets_policy: str


class SandboxPlanner:
    @staticmethod
    def plan(*, sensitive_data: bool, internal_network_required: bool,
             write_required: bool) -> SandboxPlan:
        if sensitive_data or internal_network_required:
            return SandboxPlan(
                mode="self_hosted",
                network_policy="explicit_allowlist",
                filesystem_policy="bounded_rw" if write_required else "readonly",
                secrets_policy="short_lived_brokered",
            )
        return SandboxPlan(
            mode="cloud_or_hosted",
            network_policy="provider_default_plus_allowlist",
            filesystem_policy="ephemeral_rw" if write_required else "readonly",
            secrets_policy="scoped_session_only",
        )
