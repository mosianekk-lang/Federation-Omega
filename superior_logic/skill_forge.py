from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class TrajectoryLesson:
    mission_id: str
    steps: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    accepted: bool
    regression_free: bool
    owner_interventions: int = 0


@dataclass(frozen=True, slots=True)
class SkillCandidate:
    name: str
    description: str
    steps: tuple[str, ...]
    source_missions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str
    skill_sha256: str


@dataclass(frozen=True, slots=True)
class SkillReplay:
    replay_id: str
    passed: bool
    independent: bool
    regression_free: bool
    evidence_ref: str
    actor_id: str = ""
    trust_domain: str = ""


@dataclass(frozen=True, slots=True)
class HardenedSkillContract:
    skill_name: str
    skill_sha256: str
    preconditions: tuple[str, ...]
    negative_examples: tuple[str, ...]
    verification_requirements: tuple[str, ...]
    expires_at: str
    authority_ceiling: str
    effect_authority_inherited: bool
    contract_sha256: str

    def valid_at(self, at: str) -> bool:
        return _parse_time(at) < _parse_time(self.expires_at)


class SkillForge:
    """Form portable skills only from repeated proven trajectories.

    V2 hardening adds preconditions, negative examples, verification requirements,
    expiry and explicit no-effect-authority inheritance. The legacy replay evaluator
    is retained for admitted R1 compatibility; hardened replay promotion adds actor
    and trust-domain provenance so a same-lane alias cannot self-declare independent.
    Skill formation never grants provider, repository, IAM, deployment, traffic or
    spend authority.
    """

    def propose(
        self,
        *,
        name: str,
        description: str,
        lessons: Iterable[TrajectoryLesson],
        min_lessons: int = 3,
    ) -> SkillCandidate:
        good = [x for x in lessons if x.accepted and x.regression_free and x.evidence_refs]
        if len(good) < min_lessons:
            raise ValueError("INSUFFICIENT_PROVEN_TRAJECTORIES")
        base = list(good[0].steps)
        common = set(base)
        for lesson in good[1:]:
            common &= set(lesson.steps)
        steps = tuple(step for step in base if step in common)
        if not steps:
            raise ValueError("NO_STABLE_COMMON_PROCEDURE")
        missions = tuple(sorted(x.mission_id for x in good))
        refs = tuple(sorted({ref for x in good for ref in x.evidence_refs}))
        body = (name, description, steps, missions, refs)
        return SkillCandidate(_slug(name), description.strip(), steps, missions, refs, "CANDIDATE", _hash(body))

    def evaluate(self, skill: SkillCandidate, replays: Iterable[SkillReplay], *, min_independent: int = 2) -> str:
        """R1-compatible replay evaluation; retained to avoid breaking admitted callers."""
        rows = list(replays)
        good = [row for row in rows if row.passed and row.independent and row.regression_free and row.evidence_ref]
        if any(not row.regression_free for row in rows):
            return "REJECT_REGRESSION"
        return "ADOPT_CANDIDATE" if len(good) >= min_independent else "HOLD_MORE_REPLAY"

    def evaluate_hardened(
        self,
        skill: SkillCandidate,
        replays: Iterable[SkillReplay],
        *,
        implementation_actor_id: str,
        implementation_trust_domain: str,
        min_independent: int = 2,
    ) -> str:
        """V2 replay court requiring provenance-bound independence.

        The boolean ``independent`` remains necessary but is no longer sufficient:
        a qualifying replay must come from a different actor and trust domain than
        the implementation lane and must carry evidence. This court evaluates proof
        only; it grants no effect authority.
        """
        actor = implementation_actor_id.strip()
        trust = implementation_trust_domain.strip()
        if not actor:
            raise ValueError("IMPLEMENTATION_ACTOR_REQUIRED")
        if not trust:
            raise ValueError("IMPLEMENTATION_TRUST_DOMAIN_REQUIRED")
        if min_independent < 1:
            raise ValueError("MIN_INDEPENDENT_REPLAY_INVALID")

        rows = list(replays)
        if any(not row.regression_free for row in rows):
            return "REJECT_REGRESSION"
        good = [
            row
            for row in rows
            if row.passed
            and row.independent
            and row.regression_free
            and bool(row.evidence_ref)
            and bool(row.actor_id.strip())
            and bool(row.trust_domain.strip())
            and row.actor_id != actor
            and row.trust_domain != trust
        ]
        return "ADOPT_CANDIDATE" if len(good) >= min_independent else "HOLD_INDEPENDENT_REPLAY_INCOMPLETE"

    def harden(
        self,
        skill: SkillCandidate,
        *,
        preconditions: Iterable[str],
        negative_examples: Iterable[str],
        verification_requirements: Iterable[str],
        expires_at: str,
        authority_ceiling: str = "A1_INTERNAL",
    ) -> HardenedSkillContract:
        pre = _clean(preconditions)
        negatives = _clean(negative_examples)
        checks = _clean(verification_requirements)
        if not pre:
            raise ValueError("SKILL_PRECONDITIONS_REQUIRED")
        if not negatives:
            raise ValueError("SKILL_NEGATIVE_EXAMPLES_REQUIRED")
        if not checks:
            raise ValueError("SKILL_VERIFICATION_REQUIRED")
        if authority_ceiling not in {"A0_READ", "A1_INTERNAL"}:
            raise ValueError("SKILL_AUTHORITY_CEILING_TOO_HIGH")
        _parse_time(expires_at)
        body = {
            "skill_name": skill.name,
            "skill_sha256": skill.skill_sha256,
            "preconditions": pre,
            "negative_examples": negatives,
            "verification_requirements": checks,
            "expires_at": expires_at,
            "authority_ceiling": authority_ceiling,
            "effect_authority_inherited": False,
        }
        return HardenedSkillContract(
            skill_name=skill.name,
            skill_sha256=skill.skill_sha256,
            preconditions=pre,
            negative_examples=negatives,
            verification_requirements=checks,
            expires_at=expires_at,
            authority_ceiling=authority_ceiling,
            effect_authority_inherited=False,
            contract_sha256=_hash(body),
        )

    def render_skill_md(self, skill: SkillCandidate, *, checks: tuple[str, ...] = (), forbidden: tuple[str, ...] = ()) -> str:
        lines = ["---", f"name: {skill.name}", f"description: {skill.description}", "---", "", f"# {skill.name}", "", "## Procedure"]
        lines += [f"{i}. {step}" for i, step in enumerate(skill.steps, 1)]
        if checks:
            lines += ["", "## Verification", *[f"- {item}" for item in checks]]
        if forbidden:
            lines += ["", "## Forbidden actions", *[f"- {item}" for item in forbidden]]
        lines += ["", "## Provenance", f"- Skill candidate SHA-256: `{skill.skill_sha256}`", f"- Source missions: {', '.join(skill.source_missions)}"]
        return "\n".join(lines) + "\n"

    def render_hardened_skill_md(self, skill: SkillCandidate, contract: HardenedSkillContract) -> str:
        if contract.skill_sha256 != skill.skill_sha256:
            raise ValueError("SKILL_CONTRACT_MISMATCH")
        lines = [self.render_skill_md(skill).rstrip(), "", "## Preconditions"]
        lines += [f"- {item}" for item in contract.preconditions]
        lines += ["", "## Negative examples"]
        lines += [f"- {item}" for item in contract.negative_examples]
        lines += ["", "## Verification requirements"]
        lines += [f"- {item}" for item in contract.verification_requirements]
        lines += [
            "",
            "## Authority and expiry",
            f"- Authority ceiling: `{contract.authority_ceiling}`",
            f"- Effect authority inherited: `{str(contract.effect_authority_inherited).lower()}`",
            f"- Expires at: `{contract.expires_at}`",
            f"- Contract SHA-256: `{contract.contract_sha256}`",
        ]
        return "\n".join(lines) + "\n"


__all__ = [
    "HardenedSkillContract",
    "SkillCandidate",
    "SkillForge",
    "SkillReplay",
    "TrajectoryLesson",
]
