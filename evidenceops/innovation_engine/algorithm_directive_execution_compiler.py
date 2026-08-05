from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class DirectiveExecutionCompiler:
    algorithm_id = "ALG-EOPS-DEC-001"
    name = "Directive Execution Compiler"

    _verb_contracts: Mapping[str, Mapping[str, Any]] = {
        "send": {"effect": "EXTERNAL_COMMUNICATION", "authority": "OWNER_RESERVED"},
        "email": {"effect": "EXTERNAL_COMMUNICATION", "authority": "OWNER_RESERVED"},
        "file": {"effect": "LEGAL_OR_PROVIDER_FILING", "authority": "OWNER_RESERVED"},
        "publish": {"effect": "PUBLIC_RELEASE", "authority": "OWNER_RESERVED"},
        "pay": {"effect": "FINANCIAL_EFFECT", "authority": "OWNER_RESERVED"},
        "delete": {"effect": "DESTRUCTIVE_EFFECT", "authority": "OWNER_RESERVED"},
        "deploy": {"effect": "MATERIAL_DEPLOYMENT", "authority": "CONTEXT_DEPENDENT"},
        "create": {"effect": "ARTEFACT_CREATION", "authority": "A1_INTERNAL"},
        "build": {"effect": "INTERNAL_BUILD", "authority": "A1_INTERNAL"},
        "implement": {"effect": "INTERNAL_IMPLEMENTATION", "authority": "A1_INTERNAL"},
        "update": {"effect": "TARGET_MUTATION", "authority": "CONTEXT_DEPENDENT"},
        "verify": {"effect": "READBACK", "authority": "A0_READ"},
        "audit": {"effect": "ANALYSIS", "authority": "A0_READ"},
        "analyse": {"effect": "ANALYSIS", "authority": "A0_READ"},
        "analyze": {"effect": "ANALYSIS", "authority": "A0_READ"},
        "draft": {"effect": "ARTEFACT_CREATION", "authority": "A1_INTERNAL"},
        "activate": {"effect": "STATE_CHANGE", "authority": "CONTEXT_DEPENDENT"},
        "run": {"effect": "EXECUTION", "authority": "CONTEXT_DEPENDENT"},
    }

    _artefact_terms = (
        "algorithm", "code", "email", "letter", "report", "register", "workflow",
        "system", "document", "spreadsheet", "bundle", "policy", "application",
        "draft", "analysis", "matrix", "roadmap", "script", "service",
    )

    def run(
        self,
        directive: str,
        *,
        available_routes: Sequence[Mapping[str, Any]] = (),
        current_authority: str = AUTHORITY_CEILING,
    ) -> AlgorithmResult:
        normalized = text(directive)
        lowered = normalized.lower()
        verbs = [
            verb
            for verb in self._verb_contracts
            if re.search(rf"\b{re.escape(verb)}(?:s|ed|ing)?\b", lowered)
        ]
        artefacts = [term for term in self._artefact_terms if term in lowered]
        contracts = [dict(verb=verb, **self._verb_contracts[verb]) for verb in verbs]
        owner_reserved = [row for row in contracts if row["authority"] == "OWNER_RESERVED"]
        context_dependent = [row for row in contracts if row["authority"] == "CONTEXT_DEPENDENT"]

        route_actions = {
            str(route.get("action", "")).lower(): route
            for route in available_routes
            if route.get("available") is True
        }
        matched_routes = []
        for verb in verbs:
            for action, route in route_actions.items():
                if verb in action or action in verb:
                    matched_routes.append(dict(route))
        matched_routes = sorted(matched_routes, key=lambda item: text(item.get("route_id")))

        requires_execution = any(
            row["effect"] not in {"ANALYSIS", "ARTEFACT_CREATION", "READBACK"}
            for row in contracts
        )
        violations: list[str] = []
        if not verbs:
            violations.append("NO_OPERATIONAL_VERB_IDENTIFIED")
        if requires_execution and not matched_routes:
            violations.append("EXECUTION_ROUTE_NOT_ESTABLISHED")
        if owner_reserved and current_authority != "OWNER_EXPLICIT":
            violations.append("OWNER_RESERVED_ACTION_NOT_AUTHORISED")

        execution_state = "INTERNAL_CONTRACT_READY"
        if owner_reserved and current_authority != "OWNER_EXPLICIT":
            execution_state = "OWNER_APPROVAL_REQUIRED"
        elif requires_execution and not matched_routes:
            execution_state = "BLOCKED_WITH_ROUTE_DISCOVERY_REQUIRED"
        elif requires_execution:
            execution_state = "AUTHORISED_ROUTE_READY_FOR_SEPARATE_EXECUTION"

        output = {
            "directive": normalized,
            "intended_outcome": normalized,
            "operational_verbs": verbs,
            "artefacts": artefacts,
            "verb_contracts": contracts,
            "execution_required": requires_execution,
            "matched_routes": matched_routes,
            "authority_state": execution_state,
            "verification_contract": [
                "execution receipt for the exact action",
                "target identity and state readback",
                "semantic comparison of requested and actual result",
                "accurate maturity and residual-gap report",
            ],
            "completion_rule": (
                "COMPLETE only when intended outcome, artefact, execution, "
                "verification and target-state readback all agree"
            ),
            "artifact_only_completion_permitted": False,
            "context_dependent_actions": context_dependent,
        }
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=execution_state,
            maturity="TESTED_LOCAL",
            output=output,
            violations=tuple(violations),
            metrics={
                "verb_count": float(len(verbs)),
                "route_match_count": float(len(matched_routes)),
                "intent_fidelity": 1.0 if verbs else 0.0,
            },
        )
