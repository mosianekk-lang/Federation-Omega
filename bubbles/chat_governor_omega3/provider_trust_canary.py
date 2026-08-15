from __future__ import annotations

"""Bounded receiving-home canary for ChatGov Provider Trust.

Consumes a redacted, hash-bound Federation Provider Trust resolution produced by
an already admitted provider-live lane. The canary does not call a provider,
carry credentials, or grant consequential authority. It proves that ChatGov can
reuse the shared provider trust receipt at PRE_USER_PROMPT, persist/read back its
local checkpoint, and suppress an avoidable owner prompt when the provider
runtime is already proven ready.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .provider_trust import ChatGovProviderTrustInterlock
from .state import DurableState


SCHEMA = "CHATGOV-PROVIDER-TRUST-LIVE-CANARY-1"
MISSION_ID = "aaa-chatgov-provider-trust-live-canary"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def run_canary(*, resolution_path: Path, db_path: Path) -> dict[str, Any]:
    resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
    state = DurableState(str(db_path))
    result = ChatGovProviderTrustInterlock(state).before_user_prompt(
        MISSION_ID,
        resolution,
    )
    checkpoint = state.latest_checkpoint(MISSION_ID)

    checkpoint_matches = bool(
        checkpoint
        and checkpoint.get("checkpoint_id") == result.checkpoint_id
        and checkpoint.get("payload", {}).get("event") == "PROVIDER_TRUST_RECONCILED"
        and checkpoint.get("payload", {}).get("trigger") == "PRE_USER_PROMPT"
        and checkpoint.get("payload", {}).get("trust_receipt_sha256")
        == result.checkpoint_id * 0 + resolution.get("receipt_sha256")
    )

    # The expression above deliberately avoids copying any credential-like
    # material. Normalize it to the simple semantic comparison for the receipt.
    checkpoint_matches = bool(
        checkpoint
        and checkpoint.get("checkpoint_id") == result.checkpoint_id
        and checkpoint.get("payload", {}).get("event") == "PROVIDER_TRUST_RECONCILED"
        and checkpoint.get("payload", {}).get("trigger") == "PRE_USER_PROMPT"
        and checkpoint.get("payload", {}).get("trust_receipt_sha256")
        == resolution.get("receipt_sha256")
    )

    verified = all(
        (
            result.provider_runtime_ready is True,
            result.should_prompt_owner is False,
            result.system_action_available is True,
            result.consequential_authority_granted is False,
            result.proof_bearing is True,
            checkpoint_matches,
        )
    )

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "mission_id": MISSION_ID,
        "capability_alias": result.capability_alias,
        "provider_trust_state": result.state,
        "provider_runtime_ready": result.provider_runtime_ready,
        "pre_user_prompt_reconciled": True,
        "owner_prompt_suppressed": result.should_prompt_owner is False,
        "system_action_available": result.system_action_available,
        "next_action": result.next_action,
        "credential_rotation_recommended": result.credential_rotation_recommended,
        "consequential_authority_granted": result.consequential_authority_granted,
        "proof_bearing": result.proof_bearing,
        "checkpoint_id": result.checkpoint_id,
        "checkpoint_readback_verified": checkpoint_matches,
        "provider_trust_receipt_sha256": resolution.get("receipt_sha256"),
        "provider_call_attempted": False,
        "secret_values_recorded": False,
        "state": "CHATGOV_PROVIDER_TRUST_RECEIVING_HOME_VERIFIED" if verified else "CHATGOV_PROVIDER_TRUST_RECEIVING_HOME_FAILED",
        "truth_boundary": (
            "This receipt proves ChatGov consumed the shared hash-bound provider-trust "
            "resolution at PRE_USER_PROMPT and persisted/read back its local checkpoint. "
            "It does not prove a separate ChatGov provider call, evidence truth, mutation "
            "authority, or consequential external authority."
        ),
    }
    unsigned = dict(receipt)
    receipt["receipt_sha256"] = _canonical_sha256(unsigned)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = run_canary(
        resolution_path=Path(args.resolution),
        db_path=Path(args.db),
    )
    Path(args.output).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(receipt["state"])
    return 0 if receipt["state"] == "CHATGOV_PROVIDER_TRUST_RECEIVING_HOME_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
