from __future__ import annotations

from typing import Any, Mapping, Sequence

from .algorithms import sha256, text


TERMINAL_STATES = {
    "EXTRACTED_VERIFIED",
    "DUPLICATE_CANONICAL_LINKED",
    "SUPERSEDED_BY_STRONGER_SOURCE",
    "IRRELEVANT_REASONED",
    "RESTRICTED_CONTROLLED",
    "TECHNICALLY_UNREADABLE_AFTER_EXHAUSTED_RECOVERY",
    "EXTERNALLY_UNAVAILABLE_AFTER_PROVED_SEARCH_REQUEST_AND_NON_PRODUCTION",
    "OWNER_DECISION_REQUIRED",
}


class IndependentEvidenceOpsReferenceReplica:
    """Small independent implementation for R3-style replication checks.

    This intentionally does not import the canonical finality or opportunity
    algorithms. It independently computes a conservative release decision and
    a compact opportunity frontier from a read-only EvidenceOps packet. It is
    not an alternative production foundry and cannot transfer trust.
    """

    replica_id = "EVIDENCEOPS-REFERENCE-REPLICA-V1"

    @staticmethod
    def _rows(packet: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
        value = packet.get(key)
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    @staticmethod
    def _source_state(source: Mapping[str, Any]) -> str:
        for key in (
            "terminal_state",
            "extraction_state",
            "finality_state",
            "state",
            "status",
        ):
            value = text(source.get(key)).upper()
            if value:
                return value
        return "PENDING"

    def run(
        self,
        *,
        packet: Mapping[str, Any],
        lesson_signals: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for index, source in enumerate(self._rows(packet, "sources"), start=1):
            item_id = text(source.get("source_id")) or f"SRC-{index:04d}"
            state = self._source_state(source)
            items.append(
                {
                    "item_id": item_id,
                    "state": state,
                    "terminal": state in TERMINAL_STATES,
                }
            )
        for index, record in enumerate(
            self._rows(packet, "missing_records"), start=1
        ):
            item_id = (
                text(record.get("record_id"))
                or text(record.get("missing_record_id"))
                or f"MR-{index:04d}"
            )
            items.append(
                {
                    "item_id": item_id,
                    "state": "PENDING",
                    "terminal": False,
                }
            )

        release_allowed = bool(items) and all(item["terminal"] for item in items)
        opportunities: list[dict[str, Any]] = []
        if self._rows(packet, "missing_records"):
            opportunities.extend(
                [
                    {
                        "proposed_algorithm": "ALG-EOPS-UFP-001",
                        "reason": "missing records require governed unknown prioritisation",
                    },
                    {
                        "proposed_algorithm": "ALG-EOPS-TFR-001",
                        "reason": "missing records require terminal resolution",
                    },
                    {
                        "proposed_algorithm": "ALG-EOPS-EDP-001",
                        "reason": "missing records create weak-evidence debt",
                    },
                ]
            )
        if self._rows(packet, "contradictions"):
            opportunities.append(
                {
                    "proposed_algorithm": "ALG-EOPS-CPDG-001",
                    "reason": "contradictions require claim-proof distance control",
                }
            )
        if lesson_signals:
            opportunities.append(
                {
                    "proposed_algorithm": "ALG-EOPS-AOM-001",
                    "reason": "source-backed lessons require opportunity mining",
                }
            )

        event = {
            "replica_id": self.replica_id,
            "packet_sha256": sha256(packet),
            "item_count": len(items),
            "release_allowed": release_allowed,
            "opportunities": opportunities,
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        }
        ledger_head = sha256(event)
        result = {
            "schema": "EVIDENCEOPS_INDEPENDENT_REFERENCE_REPLICA_V1",
            "replica_id": self.replica_id,
            "terminal_finality": {
                "item_count": len(items),
                "terminal_count": sum(item["terminal"] for item in items),
                "release_allowed": release_allowed,
                "items": items,
            },
            "opportunity_frontier": opportunities,
            "learning_verification": {
                "status": "PASSED" if sha256(event) == ledger_head else "FAILED",
                "ledger_head_hash": ledger_head,
            },
            "source_packet_sha256": sha256(packet),
            "source_write": False,
            "verified_fact_write": False,
            "case_wall_crossing": False,
            "external_effect": False,
            "authority_ceiling": "A1_INTERNAL",
            "trust_transfer": False,
        }
        result["result_hash"] = sha256(result)
        return result
