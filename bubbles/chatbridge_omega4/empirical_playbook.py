from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EvidenceTier(str, Enum):
    PROVIDER_READBACK = "PROVIDER_READBACK"
    REPRODUCED_CANARY = "REPRODUCED_CANARY"
    PRIMARY_ARTIFACT = "PRIMARY_ARTIFACT"
    OFFICIAL_DOCUMENTATION = "OFFICIAL_DOCUMENTATION"
    USER_REPORTED = "USER_REPORTED"
    SYSTEM_INFERENCE = "SYSTEM_INFERENCE"


class LearningState(str, Enum):
    OBSERVED_NOT_PROMOTED = "OBSERVED_NOT_PROMOTED"
    VERIFIED_BOUNDED = "VERIFIED_BOUNDED"
    PROMOTED = "PROMOTED"
    HOLD_CONTRADICTION = "HOLD_CONTRADICTION"
    HOLD_INSUFFICIENT_EMPIRICAL_PROOF = "HOLD_INSUFFICIENT_EMPIRICAL_PROOF"
    REJECTED_PRIVACY = "REJECTED_PRIVACY"
    SUPERSEDED = "SUPERSEDED"


class LearningSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LearningShareScope(str, Enum):
    NAMESPACE_ONLY = "NAMESPACE_ONLY"
    FEDERATION_OPERATIONAL = "FEDERATION_OPERATIONAL"


@dataclass(frozen=True)
class ChatLearningEvent:
    """A minimum-necessary operational observation from a ChatBridge-active chat.

    The event is not a transcript capture. Matter facts and raw sensitive content remain in
    their governed source systems. The playbook receives only a sanitized operational
    pattern, evidence pointers and the observed result.
    """

    event_id: str
    observed_at: str
    conversation_key: str
    namespace_key: str
    category: str
    problem_signature: str
    observation: str
    outcome: str
    evidence_tier: EvidenceTier = EvidenceTier.USER_REPORTED
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)
    verified: bool = False
    reproduced: bool = False
    independent_observation: bool = True
    severity: LearningSeverity = LearningSeverity.MEDIUM
    repair: str = ""
    reusable: bool = True
    share_scope: LearningShareScope = LearningShareScope.NAMESPACE_ONLY
    matter_key: str = ""
    contains_raw_sensitive_content: bool = False
    contains_secret: bool = False
    supports_candidate_rule: bool = True
    contradicts_candidate_rule: bool = False
    supersedes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        required = {
            "event_id": self.event_id,
            "observed_at": self.observed_at,
            "conversation_key": self.conversation_key,
            "namespace_key": self.namespace_key,
            "category": self.category,
            "problem_signature": self.problem_signature,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"learning event missing required fields: {missing}")
        if self.verified and not self.evidence_refs:
            raise ValueError("verified learning events require evidence_refs")
        if self.reproduced and not self.evidence_refs:
            raise ValueError("reproduced learning events require evidence_refs")
        if self.supports_candidate_rule and self.contradicts_candidate_rule:
            raise ValueError("an event cannot both support and contradict the same rule")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["evidence_tier"] = self.evidence_tier.value
        payload["severity"] = self.severity.value
        payload["share_scope"] = self.share_scope.value
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["supersedes"] = list(self.supersedes)
        return payload


class EmpiricalPlaybookStore:
    """SQLite WAL persistence for learning events, playbook rules and health history."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._local = threading.local()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path,
                timeout=30,
                isolation_level=None,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;

            CREATE TABLE IF NOT EXISTS chat_learning_events(
                event_id TEXT PRIMARY KEY,
                problem_signature TEXT NOT NULL,
                namespace_key TEXT NOT NULL,
                conversation_key TEXT NOT NULL,
                learning_state TEXT NOT NULL,
                evidence_tier TEXT NOT NULL,
                severity TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_playbook_rules(
                rule_id TEXT PRIMARY KEY,
                problem_signature TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                instruction TEXT NOT NULL,
                scope TEXT NOT NULL,
                learning_state TEXT NOT NULL,
                confidence REAL NOT NULL,
                payload_json TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_health_log(
                assessment_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL,
                risk_state TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_learning_signature
                ON chat_learning_events(problem_signature, created_at);
            CREATE INDEX IF NOT EXISTS idx_health_conversation
                ON conversation_health_log(conversation_key, created_at);
            """
        )
        conn.close()

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _fingerprint(cls, value: Any) -> str:
        return hashlib.sha256(cls._canonical_json(value).encode("utf-8")).hexdigest()

    def record_event(self, payload: Dict[str, Any], state: str) -> Dict[str, Any]:
        fingerprint = self._fingerprint(payload)
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT fingerprint FROM chat_learning_events WHERE event_id=?",
                (payload["event_id"],),
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise ValueError("event_id already exists with different content")
                conn.execute("COMMIT")
                return {
                    "event_id": payload["event_id"],
                    "learning_state": state,
                    "fingerprint": fingerprint,
                    "reused": True,
                }
            conn.execute(
                """INSERT INTO chat_learning_events(
                    event_id,problem_signature,namespace_key,conversation_key,
                    learning_state,evidence_tier,severity,payload_json,fingerprint,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    payload["event_id"],
                    payload["problem_signature"],
                    payload["namespace_key"],
                    payload["conversation_key"],
                    state,
                    payload["evidence_tier"],
                    payload["severity"],
                    self._canonical_json(payload),
                    fingerprint,
                    time.time(),
                ),
            )
            readback = conn.execute(
                "SELECT fingerprint,learning_state FROM chat_learning_events WHERE event_id=?",
                (payload["event_id"],),
            ).fetchone()
            if not readback or readback["fingerprint"] != fingerprint:
                raise RuntimeError("learning event readback failed")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return {
            "event_id": payload["event_id"],
            "learning_state": readback["learning_state"],
            "fingerprint": fingerprint,
            "reused": False,
        }

    def events(self, problem_signature: Optional[str] = None) -> List[Dict[str, Any]]:
        if problem_signature:
            rows = self._conn().execute(
                """SELECT payload_json,learning_state FROM chat_learning_events
                   WHERE problem_signature=? ORDER BY created_at ASC""",
                (problem_signature,),
            ).fetchall()
        else:
            rows = self._conn().execute(
                "SELECT payload_json,learning_state FROM chat_learning_events ORDER BY created_at ASC"
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["learning_state"] = row["learning_state"]
            result.append(payload)
        return result

    def upsert_rule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        fingerprint = self._fingerprint(payload)
        now = time.time()
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT rule_id,fingerprint,created_at FROM chat_playbook_rules WHERE problem_signature=?",
                (payload["problem_signature"],),
            ).fetchone()
            if existing and existing["fingerprint"] == fingerprint:
                conn.execute("COMMIT")
                return {
                    "rule_id": existing["rule_id"],
                    "learning_state": payload["learning_state"],
                    "fingerprint": fingerprint,
                    "reused": True,
                }
            created_at = existing["created_at"] if existing else now
            if existing and existing["rule_id"] != payload["rule_id"]:
                raise ValueError("problem_signature already belongs to a different rule_id")
            conn.execute(
                """INSERT INTO chat_playbook_rules(
                    rule_id,problem_signature,title,instruction,scope,learning_state,
                    confidence,payload_json,fingerprint,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    title=excluded.title,
                    instruction=excluded.instruction,
                    scope=excluded.scope,
                    learning_state=excluded.learning_state,
                    confidence=excluded.confidence,
                    payload_json=excluded.payload_json,
                    fingerprint=excluded.fingerprint,
                    updated_at=excluded.updated_at""",
                (
                    payload["rule_id"],
                    payload["problem_signature"],
                    payload["title"],
                    payload["instruction"],
                    payload["scope"],
                    payload["learning_state"],
                    float(payload["confidence"]),
                    self._canonical_json(payload),
                    fingerprint,
                    created_at,
                    now,
                ),
            )
            readback = conn.execute(
                "SELECT fingerprint,learning_state FROM chat_playbook_rules WHERE rule_id=?",
                (payload["rule_id"],),
            ).fetchone()
            if not readback or readback["fingerprint"] != fingerprint:
                raise RuntimeError("playbook rule readback failed")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return {
            "rule_id": payload["rule_id"],
            "learning_state": readback["learning_state"],
            "fingerprint": fingerprint,
            "reused": False,
        }

    def rules(self) -> List[Dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT payload_json FROM chat_playbook_rules ORDER BY updated_at DESC"
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def record_health(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        assessment_id = f"cbh_{uuid.uuid4().hex}"
        payload_json = self._canonical_json(assessment)
        conn = self._conn()
        conn.execute(
            """INSERT INTO conversation_health_log(
                assessment_id,conversation_key,risk_state,risk_score,payload_json,created_at
            ) VALUES(?,?,?,?,?,?)""",
            (
                assessment_id,
                assessment["conversation_key"],
                assessment["risk_state"],
                int(assessment["risk_score"]),
                payload_json,
                time.time(),
            ),
        )
        readback = conn.execute(
            "SELECT risk_state,risk_score FROM conversation_health_log WHERE assessment_id=?",
            (assessment_id,),
        ).fetchone()
        if not readback:
            raise RuntimeError("conversation health readback failed")
        return {
            "assessment_id": assessment_id,
            "risk_state": readback["risk_state"],
            "risk_score": int(readback["risk_score"]),
        }

    def health_history(self, conversation_key: str) -> List[Dict[str, Any]]:
        rows = self._conn().execute(
            """SELECT payload_json FROM conversation_health_log
               WHERE conversation_key=? ORDER BY created_at ASC""",
            (conversation_key,),
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]


class EmpiricalPlaybookEngine:
    """Evidence-bound continuous learning for ChatBridge-active conversations."""

    VERSION = "CB-PLAYBOOK-1.0"
    EMPIRICAL_TIERS = {
        EvidenceTier.PROVIDER_READBACK.value,
        EvidenceTier.REPRODUCED_CANARY.value,
        EvidenceTier.PRIMARY_ARTIFACT.value,
    }

    def __init__(self, store: EmpiricalPlaybookStore) -> None:
        self.store = store

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "coverage_scope": "ALL_CHATBRIDGE_ACTIVE_CHATS",
            "native_hidden_chat_access": "NOT_CLAIMED",
            "capture_rule": "MATERIAL_OPERATIONAL_OBSERVATIONS_ONLY",
            "privacy_rule": "MINIMUM_NECESSARY_NO_RAW_SENSITIVE_CONTENT_OR_SECRETS",
            "matter_wall_rule": "MATTER_FACTS_REMAIN_IN_GOVERNED_SOURCE_SYSTEMS",
            "evidence_hierarchy": [
                EvidenceTier.PROVIDER_READBACK.value,
                EvidenceTier.REPRODUCED_CANARY.value,
                EvidenceTier.PRIMARY_ARTIFACT.value,
                EvidenceTier.OFFICIAL_DOCUMENTATION.value,
                EvidenceTier.USER_REPORTED.value,
                EvidenceTier.SYSTEM_INFERENCE.value,
            ],
            "documentation_role": "SUPPLEMENTARY_REFERENCE_NOT_SOLE_PROMOTION_SOURCE",
            "promotion_rule": "TWO_INDEPENDENT_VERIFIED_EMPIRICAL_EVENTS_WITH_PROVIDER_OR_CANARY_SUPPORT",
            "single_event_rule": "MAY_BECOME_VERIFIED_BOUNDED_NOT_GLOBAL_PROMOTED",
            "contradiction_rule": "HOLD_AND_REVALIDATE_DO_NOT_SILENTLY_OVERWRITE",
            "model_weight_learning": "NOT_CLAIMED",
            "rule_lifecycle": [
                LearningState.OBSERVED_NOT_PROMOTED.value,
                LearningState.VERIFIED_BOUNDED.value,
                LearningState.PROMOTED.value,
                LearningState.HOLD_CONTRADICTION.value,
                LearningState.SUPERSEDED.value,
            ],
        }

    @staticmethod
    def _privacy_rejected(event: ChatLearningEvent) -> bool:
        return event.contains_raw_sensitive_content or event.contains_secret

    def record(self, event: ChatLearningEvent) -> Dict[str, Any]:
        payload = event.to_dict()
        if self._privacy_rejected(event):
            payload["observation"] = "[REDACTED_BY_PLAYBOOK_PRIVACY_POLICY]"
            payload["outcome"] = "[REDACTED_BY_PLAYBOOK_PRIVACY_POLICY]"
            payload["repair"] = ""
            if event.contains_secret:
                payload["evidence_refs"] = []
            state = LearningState.REJECTED_PRIVACY
        elif (
            event.verified
            and event.evidence_refs
            and event.evidence_tier.value in self.EMPIRICAL_TIERS
        ):
            state = LearningState.VERIFIED_BOUNDED
        else:
            state = LearningState.OBSERVED_NOT_PROMOTED
        receipt = self.store.record_event(payload, state.value)
        return {**receipt, "stored_payload": payload}

    def promote_rule(
        self,
        *,
        problem_signature: str,
        rule_id: str,
        title: str,
        instruction: str,
        requested_scope: str = "ALL_CHATBRIDGE_ACTIVE_CHATS",
    ) -> Dict[str, Any]:
        events = self.store.events(problem_signature)
        if not events:
            raise ValueError("no learning events exist for problem_signature")

        usable = [
            event
            for event in events
            if event["learning_state"] != LearningState.REJECTED_PRIVACY.value
            and bool(event.get("reusable", False))
        ]
        qualified_support = [
            event
            for event in usable
            if event["learning_state"] == LearningState.VERIFIED_BOUNDED.value
            and bool(event.get("supports_candidate_rule", False))
            and bool(event.get("independent_observation", False))
        ]
        qualified_contradictions = [
            event
            for event in usable
            if event["learning_state"] == LearningState.VERIFIED_BOUNDED.value
            and bool(event.get("contradicts_candidate_rule", False))
        ]
        distinct_conversations = {
            event["conversation_key"] for event in qualified_support
        }
        empirical_tiers = {
            event["evidence_tier"] for event in qualified_support
        }
        provider_or_canary = bool(
            empirical_tiers
            & {
                EvidenceTier.PROVIDER_READBACK.value,
                EvidenceTier.REPRODUCED_CANARY.value,
            }
        )
        docs_only = bool(usable) and all(
            event["evidence_tier"] == EvidenceTier.OFFICIAL_DOCUMENTATION.value
            for event in usable
        )

        if qualified_contradictions:
            state = LearningState.HOLD_CONTRADICTION
        elif docs_only:
            state = LearningState.HOLD_INSUFFICIENT_EMPIRICAL_PROOF
        elif (
            len(qualified_support) >= 2
            and len(distinct_conversations) >= 2
            and provider_or_canary
        ):
            state = LearningState.PROMOTED
        elif qualified_support:
            state = LearningState.VERIFIED_BOUNDED
        else:
            state = LearningState.HOLD_INSUFFICIENT_EMPIRICAL_PROOF

        global_scope_allowed = (
            state is LearningState.PROMOTED
            and requested_scope == "ALL_CHATBRIDGE_ACTIVE_CHATS"
            and bool(qualified_support)
            and all(
                event["share_scope"]
                == LearningShareScope.FEDERATION_OPERATIONAL.value
                for event in qualified_support
            )
            and all(not event.get("matter_key") for event in qualified_support)
        )
        if global_scope_allowed:
            scope = requested_scope
        else:
            namespaces = sorted({event["namespace_key"] for event in usable})
            scope = (
                "NAMESPACE:" + ",".join(namespaces)
                if namespaces
                else "NO_PROMOTABLE_SCOPE"
            )

        confidence = 0.25
        confidence += min(0.35, len(qualified_support) * 0.12)
        confidence += min(0.20, len(distinct_conversations) * 0.07)
        if provider_or_canary:
            confidence += 0.12
        if qualified_contradictions:
            confidence = min(confidence, 0.35)
        confidence = round(min(0.99, confidence), 2)

        evidence_event_ids = [event["event_id"] for event in usable]
        evidence_refs = sorted(
            {
                ref
                for event in usable
                for ref in event.get("evidence_refs", [])
            }
        )
        payload = {
            "rule_id": rule_id,
            "playbook_version": self.VERSION,
            "problem_signature": problem_signature,
            "title": title,
            "instruction": instruction,
            "scope": scope,
            "learning_state": state.value,
            "confidence": confidence,
            "qualified_support_count": len(qualified_support),
            "qualified_contradiction_count": len(qualified_contradictions),
            "distinct_conversation_count": len(distinct_conversations),
            "evidence_event_ids": evidence_event_ids,
            "evidence_refs": evidence_refs,
            "documentation_only": docs_only,
            "provider_or_canary_support": provider_or_canary,
            "review_triggers": [
                "NEW_CONTRADICTORY_PROVIDER_READBACK",
                "CHATGPT_UI_OR_PROVIDER_BEHAVIOUR_CHANGE",
                "FAILED_REGRESSION_CANARY",
                "SCOPE_OR_PRIVACY_CHANGE",
            ],
            "truth_boundary": (
                "BOUNDED_OPERATIONAL_RULE_NOT_OPENAI_PLATFORM_GUARANTEE"
            ),
        }
        receipt = self.store.upsert_rule(payload)
        return {**receipt, "rule": payload}

    def rules(self) -> List[Dict[str, Any]]:
        return self.store.rules()
