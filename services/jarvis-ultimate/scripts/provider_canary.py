#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from jarvis.core import semantic_fingerprint
from jarvis.graph import semantic_response_valid
from jarvis.providers import ProviderError, ProviderSettings, select_reasoner


def main() -> int:
    try:
        settings = ProviderSettings.from_env()
        if settings.mode == "offline":
            raise ProviderError("LIVE_PROVIDER_REQUIRED")
        reasoner = select_reasoner(settings)
        context = {"capabilities": [], "principles": []}
        prompt = "Return a concise canary stating the selected provider mode, without claiming tools or external access."
        first = reasoner.respond(prompt, context)
        second = reasoner.respond(prompt, context)
        stable_identity = (
            first.provider,
            first.model,
            first.api_version,
        ) == (
            second.provider,
            second.model,
            second.api_version,
        )
        semantic = semantic_response_valid(first) and semantic_response_valid(second)
        if not stable_identity or not semantic:
            raise ProviderError("TWO_PASS_SEMANTIC_CANARY_FAILED")
        evidence = {
            "provider": first.provider,
            "model": first.model,
            "apiVersion": first.api_version,
            "passCount": 2,
            "responseHashes": [
                semantic_fingerprint({"text": first.text}),
                semantic_fingerprint({"text": second.text}),
            ],
        }
        print(json.dumps({"status": "VERIFIED_SESSION_SEMANTIC", **evidence, "evidenceHash": semantic_fingerprint(evidence)}, sort_keys=True))
        return 0
    except ProviderError as exc:
        print(json.dumps({"status": "NO_GO", "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
