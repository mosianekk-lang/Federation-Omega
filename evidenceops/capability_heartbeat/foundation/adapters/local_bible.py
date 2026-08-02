"""Read Local Bible latest-transaction semantics without ingesting body content."""

from __future__ import annotations

import re
from pathlib import Path

from ..contracts import BlockerCode, CapabilityStatus
from ..errors import ContractError, PrivacyError
from ..privacy import require_code, strict_json_loads
from .common import Observation, make_observation, read_local_text, safe_root

LATEST = re.compile(r"(?im)^latest transaction:\s*`?(TXN-[A-Z0-9-]{3,60})`?\s*$")
TX_FILE = re.compile(r"transaction-(\d{4})\.json")


def read_local_bible(
    root: str | Path,
    *,
    node_id: str,
    owner_code: str,
    matter_code: str,
    observed_at: str,
) -> Observation:
    bible_root = safe_root(root)
    header = read_local_text(bible_root, "LOCAL_BIBLE.md")
    match = LATEST.search(header)
    if match is None:
        raise ContractError("LOCAL_BIBLE_LATEST_TRANSACTION_MISSING")
    latest_transaction = require_code(match.group(1), field="latest_transaction")
    candidates = sorted(
        path for path in bible_root.iterdir()
        if path.is_file() and not path.is_symlink() and TX_FILE.fullmatch(path.name)
    )
    if not candidates:
        raise ContractError("LOCAL_BIBLE_TRANSACTION_FILES_MISSING")
    latest_file = candidates[-1]
    if latest_file.stat().st_size > 1_048_576:
        raise ContractError("LOCAL_BIBLE_TRANSACTION_OVERSIZED")
    try:
        payload = strict_json_loads(
            latest_file.read_text(encoding="utf-8"),
            field="local_bible_transaction",
        )
    except PrivacyError as exc:
        raise ContractError("LOCAL_BIBLE_TRANSACTION_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ContractError("LOCAL_BIBLE_TRANSACTION_OBJECT_REQUIRED")
    actual = payload.get("transaction_id") or payload.get("transactionId")
    if actual != latest_transaction:
        raise ContractError("LOCAL_BIBLE_LATEST_TRANSACTION_SEMANTIC_DRIFT")
    return make_observation(
        source_code="LOCAL_BIBLE",
        node_id=node_id,
        owner_code=owner_code,
        matter_code=matter_code,
        capability_code="LOCAL_BIBLE_READBACK",
        status=CapabilityStatus.AVAILABLE,
        confidence_bp=9500,
        freshness_seconds=0,
        evidence_count=3,
        blocker_code=BlockerCode.NONE,
        observed_at=observed_at,
        semantic_value={
            "latest_transaction": latest_transaction,
            "transaction_sequence": int(TX_FILE.fullmatch(latest_file.name).group(1)),
            "semantic_alignment": True,
        },
    )
