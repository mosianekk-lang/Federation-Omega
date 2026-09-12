from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REGISTRY_SCHEMA = "FEDERATION_FDOF_REGISTRY_V3"
LEASE_SCHEMA = "FEDERATION_SCOPED_LEASE_V3"
CLAIM_SCHEMA = "FEDERATION_COORDINATION_V2"
DEFAULT_REGISTRY_REF = "refs/heads/locks/fdof-v3-scoped-registry"
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "governance" / "federation_repository_coordination_v3.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Finding:
    rule: str
    detail: str


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "FEDERATION-REPOSITORY-COORDINATION-V3":
        raise ValueError("unexpected scoped repository coordination policy")
    return payload


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be offset-aware")
    return dt.astimezone(timezone.utc)


def normalize_ref(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith("refs/heads/"):
        return value
    if value.startswith("heads/"):
        return "refs/" + value
    return "refs/heads/" + value.lstrip("/")


def normalize_scope(value: str) -> str:
    value = str(value or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    value = re.sub(r"/+", "/", value.lstrip("/"))
    if value in {"*", "REPOSITORY", "repository:*"}:
        return "repository:*"
    return value.rstrip("/")


def normalize_write_set(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({normalize_scope(v) for v in values if str(v or "").strip()}))


def write_set_digest(values: Iterable[str]) -> str:
    payload = json.dumps(normalize_write_set(values), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _prefix(scope: str) -> bool:
    return scope.endswith("/**")


def _base(scope: str) -> str:
    return scope[:-3].rstrip("/") if _prefix(scope) else scope


def scopes_overlap(left: str, right: str) -> bool:
    a, b = normalize_scope(left), normalize_scope(right)
    if "repository:*" in {a, b}:
        return True
    ab, bb = _base(a), _base(b)
    if ab == bb:
        return True
    return (_prefix(a) and bb.startswith(ab + "/")) or (_prefix(b) and ab.startswith(bb + "/"))


def write_sets_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    return any(scopes_overlap(a, b) for a in normalize_write_set(left) for b in normalize_write_set(right))


def covers(write_set: Iterable[str], path: str) -> bool:
    target = normalize_scope(path)
    for scope in normalize_write_set(write_set):
        if scope == "repository:*" or scope == target:
            return True
        if _prefix(scope) and target.startswith(_base(scope) + "/"):
            return True
    return False


def parse_registry_message(message: str) -> dict[str, Any] | None:
    text = str(message or "").strip()
    if not text:
        return None
    first, _, body = text.partition("\n")
    if first.strip() != REGISTRY_SCHEMA:
        return None
    payload = json.loads(body)
    if not isinstance(payload, dict) or payload.get("schema") != REGISTRY_SCHEMA:
        raise ValueError("scoped registry schema mismatch")
    return payload


def extract_claim(body: str) -> dict[str, Any] | None:
    text = str(body or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, Mapping):
        if payload.get("schema") == CLAIM_SCHEMA:
            return dict(payload)
        if isinstance(payload.get("coordination"), Mapping):
            return dict(payload["coordination"])
        nested = payload.get("payload")
        if isinstance(nested, Mapping) and isinstance(nested.get("coordination"), Mapping):
            return dict(nested["coordination"])
    marker = re.search(r"<!--\s*FEDERATION_COORDINATION_V2\s*(\{.*?\})\s*-->", text, re.DOTALL)
    return json.loads(marker.group(1)) if marker else None


def _registry_findings(registry: Mapping[str, Any], policy: Mapping[str, Any], now: datetime) -> list[Finding]:
    out: list[Finding] = []
    try:
        generation = int(registry.get("generation", 0))
        if generation < 1:
            raise ValueError
    except (TypeError, ValueError):
        out.append(Finding("V3_REGISTRY_GENERATION_INVALID", str(registry.get("generation"))))
    leases = registry.get("active_leases")
    if not isinstance(leases, list):
        return out + [Finding("V3_REGISTRY_ACTIVE_LEASES_INVALID", "active_leases must be list")]
    ids: set[str] = set()
    fences: set[int] = set()
    valid: list[Mapping[str, Any]] = []
    for lease in leases:
        if not isinstance(lease, Mapping):
            out.append(Finding("V3_LEASE_INVALID", "lease must be object"))
            continue
        valid.append(lease)
        for field in policy.get("required_scoped_lease_fields", []):
            if lease.get(field) in (None, "", []):
                out.append(Finding("V3_LEASE_FIELD_MISSING", f"{lease.get('lease_id')}:{field}"))
        if lease.get("schema") != LEASE_SCHEMA or lease.get("state") != "ACTIVE":
            out.append(Finding("V3_LEASE_SCHEMA_OR_STATE_INVALID", str(lease.get("lease_id"))))
        if lease.get("effect") != "NONE":
            out.append(Finding("V3_LEASE_EFFECT_INVALID", str(lease.get("lease_id"))))
        if not SHA40.fullmatch(str(lease.get("source_head", ""))):
            out.append(Finding("V3_LEASE_SOURCE_INVALID", str(lease.get("lease_id"))))
        try:
            fence = int(lease.get("fencing_token", 0))
            if fence < 1 or fence in fences:
                out.append(Finding("V3_LEASE_FENCE_INVALID_OR_DUPLICATE", str(fence)))
            fences.add(fence)
        except (TypeError, ValueError):
            out.append(Finding("V3_LEASE_FENCE_INVALID_OR_DUPLICATE", str(lease.get("fencing_token"))))
        lid = str(lease.get("lease_id") or "")
        if lid in ids:
            out.append(Finding("V3_LEASE_ID_DUPLICATE", lid))
        ids.add(lid)
        try:
            if parse_time(str(lease.get("expires_at"))) <= now:
                out.append(Finding("V3_ACTIVE_EXPIRED_NOT_TERMINAL", lid))
        except ValueError:
            out.append(Finding("V3_LEASE_TIME_INVALID", lid))
        ws = normalize_write_set(lease.get("write_set") or [])
        if not ws or str(lease.get("write_set_digest")) != write_set_digest(ws):
            out.append(Finding("V3_WRITE_SET_INVALID", lid))
    for i, left in enumerate(valid):
        for right in valid[i + 1:]:
            if write_sets_overlap(left.get("write_set") or [], right.get("write_set") or []):
                out.append(Finding("V3_REGISTRY_ACTIVE_OVERLAP", f"{left.get('lease_id')}:{right.get('lease_id')}"))
    return out


def can_acquire(registry: Mapping[str, Any], requested: Sequence[str], *, now: datetime | None = None, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(policy or load_policy())
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    findings = _registry_findings(registry, policy, now_utc)
    request = normalize_write_set(requested)
    if not request:
        findings.append(Finding("V3_ACQUIRE_EMPTY_WRITE_SET", "write_set empty"))
    for lease in registry.get("active_leases", []) if isinstance(registry.get("active_leases"), list) else []:
        if isinstance(lease, Mapping) and write_sets_overlap(request, lease.get("write_set") or []):
            findings.append(Finding("V3_ACQUIRE_CONFLICT", str(lease.get("lease_id"))))
    return {"schema":"FEDERATION-FDOF-V3-ACQUIRE-PREFLIGHT","status":"PASS" if not findings else "FAIL","write_set":list(request),"write_set_digest":write_set_digest(request),"findings":[asdict(x) for x in findings]}


def evaluate(*, base_sha: str, pr_paths: Sequence[str], pr_body: str, registry_message: str, registry_sha: str, now: datetime | None = None, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(policy or load_policy())
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    paths = normalize_write_set(pr_paths)
    try:
        registry = parse_registry_message(registry_message)
    except Exception as exc:
        return _result("FAIL","V3_REGISTRY_MALFORMED",registry_sha,None,paths,[Finding("V3_REGISTRY_MALFORMED",str(exc))])
    if registry is None:
        state = "V3_REGISTRY_NOT_INITIALIZED_COMPAT" if policy.get("legacy_unscoped_compatibility", True) else "V3_REGISTRY_REQUIRED"
        return _result("PASS" if policy.get("legacy_unscoped_compatibility", True) else "FAIL",state,registry_sha,None,paths,[])
    findings = _registry_findings(registry, policy, now_utc)
    if findings:
        return _result("FAIL","V3_REGISTRY_INVALID",registry_sha,registry,paths,findings)
    claim = extract_claim(pr_body)
    v3_claim = claim if isinstance(claim, Mapping) and claim.get("schema") == CLAIM_SCHEMA else None
    active = [x for x in registry.get("active_leases", []) if isinstance(x, Mapping)]
    own = None
    if v3_claim:
        own = next((x for x in active if str(x.get("lease_id")) == str(v3_claim.get("lease_id"))), None)
        if own is None:
            findings.append(Finding("V3_OWN_LEASE_NOT_ACTIVE", str(v3_claim.get("lease_id"))))
        else:
            for field in policy.get("required_scoped_claim_fields", []):
                if v3_claim.get(field) in (None,"",[]):
                    findings.append(Finding("V3_CLAIM_FIELD_MISSING", field))
            for field in ("lease_id","writer_node","system","workstream","transaction_id","idempotency_key","source_head","turn_capture_id","fencing_token","write_set_digest"):
                if str(v3_claim.get(field)) != str(own.get(field)):
                    findings.append(Finding("V3_CLAIM_MISMATCH", field))
            if normalize_ref(str(v3_claim.get("registry_ref"))) != normalize_ref(str(policy.get("registry_ref", DEFAULT_REGISTRY_REF))):
                findings.append(Finding("V3_REGISTRY_REF_MISMATCH", str(v3_claim.get("registry_ref"))))
            if str(own.get("source_head")) != str(base_sha):
                findings.append(Finding("V3_SOURCE_EPOCH_MISMATCH", str(own.get("source_head"))))
            escaped = [p for p in paths if not covers(own.get("write_set") or [], p)]
            if escaped:
                findings.append(Finding("V3_WRITE_SET_ESCAPE", ",".join(escaped)))
            if any(write_sets_overlap([p], policy.get("repository_global_paths", [])) for p in paths) and "repository:*" not in normalize_write_set(own.get("write_set") or []):
                findings.append(Finding("V3_GLOBAL_PATH_REQUIRES_REPOSITORY_SCOPE", "repository:* required"))
    for lease in active:
        if own is lease:
            continue
        if write_sets_overlap(paths, lease.get("write_set") or []):
            findings.append(Finding("V3_FOREIGN_WRITE_CONFLICT", str(lease.get("lease_id"))))
    if not v3_claim and not findings:
        if policy.get("legacy_unscoped_compatibility", True):
            return _result("PASS","V3_LEGACY_UNSCOPED_NO_CONFLICT",registry_sha,registry,paths,[])
        findings.append(Finding("V3_SCOPED_CLAIM_REQUIRED","claim required"))
    status = "PASS" if not findings else "FAIL"
    state = "V3_SCOPED_CLAIM_VERIFIED_DISJOINT_ALLOWED" if status == "PASS" else ("V3_OVERLAP_REJECTED" if any(x.rule=="V3_FOREIGN_WRITE_CONFLICT" for x in findings) else "V3_CLAIM_REJECTED")
    return _result(status,state,registry_sha,registry,paths,findings)


def _result(status: str, state: str, registry_sha: str, registry: Mapping[str, Any] | None, paths: Sequence[str], findings: Sequence[Finding]) -> dict[str, Any]:
    return {"schema":"FEDERATION-REPOSITORY-COORDINATION-ASSESSMENT-V3","status":status,"state":state,"registry_commit_sha":registry_sha,"registry_generation":registry.get("generation") if isinstance(registry,Mapping) else None,"active_lease_count":len(registry.get("active_leases",[])) if isinstance(registry,Mapping) and isinstance(registry.get("active_leases"),list) else 0,"pr_paths":list(paths),"findings":[asdict(x) for x in findings],"provider_effect_authorized":False,"provider_branch_protection_equivalent":False}


def _git(root: Path, args: list[str]) -> str:
    p = subprocess.run(["git",*args],cwd=root,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git command failed")
    return p.stdout.strip()


def _origin_available(root: Path) -> bool:
    p = subprocess.run(["git","remote","get-url","origin"],cwd=root,text=True,capture_output=True)
    return p.returncode == 0 and bool(p.stdout.strip())


def evaluate_hosted_pull_request_v3(repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or Path(__file__).resolve().parents[1])
    policy = load_policy()
    if not _origin_available(root):
        return _result(
            "NOT_APPLICABLE",
            "V3_HOSTED_PROVIDER_NOT_APPLICABLE_NO_ORIGIN",
            "",
            None,
            (),
            [Finding("V3_HOSTED_PROVIDER_NOT_APPLICABLE_NO_ORIGIN", "provider git origin unavailable")],
        )
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pr = event.get("pull_request") or {}
    base = str((pr.get("base") or {}).get("sha") or "")
    head = str((pr.get("head") or {}).get("sha") or "")
    body = str(pr.get("body") or "")
    ref = str(policy.get("registry_ref", DEFAULT_REGISTRY_REF))
    remote = _git(root,["ls-remote","origin",ref])
    if not remote:
        return evaluate(base_sha=base,pr_paths=(),pr_body=body,registry_message="",registry_sha="",policy=policy)
    registry_sha = remote.split()[0]
    _git(root,["fetch","--no-tags","--quiet","origin",ref])
    message = _git(root,["show","-s","--format=%B",registry_sha])
    for sha in (base,head):
        if SHA40.fullmatch(sha):
            try:
                _git(root,["cat-file","-e",f"{sha}^{{commit}}"])
            except RuntimeError:
                _git(root,["fetch","--no-tags","--quiet","origin",sha])
    paths = tuple(x for x in _git(root,["diff","--name-only",f"{base}...{head}"]).splitlines() if x.strip()) if SHA40.fullmatch(base) and SHA40.fullmatch(head) else ()
    return evaluate(base_sha=base,pr_paths=paths,pr_body=body,registry_message=message,registry_sha=registry_sha,policy=policy)
