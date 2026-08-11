from __future__ import annotations

from collections import defaultdict
from typing import Any


class Mnemosyne:
    name = "MNEMOSYNE"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        events = list(context.get("memory_events", []))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            grouped[str(event.get("signature", event.get("kind", "UNKNOWN")))].append(event)
        consolidated, antibodies, archive = [], [], []
        for signature, rows in sorted(grouped.items()):
            latest = rows[-1]
            failures = [r for r in rows if r.get("outcome") == "FAILURE"]
            record = {
                "signature": signature,
                "occurrences": len(rows),
                "latest": latest.get("lesson"),
                "state": "ACTIVE" if latest.get("reliable", True) else "NON_RELIABLE",
            }
            consolidated.append(record)
            if len(failures) >= 2:
                antibodies.append({
                    "signature": signature,
                    "detection_rule": f"BLOCK_REPEAT:{signature}",
                    "regression_test": f"TEST:{signature}",
                    "repair_playbook": latest.get("repair", "REQUIRE_READBACK"),
                })
            archive.extend(r for r in rows[:-1] if r.get("superseded") or len(rows) > 1)
        return {
            "system": self.name,
            "consolidated": consolidated,
            "cognitive_antibodies": antibodies,
            "archived_episode_count": len(archive),
            "constitutional_memory_modified": False,
        }


class Morphos:
    name = "MORPHOS"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        genome = context.get("mission_genome", {})
        required = set(genome.get("required_organs", []))
        optional = set(genome.get("optional_organs", []))
        present = set(context.get("present_organs", []))
        signals = set(context.get("environment_signals", []))
        signal_map = genome.get("signal_to_organ", {})
        required |= {signal_map[s] for s in signals if s in signal_map}
        grow = sorted(required - present)
        repair = sorted(x for x in required & present if x in set(context.get("unhealthy_organs", [])))
        prune = sorted(x for x in optional & present if x not in set(context.get("used_organs", [])))
        final = (present | set(grow)) - set(prune)
        mature = required.issubset(final) and not repair
        return {
            "system": self.name,
            "grow": grow,
            "repair": repair,
            "prune": prune,
            "final_organs": sorted(final),
            "maturity": "HOMEOSTATIC" if mature else "DEVELOPING",
            "identity_preserved": True,
            "authority_expanded": False,
        }
