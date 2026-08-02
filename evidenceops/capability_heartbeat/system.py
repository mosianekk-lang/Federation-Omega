from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authority import VerifiedV4Authority
from .engine import CapabilityHeartbeatEngine, HeartbeatError, SAFE_ID, canonical_json, sha256_value
from .foundation.contracts import HeartbeatEnvelope, Receipt, canonicalize, digest
from .foundation.errors import ReplayError
from .foundation.privacy import strict_json_loads

PRIVACY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
LIVE_STATES = {"LIVE_BIDIRECTIONAL_VERIFIED"}
ACCEPTED_INGRESS_STATES = {"TURN_TRANSACTION_VERIFIED_LOCAL"}


def parse_timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HeartbeatError("invalid heartbeat-system timestamp") from exc
    if result.tzinfo is None:
        raise HeartbeatError("heartbeat-system timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def text_ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class EvidenceOpsHeartbeatSystem:
    """Transactional surface, turn, response and adapter-remediation control plane."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        repository_root: str | Path | None = None,
        capability_registry: str = "evidenceops/capability_heartbeat/sources.json",
        authority: VerifiedV4Authority | None = None,
    ):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.authority = authority
        self.capability_engine = None
        if repository_root:
            self.capability_engine = CapabilityHeartbeatEngine(
                repository_root, capability_registry, bible_node_path=None, authority=authority
            )
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS surfaces(
                  surface_id TEXT PRIMARY KEY, node_id TEXT UNIQUE NOT NULL,
                  title TEXT NOT NULL, kind TEXT NOT NULL, privacy_tier TEXT NOT NULL,
                  ingress_mode TEXT NOT NULL, egress_mode TEXT NOT NULL,
                  heartbeat_state TEXT NOT NULL, ttl_seconds INTEGER NOT NULL,
                  adapter_ref TEXT, contract_sha TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_nodes(
                  chat_id TEXT PRIMARY KEY, node_id TEXT UNIQUE NOT NULL,
                  surface_id TEXT NOT NULL REFERENCES surfaces(surface_id),
                  privacy_tier TEXT NOT NULL, state TEXT NOT NULL,
                  last_sequence INTEGER NOT NULL, last_event_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL, last_event_sha TEXT NOT NULL,
                  last_receipt_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turn_events(
                  event_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL,
                  surface_id TEXT NOT NULL, turn_id TEXT NOT NULL,
                  sequence INTEGER NOT NULL, event_sha TEXT UNIQUE NOT NULL,
                  payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  UNIQUE(chat_id, sequence), UNIQUE(chat_id, turn_id)
                );
                CREATE TABLE IF NOT EXISTS outbox(
                  message_id TEXT PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
                  chat_id TEXT NOT NULL, kind TEXT NOT NULL, route TEXT NOT NULL,
                  payload_json TEXT NOT NULL, status TEXT NOT NULL,
                  effectful INTEGER NOT NULL, permit_ref TEXT,
                  attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                  delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS receipts(
                  receipt_id TEXT PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
                  kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adapter_cases(
                  case_id TEXT PRIMARY KEY, surface_id TEXT UNIQUE NOT NULL,
                  state TEXT NOT NULL, selected_strategy TEXT,
                  candidates_json TEXT NOT NULL, attempt_count INTEGER NOT NULL,
                  next_attempt_at TEXT, last_result TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS connector_seeds(
                  seed_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL,
                  connector_id TEXT NOT NULL, privacy_tier TEXT NOT NULL,
                  policy_version TEXT NOT NULL, seed_sha TEXT UNIQUE NOT NULL,
                  state TEXT NOT NULL, created_at TEXT NOT NULL,
                  UNIQUE(chat_id, connector_id, policy_version)
                );
                CREATE TABLE IF NOT EXISTS connector_events(
                  connector_event_id TEXT PRIMARY KEY, seed_id TEXT NOT NULL REFERENCES connector_seeds(seed_id),
                  operation_id TEXT NOT NULL, phase TEXT NOT NULL,
                  capability TEXT NOT NULL, status TEXT NOT NULL,
                  result_ref TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  UNIQUE(seed_id, operation_id, phase)
                );
                """
            )

    @staticmethod
    def load_surface_registry(path: str | Path) -> dict[str, Any]:
        try:
            registry = strict_json_loads(Path(path).read_text(encoding="utf-8"), field="surface_registry")
        except (OSError, ValueError) as exc:
            raise HeartbeatError("cannot load surface registry") from exc
        if registry.get("schema") != "EVIDENCEOPS-HEARTBEAT-SURFACES-2":
            raise HeartbeatError("unsupported surface registry")
        if registry.get("fixture_mode") != "SYNTHETIC_STATIC_CATALOGUE":
            raise HeartbeatError("surface registry must be explicitly synthetic")
        return registry

    @staticmethod
    def _validate_surface(surface: dict[str, Any]) -> None:
        for key in ("surface_id", "node_id"):
            if not SAFE_ID.fullmatch(str(surface.get(key, ""))):
                raise HeartbeatError(f"invalid surface {key}")
        if surface.get("privacy_tier") not in PRIVACY_RANK:
            raise HeartbeatError("invalid surface privacy tier")
        if not isinstance(surface.get("ttl_seconds"), int) or surface["ttl_seconds"] < 60:
            raise HeartbeatError("surface ttl_seconds must be at least 60")
        routes = surface.get("workaround_routes")
        if not isinstance(routes, list) or not routes:
            raise HeartbeatError("every surface requires at least one workaround route")
        if any(route.get("authority_class") != "A0" for route in routes):
            raise HeartbeatError("surface catalogue authority ceiling must be A0")
        if any(not isinstance(route.get("route"), str) or not SAFE_ID.fullmatch(route["route"]) for route in routes):
            raise HeartbeatError("surface route code is invalid")

    def index_surfaces(self, registry: dict[str, Any], *, observed_at: str) -> dict[str, Any]:
        observed = parse_timestamp(observed_at).isoformat()
        surfaces = registry.get("surfaces")
        if not isinstance(surfaces, list) or not surfaces:
            raise HeartbeatError("surface registry is empty")
        seen: set[str] = set()
        with self.lock, self.conn:
            for surface in surfaces:
                self._validate_surface(surface)
                surface_id = surface["surface_id"]
                if surface_id in seen:
                    raise HeartbeatError("duplicated surface_id")
                seen.add(surface_id)
                contract_sha = sha256_value(surface)
                self.conn.execute(
                    """INSERT INTO surfaces VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(surface_id) DO UPDATE SET
                    node_id=excluded.node_id,title=excluded.title,kind=excluded.kind,
                    privacy_tier=excluded.privacy_tier,ingress_mode=excluded.ingress_mode,
                    egress_mode=excluded.egress_mode,heartbeat_state=excluded.heartbeat_state,
                    ttl_seconds=excluded.ttl_seconds,adapter_ref=excluded.adapter_ref,
                    contract_sha=excluded.contract_sha,updated_at=excluded.updated_at""",
                    (
                        surface_id, surface["node_id"], surface["title"], surface["kind"],
                        surface["privacy_tier"], surface["ingress_mode"], surface["egress_mode"],
                        surface["heartbeat_state"], surface["ttl_seconds"],
                        surface.get("adapter_ref"), contract_sha, observed,
                    ),
                )
                if surface["heartbeat_state"] not in LIVE_STATES:
                    self._upsert_adapter_case(surface, observed)
        return self.surface_status()

    def _upsert_adapter_case(self, surface: dict[str, Any], observed: str) -> None:
        routes = list(surface["workaround_routes"])
        case_id = "ADP-" + sha256_value(surface["surface_id"])[:20].upper()
        self.conn.execute(
            """INSERT INTO adapter_cases VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(surface_id) DO UPDATE SET state=excluded.state,
            selected_strategy=excluded.selected_strategy,candidates_json=excluded.candidates_json,
            updated_at=excluded.updated_at""",
            (
                case_id, surface["surface_id"], "INVENTORY_ONLY", None,
                canonical_json(routes), 0, None, None, observed,
            ),
        )

    def surface_status(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT surface_id,node_id,title,kind,privacy_tier,ingress_mode,egress_mode,heartbeat_state,ttl_seconds,adapter_ref,contract_sha FROM surfaces ORDER BY surface_id"
        ).fetchall()
        surfaces = [dict(row) for row in rows]
        return {
            "schema": "EVIDENCEOPS-HEARTBEAT-SURFACE-INDEX-1",
            "surface_count": len(surfaces),
            "live_bidirectional_count": sum(s["heartbeat_state"] in LIVE_STATES for s in surfaces),
            "surfaces": surfaces,
            "truth_boundary": "The index covers documented surface classes. A surface is live only after provider-backed bidirectional readback.",
        }

    def remediation_cycle(self, *, observed_at: str) -> dict[str, Any]:
        observed = parse_timestamp(observed_at)
        open_count = self.conn.execute(
            "SELECT COUNT(*) FROM adapter_cases WHERE state != 'CLOSED_VERIFIED'"
        ).fetchone()[0]
        rows = self.conn.execute("SELECT * FROM adapter_cases ORDER BY surface_id").fetchall()
        cases: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["candidates"] = strict_json_loads(item.pop("candidates_json"), field="adapter_candidates")
            item["selected_strategy"] = None
            item["next_action"] = None
            item["automatic_action_allowed"] = False
            item["scheduler_authority"] = False
            cases.append(item)
        return {
            "schema": "EVIDENCEOPS-ADAPTER-INVENTORY-REPORT-2",
            "open_case_count": open_count,
            "due_case_count": len(cases),
            "deferred_case_count": 0,
            "cases": cases,
            "bypass_attempted": False,
            "scheduler_authority": False,
            "inventory_only": True,
            "observed_at": observed.isoformat(),
            "truth_boundary": "The facade inventories adapter obligations only. It does not rank, schedule, advance, retry, authorize or execute a route.",
        }

    def _route_requirements(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.capability_engine:
            return []
        return self.capability_engine.route_requirements(requirements)

    def ingest_turn(
        self,
        event: dict[str, Any],
        *,
        lineage: tuple[HeartbeatEnvelope, ...],
    ) -> dict[str, Any]:
        """Accept only metadata whose complete signed lineage passes v4 authority."""
        if self.authority is None:
            raise HeartbeatError("VERIFIED_V4_AUTHORITY_REQUIRED")
        allowed = {
            "schema", "event_id", "surface_id", "sequence", "observed_at",
            "destination_node_id", "envelope_id", "idempotency_key", "fixture_only",
        }
        if set(event) - allowed:
            raise HeartbeatError("raw or unknown turn event field prohibited")
        if event.get("schema") != "EVIDENCEOPS-CHAT-TURN-EVENT-2":
            raise HeartbeatError("unsupported turn event")
        if event.get("fixture_only"):
            raise HeartbeatError("static fixture cannot authorize ingress")
        for key in ("event_id", "surface_id", "destination_node_id"):
            if not SAFE_ID.fullmatch(str(event.get(key, ""))):
                raise HeartbeatError(f"invalid turn event {key}")
        sequence = event.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise HeartbeatError("turn sequence must be positive")
        observed = parse_timestamp(event.get("observed_at"))
        if not isinstance(lineage, tuple) or not lineage or any(not isinstance(item, HeartbeatEnvelope) for item in lineage):
            raise HeartbeatError("complete typed signed lineage is required")
        envelope = lineage[-1]
        if event.get("envelope_id") != envelope.envelope_id:
            raise HeartbeatError("turn event envelope binding mismatch")
        if event.get("idempotency_key") != envelope.idempotency_key:
            raise ReplayError("turn event idempotency binding mismatch")
        if sequence != envelope.sequence:
            raise ReplayError("turn sequence does not match signed envelope")
        surface_row = self.conn.execute(
            "SELECT * FROM surfaces WHERE surface_id=?", (event["surface_id"],)
        ).fetchone()
        if not surface_row:
            raise HeartbeatError("turn surface is not indexed")
        surface = dict(surface_row)
        if surface["heartbeat_state"] not in ACCEPTED_INGRESS_STATES:
            raise HeartbeatError("unhosted or catalogue-only surface cannot accept ingress")
        if surface["node_id"] != event["destination_node_id"]:
            raise HeartbeatError("surface destination registration mismatch")

        signed_receipt: Receipt = self.authority.accept(
            lineage=lineage,
            destination_node_id=event["destination_node_id"],
            now=observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        projected = {
            "schema": event["schema"],
            "event_id": event["event_id"],
            "surface_id": event["surface_id"],
            "sequence": sequence,
            "observed_at": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "origin_node_id": envelope.origin_node_id,
            "signing_node_id": envelope.signing_node_id,
            "destination_node_id": event["destination_node_id"],
            "envelope_id": envelope.envelope_id,
            "idempotency_key": envelope.idempotency_key,
            "owner_code": envelope.owner_code,
            "matter_code": envelope.matter_code,
            "classification": envelope.classification.value,
            "control_generation": envelope.control_generation,
            "capability_hashes": list(envelope.capability_hashes),
            "blocker_codes": [item.value for item in envelope.blocker_codes],
            "recommendations": [canonicalize(item) for item in envelope.recommendations],
            "signed_receipt": canonicalize(signed_receipt),
            "raw_content_included": False,
            "credentials_included": False,
        }
        event_sha = digest(projected)
        message_id = "MSG-" + event_sha.split(":", 1)[1][:20].upper()
        response = {
            "message_id": message_id,
            "kind": "VERIFIED_METADATA_RECEIPT",
            "event_id": event["event_id"],
            "acknowledged_sequence": sequence,
            "node_state": "NODE_ACTIVE_VERIFIED",
            "recommendations": projected["recommendations"],
            "authority_source": "VERIFIED_V4_FOUNDATION",
            "authority_ceiling": "A0",
            "content_policy": "METADATA_CODES_HASHES_AND_SIGNED_RECEIPTS_ONLY",
        }
        receipt_payload = {
            "receipt_id": signed_receipt.receipt_id,
            "operation_id": event["event_id"],
            "event_sha256": event_sha,
            "node_id": envelope.origin_node_id,
            "node_state": "NODE_ACTIVE_VERIFIED",
            "response": response,
            "signed_destination_receipt": canonicalize(signed_receipt),
            "duplicate": False,
            "transaction_state": "COMMITTED",
        }
        with self.lock:
            prior = self.conn.execute(
                "SELECT payload_json FROM receipts WHERE operation_id=?", (event["event_id"],)
            ).fetchone()
            if prior:
                prior_payload = strict_json_loads(prior["payload_json"], field="prior_receipt")
                if prior_payload.get("event_sha256") != event_sha:
                    raise ReplayError("TURN_OPERATION_IDEMPOTENCY_CONFLICT")
                prior_payload["duplicate"] = True
                return prior_payload
            current = self.conn.execute(
                "SELECT last_sequence FROM chat_nodes WHERE chat_id=?", (envelope.origin_node_id,)
            ).fetchone()
            if current and sequence <= current["last_sequence"]:
                raise ReplayError("stale or replayed signed sequence")
            state = "NODE_ACTIVE_VERIFIED"
            if current and sequence > current["last_sequence"] + 1:
                state = "NODE_SYNC_PENDING"
                response["node_state"] = state
                response["sequence_gap"] = sequence - current["last_sequence"] - 1
                receipt_payload["node_state"] = state
            destination = self.authority.registry.get(event["destination_node_id"])
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self.conn.execute(
                    "INSERT INTO turn_events VALUES(?,?,?,?,?,?,?,?)",
                    (
                        event["event_id"], envelope.origin_node_id, event["surface_id"],
                        envelope.envelope_id, sequence, event_sha,
                        canonical_json(projected), observed.isoformat(),
                    ),
                )
                self.conn.execute(
                    """INSERT INTO chat_nodes VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(chat_id) DO UPDATE SET state=excluded.state,
                    last_sequence=excluded.last_sequence,last_event_at=excluded.last_event_at,
                    expires_at=excluded.expires_at,last_event_sha=excluded.last_event_sha,
                    last_receipt_id=excluded.last_receipt_id""",
                    (
                        envelope.origin_node_id, envelope.origin_node_id, event["surface_id"],
                        surface["privacy_tier"], state, sequence, envelope.observed_at,
                        min(envelope.expires_at, destination.expires_at), event_sha, signed_receipt.receipt_id,
                    ),
                )
                self.conn.execute(
                    "INSERT INTO outbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        message_id, event["event_id"], envelope.origin_node_id,
                        response["kind"], surface["egress_mode"], canonical_json(response),
                        "READ_ONLY_RECEIPT_READY", 0, None, 0, observed.isoformat(), None,
                    ),
                )
                self.conn.execute(
                    "INSERT INTO receipts VALUES(?,?,?,?,?)",
                    (
                        signed_receipt.receipt_id, event["event_id"], "FOUNDATION_SIGNED_TURN",
                        canonical_json(receipt_payload), observed.isoformat(),
                    ),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        return receipt_payload

    def seed_connector(
        self,
        *,
        chat_id: str,
        connector_id: str,
        privacy_tier: str,
        created_at: str,
        policy_version: str = "KIMMIE-SEED-1.0",
    ) -> dict[str, Any]:
        for value in (chat_id, connector_id, policy_version):
            if not SAFE_ID.fullmatch(value):
                raise HeartbeatError("invalid Kimmie Seed identifier")
        if privacy_tier not in PRIVACY_RANK:
            raise HeartbeatError("invalid Kimmie Seed privacy tier")
        created = parse_timestamp(created_at).isoformat()
        body = {
            "schema": "EVIDENCEOPS-KIMMIE-SEED-1",
            "chat_ref": chat_id if PRIVACY_RANK[privacy_tier] <= PRIVACY_RANK["P1"] else text_ref(chat_id),
            "connector_id": connector_id,
            "privacy_tier": privacy_tier,
            "policy_version": policy_version,
            "required_phases": ["PRE", "POST"],
            "required_controls": [
                "CAPABILITY_SCAN", "AUTHORITY_CHECK", "PRIVACY_PROJECTION",
                "RESULT_HASH", "HEARTBEAT_READBACK", "ADAPTER_GAP_REMEDIATION",
            ],
            "credentials_included": False,
            "chat_content_included": False,
        }
        seed_sha = sha256_value(body)
        seed_id = "KSEED-" + seed_sha[:20].upper()
        with self.lock, self.conn:
            self.conn.execute(
                """INSERT INTO connector_seeds VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(chat_id,connector_id,policy_version) DO UPDATE SET state='ACTIVE',created_at=excluded.created_at""",
                (seed_id, chat_id, connector_id, privacy_tier, policy_version, seed_sha, "ACTIVE", created),
            )
            row = self.conn.execute(
                "SELECT * FROM connector_seeds WHERE chat_id=? AND connector_id=? AND policy_version=?",
                (chat_id, connector_id, policy_version),
            ).fetchone()
        return {**body, **dict(row), "seed_receipt": "RCP-" + seed_id}

    def record_connector_cycle(
        self,
        *,
        seed_id: str,
        operation_id: str,
        phase: str,
        capability: str,
        status: str,
        created_at: str,
        result_summary: str | None = None,
    ) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(seed_id) or not SAFE_ID.fullmatch(operation_id):
            raise HeartbeatError("invalid connector-cycle identifier")
        if phase not in {"PRE", "POST"}:
            raise HeartbeatError("connector-cycle phase must be PRE or POST")
        created = parse_timestamp(created_at).isoformat()
        seed = self.conn.execute("SELECT * FROM connector_seeds WHERE seed_id=?", (seed_id,)).fetchone()
        if not seed or seed["state"] != "ACTIVE":
            raise HeartbeatError("active Kimmie Seed not found")
        if phase == "POST":
            pre = self.conn.execute(
                "SELECT 1 FROM connector_events WHERE seed_id=? AND operation_id=? AND phase='PRE'",
                (seed_id, operation_id),
            ).fetchone()
            if not pre:
                raise HeartbeatError("connector POST requires a committed PRE seed event")
        result_ref = None
        if result_summary:
            result_ref = text_ref(result_summary)
        if not SAFE_ID.fullmatch(capability) or not SAFE_ID.fullmatch(status):
            raise HeartbeatError("connector capability and status must be controlled codes")
        payload = {
            "seed_id": seed_id, "operation_id": operation_id, "phase": phase,
            "capability": capability[:160], "status": status[:80],
            "result_ref": result_ref, "result_summary": None,
            "raw_content_included": False, "credentials_included": False,
        }
        event_id = "KCE-" + sha256_value(payload)[:20].upper()
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO connector_events VALUES(?,?,?,?,?,?,?,?,?)",
                (event_id, seed_id, operation_id, phase, capability[:160], status[:80], result_ref, canonical_json(payload), created),
            )
        return {
            **payload, "connector_event_id": event_id,
            "state": "PRE_BOUND" if phase == "PRE" else "POST_RECEIPT_BOUND",
        }

    def connector_seed_status(self, chat_id: str | None = None) -> dict[str, Any]:
        if chat_id:
            seeds = self.conn.execute("SELECT * FROM connector_seeds WHERE chat_id=? ORDER BY connector_id", (chat_id,)).fetchall()
        else:
            seeds = self.conn.execute("SELECT * FROM connector_seeds ORDER BY connector_id,chat_id").fetchall()
        output = []
        for raw in seeds:
            seed = dict(raw)
            counts = self.conn.execute(
                "SELECT phase,COUNT(*) AS count FROM connector_events WHERE seed_id=? GROUP BY phase", (seed["seed_id"],)
            ).fetchall()
            seed["phase_counts"] = {row["phase"]: row["count"] for row in counts}
            seed.pop("chat_id", None)
            output.append(seed)
        return {
            "schema": "EVIDENCEOPS-KIMMIE-SEED-STATUS-1", "seed_count": len(output), "seeds": output,
            "truth_boundary": "Seeds govern connector calls routed through a participating adapter; they cannot intercept unrelated direct connector calls.",
        }

    def acknowledge_delivery(self, message_id: str, *, adapter_receipt: str, delivered_at: str) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(message_id) or not SAFE_ID.fullmatch(adapter_receipt):
            raise HeartbeatError("invalid delivery receipt")
        delivered = parse_timestamp(delivered_at).isoformat()
        with self.lock, self.conn:
            row = self.conn.execute("SELECT status FROM outbox WHERE message_id=?", (message_id,)).fetchone()
            if not row:
                raise HeartbeatError("outbox message not found")
            self.conn.execute(
                "UPDATE outbox SET status='ADAPTER_DELIVERY_SUBMITTED',attempts=attempts+1,delivered_at=? WHERE message_id=?",
                (delivered, message_id),
            )
            receipt = {"message_id": message_id, "adapter_receipt": adapter_receipt, "state": "ADAPTER_DELIVERY_SUBMITTED", "delivered_at": delivered}
            self.conn.execute(
                "INSERT OR IGNORE INTO receipts VALUES(?,?,?,?,?)",
                ("RCP-DELIVERY-" + sha256_value(receipt)[:20].upper(), adapter_receipt, "DELIVERY", canonical_json(receipt), delivered),
            )
        return receipt

    def reconcile(self, *, observed_at: str) -> dict[str, Any]:
        observed = parse_timestamp(observed_at)
        nodes = self.conn.execute("SELECT * FROM chat_nodes ORDER BY node_id").fetchall()
        output = []
        with self.lock, self.conn:
            for raw in nodes:
                node = dict(raw)
                if node["state"] != "NODE_SYNC_PENDING" and parse_timestamp(node["expires_at"]) < observed:
                    node["state"] = "NODE_STALE"
                    self.conn.execute("UPDATE chat_nodes SET state='NODE_STALE' WHERE chat_id=?", (node["chat_id"],))
                output.append({
                    "node_id": node["node_id"], "surface_id": node["surface_id"],
                    "privacy_tier": node["privacy_tier"], "state": node["state"],
                    "last_sequence": node["last_sequence"], "last_event_at": node["last_event_at"],
                    "expires_at": node["expires_at"], "last_receipt_id": node["last_receipt_id"],
                })
        remediation = self.remediation_cycle(observed_at=observed.isoformat())
        return {
            "schema": "EVIDENCEOPS-HEARTBEAT-RECONCILIATION-1",
            "observed_at": observed.isoformat(), "nodes": output,
            "active_count": sum(n["state"] == "NODE_ACTIVE_VERIFIED" for n in output),
            "stale_count": sum(n["state"] == "NODE_STALE" for n in output),
            "sync_pending_count": sum(n["state"] == "NODE_SYNC_PENDING" for n in output),
            "adapter_remediation": remediation,
            "truth_boundary": "Only indexed chats that submitted a current turn event are visible; unsupported surfaces continuously produce remediation cases.",
        }

    def outbox(self, chat_id: str | None = None) -> list[dict[str, Any]]:
        if chat_id:
            rows = self.conn.execute("SELECT * FROM outbox WHERE chat_id=? ORDER BY created_at", (chat_id,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM outbox ORDER BY created_at").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = strict_json_loads(item.pop("payload_json"), field="outbox_payload")
            result.append(item)
        return result
