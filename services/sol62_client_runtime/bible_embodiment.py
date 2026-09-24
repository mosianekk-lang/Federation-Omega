from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sol_61_runtime.sol_62_frontier_primitives import ConstraintError, digest
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime


SCHEMA = "SOL62_BIBLE_EMBODIMENT_FABRIC_V1"
SNAPSHOT_SCHEMA = "SOL62_BIBLE_SNAPSHOT_V1"
CAPSULE_SCHEMA = "SOL62_BIBLE_EMBODIMENT_CAPSULE_V1"
DEFAULT_CHUNK_CHARS = 12000

_ALWAYS_HYDRATE_SYSTEMS = {
    "FUSE Ω∞",
    "Federation Omega",
    "Human-First Ω",
    "FORMATION-OMEGA Unified Powerhouse",
    "Superior Logic Doctrine",
    "Strategic FUSE",
    "Strategic FUSE Commercial",
    "Kim Dataverse",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9_Ωω∞-]{3,}")


@dataclass(frozen=True, slots=True)
class BibleSnapshot:
    bible_id: str
    system: str
    source_ref: str
    title: str
    revision: str
    observed_at_epoch: int
    content_sha256: str
    char_count: int
    chunk_count: int
    domain_authority: str
    freshness: str
    text: str


def _stable_sha(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


def _chunks(text: str, size: int = DEFAULT_CHUNK_CHARS) -> tuple[str, ...]:
    if size < 1000:
        raise ValueError("CHUNK_SIZE_TOO_SMALL")
    return tuple(text[i : i + size] for i in range(0, len(text), size)) or ("",)


class BibleEstateManifest:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path(__file__).with_name("bible_estate_manifest.json"))
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))
        if self.payload.get("schema") != "SOL62_BIBLE_ESTATE_MANIFEST_V1":
            raise ValueError("BIBLE_MANIFEST_SCHEMA_INVALID")
        entries = self.payload.get("entries")
        if not isinstance(entries, list) or not entries:
            raise ValueError("BIBLE_MANIFEST_EMPTY")
        self.entries = tuple(dict(item) for item in entries)
        ids = [str(item.get("bible_id") or "") for item in self.entries]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("BIBLE_MANIFEST_ID_INVALID")

    def by_id(self, bible_id: str) -> Mapping[str, Any]:
        for item in self.entries:
            if item["bible_id"] == bible_id:
                return item
        raise KeyError(bible_id)

    def status(self) -> dict[str, Any]:
        return {
            "schema": self.payload["schema"],
            "entry_count": len(self.entries),
            "invariants": list(self.payload.get("invariants") or ()),
            "generated_from": dict(self.payload.get("generated_from") or {}),
        }


class BibleEmbodimentFabric:
    """Durable, provenance-preserving Bible embodiment over the SOL state root.

    The fabric inventories every registered Bible/system entry, stores full source
    snapshots by hash, and compiles small mission-specific capsules. It does not
    flatten domain authority or treat raw text as provider/effect authority.
    """

    def __init__(
        self,
        client: Sol62CompleteClientRuntime,
        *,
        manifest: BibleEstateManifest | None = None,
    ) -> None:
        self.client = client
        self.manifest = manifest or BibleEstateManifest()

    def register_manifest(self, *, observed_epoch: int | None = None) -> dict[str, Any]:
        now = int(time.time()) if observed_epoch is None else int(observed_epoch)
        for item in self.manifest.entries:
            body = {
                "schema": SCHEMA,
                "bible_id": item["bible_id"],
                "system": item.get("system", ""),
                "primary_title": item.get("primary_title", ""),
                "primary_ref": item.get("primary_ref", ""),
                "secondary_title": item.get("secondary_title", ""),
                "secondary_ref": item.get("secondary_ref", ""),
                "domain_authority": item.get("domain_authority", ""),
                "registry_state": item.get("registry_state", ""),
                "freshness": item.get("freshness", ""),
                "open_boundary": item.get("open_boundary", ""),
                "master_fabric_rule": item.get("master_fabric_rule", ""),
                "source_origin": item.get("source_origin", ""),
                "manifest_observed_epoch": now,
                "raw_text_is_authority": False,
                "maturity_inheritance": False,
            }
            self.client._put("sol62.bible.manifest", str(item["bible_id"]), body)
        receipt = {
            "schema": SCHEMA,
            "entry_count": len(self.manifest.entries),
            "observed_epoch": now,
            "manifest_sha256": digest(self.manifest.payload),
            "domain_authority_preserved": True,
            "raw_text_is_authority": False,
        }
        self.client.runtime.control.append_event(
            "SOL62-BIBLE-ESTATE",
            "SOL62_BIBLE_MANIFEST_REGISTERED",
            receipt,
        )
        return receipt

    def ingest_snapshot(
        self,
        *,
        bible_id: str,
        source_ref: str,
        title: str,
        text: str,
        revision: str = "",
        freshness: str = "PROVIDER_READBACK",
        observed_epoch: int | None = None,
    ) -> dict[str, Any]:
        entry = self.manifest.by_id(bible_id)
        if not isinstance(text, str) or not text.strip():
            raise ConstraintError("BIBLE_SNAPSHOT_TEXT_REQUIRED")
        if source_ref not in {str(entry.get("primary_ref") or ""), str(entry.get("secondary_ref") or "")}:
            raise ConstraintError("BIBLE_SOURCE_REF_NOT_REGISTERED")
        now = int(time.time()) if observed_epoch is None else int(observed_epoch)
        content_sha = _stable_sha(text)
        chunks = _chunks(text)
        snapshot_id = f"{bible_id}|{source_ref}"
        body = {
            "schema": SNAPSHOT_SCHEMA,
            "bible_id": bible_id,
            "system": entry.get("system", ""),
            "source_ref": source_ref,
            "title": title,
            "revision": revision,
            "observed_at_epoch": now,
            "content_sha256": content_sha,
            "char_count": len(text),
            "chunk_count": len(chunks),
            "domain_authority": entry.get("domain_authority", ""),
            "freshness": freshness,
            "text": text,
            "raw_text_is_authority": False,
            "maturity_inheritance": False,
        }
        stored = self.client._put("sol62.bible.snapshot", snapshot_id, body)
        for index, chunk in enumerate(chunks):
            self.client._put(
                "sol62.bible.chunk",
                f"{snapshot_id}|{index:05d}",
                {
                    "schema": "SOL62_BIBLE_CHUNK_V1",
                    "snapshot_id": snapshot_id,
                    "bible_id": bible_id,
                    "source_ref": source_ref,
                    "chunk_index": index,
                    "chunk_sha256": _stable_sha(chunk),
                    "text": chunk,
                },
            )
        self.client.runtime.control.append_event(
            bible_id,
            "SOL62_BIBLE_SNAPSHOT_INGESTED",
            {
                "source_ref": source_ref,
                "revision": revision,
                "content_sha256": content_sha,
                "char_count": len(text),
                "chunk_count": len(chunks),
                "freshness": freshness,
            },
        )
        return stored

    def snapshot_coverage(self) -> dict[str, Any]:
        manifest_rows = self.client._rows("sol62.bible.manifest")
        snapshot_rows = self.client._rows("sol62.bible.snapshot")
        snap_ids = {str(row["value"]["bible_id"]) for row in snapshot_rows}
        systems = {str(row["value"].get("system") or "") for row in manifest_rows}
        covered_systems = {
            str(row["value"].get("system") or "") for row in snapshot_rows
        }
        return {
            "schema": "SOL62_BIBLE_COVERAGE_V1",
            "manifest_entries": len(manifest_rows),
            "snapshot_entries": len(snapshot_rows),
            "bible_ids_with_snapshot": len(snap_ids),
            "systems_registered": len(systems),
            "systems_with_snapshot": len(covered_systems),
            "full_inventory_registered": len(manifest_rows) == len(self.manifest.entries),
            "all_registered_bibles_read": len(snap_ids) == len(self.manifest.entries),
            "truth_boundary": (
                "MANIFEST_REGISTERED_NE_SOURCE_READ; SOURCE_READ_NE_CURRENT_ON_USE; "
                "SOURCE_READ_NE_AUTHORITY_TRANSFER; CORPUS_AVAILABLE_NE_MISSION_RELEVANT"
            ),
        }

    def _score_entry(
        self,
        entry: Mapping[str, Any],
        *,
        objective_tokens: set[str],
        system_tokens: set[str],
    ) -> int:
        system = str(entry.get("system") or "")
        if system in _ALWAYS_HYDRATE_SYSTEMS:
            return 1000
        haystack = " ".join(
            str(entry.get(key) or "")
            for key in (
                "system",
                "primary_title",
                "secondary_title",
                "registry_state",
                "open_boundary",
                "master_fabric_rule",
            )
        )
        entry_tokens = _tokens(haystack)
        return 4 * len(objective_tokens & entry_tokens) + 2 * len(system_tokens & entry_tokens)

    def compile_capsule(
        self,
        *,
        mission_id: str,
        objective: str,
        requested_systems: Sequence[str] = (),
        max_bibles: int = 16,
        max_chars_per_bible: int = 5000,
    ) -> dict[str, Any]:
        if max_bibles < 1 or max_chars_per_bible < 500:
            raise ValueError("BIBLE_CAPSULE_LIMIT_INVALID")
        manifest_rows = [row["value"] for row in self.client._rows("sol62.bible.manifest")]
        if not manifest_rows:
            raise ConstraintError("BIBLE_MANIFEST_NOT_REGISTERED")
        snapshots = [row["value"] for row in self.client._rows("sol62.bible.snapshot")]
        snapshots_by_bible: dict[str, list[Mapping[str, Any]]] = {}
        for row in snapshots:
            snapshots_by_bible.setdefault(str(row["bible_id"]), []).append(row)

        objective_tokens = _tokens(objective)
        requested = {item.lower() for item in requested_systems}
        system_tokens = _tokens(" ".join(requested_systems))
        ranked = sorted(
            manifest_rows,
            key=lambda entry: (
                -(
                    self._score_entry(
                        entry,
                        objective_tokens=objective_tokens,
                        system_tokens=system_tokens,
                    )
                    + (500 if str(entry.get("system") or "").lower() in requested else 0)
                ),
                str(entry.get("bible_id")),
            ),
        )
        selected = ranked[:max_bibles]
        source_capsules: list[dict[str, Any]] = []
        missing: list[str] = []
        for entry in selected:
            bible_id = str(entry["bible_id"])
            candidates = sorted(
                snapshots_by_bible.get(bible_id, ()),
                key=lambda row: int(row.get("observed_at_epoch", 0)),
                reverse=True,
            )
            if not candidates:
                missing.append(bible_id)
                source_capsules.append(
                    {
                        "bible_id": bible_id,
                        "system": entry.get("system", ""),
                        "status": "SOURCE_READ_REQUIRED",
                        "domain_authority": entry.get("domain_authority", ""),
                        "registry_state": entry.get("registry_state", ""),
                        "open_boundary": entry.get("open_boundary", ""),
                    }
                )
                continue
            snapshot = candidates[0]
            source_capsules.append(
                {
                    "bible_id": bible_id,
                    "system": entry.get("system", ""),
                    "status": "HYDRATED",
                    "source_ref": snapshot.get("source_ref", ""),
                    "revision": snapshot.get("revision", ""),
                    "content_sha256": snapshot.get("content_sha256", ""),
                    "freshness": snapshot.get("freshness", ""),
                    "domain_authority": snapshot.get("domain_authority", ""),
                    "text_excerpt": str(snapshot.get("text", ""))[:max_chars_per_bible],
                    "full_text_persisted": True,
                }
            )
        capsule = {
            "schema": CAPSULE_SCHEMA,
            "mission_id": mission_id,
            "objective": objective,
            "requested_systems": list(requested_systems),
            "selected_bible_count": len(selected),
            "sources": source_capsules,
            "missing_source_reads": missing,
            "authority_rules": [
                "DOMAIN_AUTHORITY_PRESERVED",
                "FRESH_PROVIDER_SOURCE_OUTRANKS_SNAPSHOT",
                "RAW_TEXT_NE_EFFECT_AUTHORITY",
                "NO_MATURITY_INHERITANCE",
                "CONFLICT_RESOLUTION_BY_CANONICAL_DOMAIN_AUTHORITY_AND_CURRENTNESS_NOT_VOTE",
                "HUMAN_FIRST_PARENT_CONSTITUTION_PRESERVED",
                "FUSE_PARENT_COMPOSITION_DOES_NOT_ERASE_SPECIALIST_ORGANS",
            ],
            "embodiment_rule": (
                "FULL_CORPUS_PERSISTED; MISSION_CONTEXT_LAZY; SOURCE_PROVENANCE_REQUIRED; "
                "NO_PROMPT_FLATTENING; NO_AUTHORITY_TRANSFER"
            ),
        }
        capsule["capsule_sha256"] = digest(capsule)
        self.client._put("sol62.bible.capsule", mission_id, capsule)
        self.client.runtime.control.append_event(
            mission_id,
            "SOL62_BIBLE_EMBODIMENT_CAPSULE_COMPILED",
            {
                "capsule_sha256": capsule["capsule_sha256"],
                "selected_bible_count": len(selected),
                "missing_source_reads": len(missing),
            },
        )
        return capsule

    def embodiment_status(self) -> dict[str, Any]:
        coverage = self.snapshot_coverage()
        return {
            "schema": SCHEMA,
            "manifest": self.manifest.status(),
            "coverage": coverage,
            "full_corpus_available": bool(coverage["all_registered_bibles_read"]),
            "mission_hydration": "LAZY_RELEVANCE_WITH_MANDATORY_PARENT_CONSTITUTION",
            "authority_model": "DOMAIN_PRESERVING",
            "prompt_flattening": False,
            "provider_effect_authority_granted": False,
            "source_mutation_authority_granted": False,
        }
