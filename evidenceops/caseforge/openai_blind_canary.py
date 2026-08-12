from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .openai_provider_adapter import (
    OpenAIProviderBlindExperiment,
    OpenAIStoredResponseReadbackVerifier,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("blind benchmark file must contain one JSON object")
    return value


def _receipt_payload(receipt: Any) -> dict[str, Any]:
    execution = receipt.provider_execution
    blind_run = receipt.blind_run
    return {
        "schema": "CASEFORGE-OPENAI-BLIND-CANARY-2",
        "run_id": blind_run.run_id,
        "case_id": blind_run.case_id,
        "blind_input_sha256": blind_run.blind_input_sha256,
        "tested_output_sha256": blind_run.tested_output_sha256,
        "provider": execution.provider,
        "requested_model": execution.requested_model,
        "provider_response_model": execution.response_model,
        "provider_response_id": execution.response_id,
        "provider_status": execution.status,
        "provider_request_id": execution.request_id,
        "provider_output_sha256": execution.output_text_sha256,
        "provider_state": receipt.provider_state,
        "provider_readback_ref": receipt.provider_readback_ref,
        "provider_model_resource_version_ref": receipt.verified_model_version,
        "request_configuration_sha256": execution.configuration_sha256,
        "verified_configuration_sha256": receipt.verified_configuration_sha256,
        "store": execution.store,
        "authority_ceiling": receipt.authority_ceiling,
        "external_effect": receipt.external_effect,
        "scoring_state": "SEPARATE_HIDDEN_SCORER_REQUIRED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the tested-agent side of a CASEFORGE blind benchmark through an "
            "already-authorised OpenAI Responses client. This command never loads "
            "the hidden scoring/control pack."
        )
    )
    parser.add_argument("blind_pack", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default=os.getenv("CASEFORGE_OPENAI_MODEL", ""))
    parser.add_argument("--max-output-tokens", type=int, default=2400)
    parser.add_argument("--reasoning-effort", default="")
    parser.add_argument(
        "--provider-readback",
        action="store_true",
        help=(
            "Store this public/synthetic provider canary long enough to retrieve the "
            "Response and model resource for independent provider readback. Private "
            "or unclassified blind packs fail closed before invocation."
        ),
    )
    args = parser.parse_args()

    if not args.model.strip():
        raise SystemExit(
            "CASEFORGE_OPENAI_MODEL or --model is required; no model is assumed by source."
        )

    from openai import OpenAI

    options: dict[str, Any] = {"max_output_tokens": args.max_output_tokens}
    if args.reasoning_effort.strip():
        options["reasoning"] = {"effort": args.reasoning_effort.strip()}

    blind_payload = _load_json(args.blind_pack)
    client = OpenAI()
    verifier = (
        OpenAIStoredResponseReadbackVerifier(client=client)
        if args.provider_readback
        else None
    )
    receipt = OpenAIProviderBlindExperiment().run(
        run_id=args.run_id,
        blind_payload=blind_payload,
        client=client,
        model=args.model,
        request_options=options,
        store=bool(args.provider_readback),
        readback_verifier=verifier,
    )
    print(json.dumps(_receipt_payload(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
