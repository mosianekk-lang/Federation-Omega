from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,127}")
GENERIC_DEF_RE = re.compile(r"(?:class|def|function|interface|type|struct|enum|trait|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)")
IMPORT_RE = re.compile(r"(?:from\s+([A-Za-z0-9_./-]+)\s+import|import\s+([A-Za-z0-9_./-]+)|require\(['\"]([^'\"]+)|from\s+['\"]([^'\"]+))")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _safe_path(raw: str) -> str:
    p = PurePosixPath(raw)
    if p.is_absolute() or not p.parts or ".." in p.parts:
        raise ValueError(f"unsafe repository path: {raw}")
    return p.as_posix()


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(x.lower() for x in TOKEN_RE.findall(text))


@dataclass(frozen=True, slots=True)
class GraphFile:
    path: str
    sha256: str
    language: str
    symbols: tuple[str, ...]
    imports: tuple[str, ...]
    references: tuple[str, ...]
    complexity: int


@dataclass(frozen=True, slots=True)
class RepoGraphSnapshot:
    files: tuple[GraphFile, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    symbol_owners: tuple[tuple[str, str], ...]
    graph_sha256: str

    def by_path(self) -> dict[str, GraphFile]:
        return {x.path: x for x in self.files}


@dataclass(frozen=True, slots=True)
class ImpactResult:
    seeds: tuple[str, ...]
    impacted_paths: tuple[str, ...]
    reasons: tuple[tuple[str, str], ...]
    impact_sha256: str


class RepoGraph:
    """Deterministic repository graph with Python AST precision and portable fallback parsing."""

    LANGUAGE_BY_EXT = {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
        ".jsx": "javascript", ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
        ".cs": "csharp", ".rb": "ruby", ".php": "php", ".cpp": "cpp", ".cc": "cpp",
        ".c": "c", ".h": "c-header", ".md": "markdown", ".json": "json", ".yaml": "yaml",
        ".yml": "yaml",
    }

    @classmethod
    def _analyze(cls, raw_path: str, text: str) -> GraphFile:
        path = _safe_path(raw_path)
        language = cls.LANGUAGE_BY_EXT.get(PurePosixPath(path).suffix.lower(), "text")
        symbols: set[str] = set()
        imports: set[str] = set()
        refs: set[str] = set()
        complexity = 1
        if language == "python":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                tree = None
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.add(node.name)
                    elif isinstance(node, ast.Import):
                        imports.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module)
                    elif isinstance(node, ast.Name):
                        refs.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        refs.add(node.attr)
                    elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match, ast.BoolOp)):
                        complexity += 1
        if not symbols:
            symbols.update(GENERIC_DEF_RE.findall(text))
        if language != "python":
            for m in IMPORT_RE.finditer(text):
                imports.add(next(x for x in m.groups() if x))
            refs.update(TOKEN_RE.findall(text))
            complexity += text.count(" if ") + text.count(" for ") + text.count(" while ") + text.count(" case ")
        refs.difference_update(symbols)
        return GraphFile(
            path=path,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            language=language,
            symbols=tuple(sorted(symbols)),
            imports=tuple(sorted(imports)),
            references=tuple(sorted(refs)),
            complexity=max(complexity, 1),
        )

    def build(self, files: Mapping[str, str]) -> RepoGraphSnapshot:
        records = tuple(sorted((self._analyze(p, text) for p, text in files.items()), key=lambda x: x.path))
        symbol_owner: dict[str, str] = {}
        module_owner: dict[str, str] = {}
        for record in records:
            for symbol in record.symbols:
                symbol_owner.setdefault(symbol, record.path)
            module = record.path.rsplit(".", 1)[0].replace("/", ".")
            module_owner[module] = record.path
            module_owner[module.split(".")[-1]] = record.path
        edges: set[tuple[str, str]] = set()
        for record in records:
            for imp in record.imports:
                target = module_owner.get(imp) or module_owner.get(imp.split(".")[-1])
                if target and target != record.path:
                    edges.add((record.path, target))
            for ref in record.references:
                target = symbol_owner.get(ref)
                if target and target != record.path:
                    edges.add((record.path, target))
        owners = tuple(sorted((symbol, owner) for symbol, owner in symbol_owner.items()))
        edge_rows = tuple(sorted(edges))
        body = {
            "files": [(x.path, x.sha256, x.symbols, x.imports, x.complexity) for x in records],
            "edges": edge_rows,
            "owners": owners,
        }
        return RepoGraphSnapshot(records, edge_rows, owners, _sha(body))

    def impact(self, snapshot: RepoGraphSnapshot, changed_paths: Iterable[str], *, depth: int = 3) -> ImpactResult:
        if depth < 0:
            raise ValueError("depth must be >= 0")
        available = set(snapshot.by_path())
        seeds = tuple(sorted({_safe_path(p) for p in changed_paths if _safe_path(p) in available}))
        reverse: dict[str, set[str]] = defaultdict(set)
        for src, dst in snapshot.dependency_edges:
            reverse[dst].add(src)
        q = deque((seed, 0) for seed in seeds)
        seen = set(seeds)
        reasons: dict[str, str] = {seed: "direct_change" for seed in seeds}
        while q:
            node, d = q.popleft()
            if d >= depth:
                continue
            for dependent in sorted(reverse.get(node, ())):
                if dependent not in seen:
                    seen.add(dependent)
                    reasons[dependent] = f"depends_on:{node}"
                    q.append((dependent, d + 1))
        reason_rows = tuple(sorted(reasons.items()))
        impacted = tuple(sorted(seen))
        return ImpactResult(seeds, impacted, reason_rows, _sha((seeds, impacted, reason_rows)))

    def ranked_context(self, snapshot: RepoGraphSnapshot, query: str, *, limit: int = 12) -> tuple[str, ...]:
        q = set(_tokens(query))
        if not q or limit < 1:
            return ()
        scored: list[tuple[float, str]] = []
        for record in snapshot.files:
            path_tokens = set(_tokens(record.path))
            symbol_tokens = set(_tokens(" ".join(record.symbols)))
            ref_tokens = set(_tokens(" ".join(record.references)))
            score = 4 * len(q & symbol_tokens) + 2 * len(q & path_tokens) + len(q & ref_tokens)
            score += min(record.complexity / 20, 1.5)
            if score:
                scored.append((score, record.path))
        return tuple(path for _, path in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit])


class WorkspaceMode(StrEnum):
    EPHEMERAL = "EPHEMERAL"
    PREPARED = "PREPARED"
    PERSISTENT_MISSION = "PERSISTENT_MISSION"


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    workspace_id: str
    base_revision: str
    repo_graph_sha256: str
    toolchain_digest: str
    dependency_digest: str
    mode: WorkspaceMode
    writable_paths: tuple[str, ...]
    network_policy: str
    cache_key: str
    rollback_ref: str
    spec_sha256: str


@dataclass(frozen=True, slots=True)
class WorkspaceReceipt:
    workspace_id: str
    prepared: bool
    isolated: bool
    base_revision_verified: bool
    rollback_verified: bool
    artifact_refs: tuple[str, ...]
    receipt_sha256: str


class PreparedWorkspaceForge:
    """Creates content-addressed workspace contracts; actual environment execution remains delegated."""

    def plan(
        self,
        *,
        base_revision: str,
        repo_graph_sha256: str,
        toolchain: Mapping[str, str],
        dependencies: Mapping[str, str],
        writable_paths: Iterable[str],
        mode: WorkspaceMode = WorkspaceMode.PREPARED,
        network_policy: str = "DENY_BY_DEFAULT",
    ) -> WorkspaceSpec:
        if not base_revision.strip() or not repo_graph_sha256.strip():
            raise ValueError("base_revision/repo_graph_sha256 required")
        paths = tuple(sorted({_safe_path(p) for p in writable_paths}))
        tool_digest = _sha(dict(sorted(toolchain.items())))
        dep_digest = _sha(dict(sorted(dependencies.items())))
        cache_key = _sha((base_revision, repo_graph_sha256, tool_digest, dep_digest, mode.value))
        workspace_id = "ws-" + cache_key[:20]
        rollback_ref = f"git:{base_revision}"
        body = (workspace_id, base_revision, repo_graph_sha256, tool_digest, dep_digest, mode.value, paths, network_policy, rollback_ref)
        return WorkspaceSpec(
            workspace_id, base_revision, repo_graph_sha256, tool_digest, dep_digest, mode,
            paths, network_policy, cache_key, rollback_ref, _sha(body)
        )

    def verify(
        self,
        spec: WorkspaceSpec,
        *,
        observed_base_revision: str,
        isolated: bool,
        rollback_readback_ref: str,
        artifact_refs: Iterable[str] = (),
    ) -> WorkspaceReceipt:
        refs = tuple(sorted(set(x for x in artifact_refs if str(x).strip())))
        base_ok = observed_base_revision == spec.base_revision
        rollback_ok = rollback_readback_ref == spec.rollback_ref
        prepared = base_ok and isolated and rollback_ok
        body = (spec.workspace_id, prepared, isolated, base_ok, rollback_ok, refs)
        return WorkspaceReceipt(spec.workspace_id, prepared, isolated, base_ok, rollback_ok, refs, _sha(body))


class SpecialistRole(StrEnum):
    EXPLORER = "EXPLORER"
    ARCHITECT = "ARCHITECT"
    IMPLEMENTER = "IMPLEMENTER"
    TESTER = "TESTER"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    VERIFIER = "VERIFIER"
    INTEGRATOR = "INTEGRATOR"


@dataclass(frozen=True, slots=True)
class FleetTask:
    task_id: str
    role: SpecialistRole
    target_paths: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    mutation: bool = False
    proof_obligations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FleetLane:
    lane_id: str
    task_ids: tuple[str, ...]
    writable_paths: tuple[str, ...]
    mutation: bool
    conflict_domain: str


@dataclass(frozen=True, slots=True)
class FleetPlan:
    lanes: tuple[FleetLane, ...]
    fan_in_order: tuple[str, ...]
    serial_barriers: tuple[tuple[str, str], ...]
    plan_sha256: str


class CodingFleetPlanner:
    """Parallelises only disjoint mutation domains; read/no-effect lanes may freely fan out."""

    @staticmethod
    def _overlap(a: Sequence[str], b: Sequence[str]) -> bool:
        aa, bb = set(a), set(b)
        if aa & bb:
            return True
        for x in aa:
            for y in bb:
                if x.startswith(y.rstrip("/") + "/") or y.startswith(x.rstrip("/") + "/"):
                    return True
        return False

    def plan(self, tasks: Iterable[FleetTask]) -> FleetPlan:
        rows = list(tasks)
        if not rows:
            raise ValueError("at least one task required")
        ids = {x.task_id for x in rows}
        if len(ids) != len(rows):
            raise ValueError("duplicate task_id")
        if any(set(x.depends_on) - ids for x in rows):
            raise ValueError("unknown dependency")

        lanes: list[FleetLane] = []
        serial: set[tuple[str, str]] = set()
        for task in sorted(rows, key=lambda x: x.task_id):
            paths = tuple(sorted({_safe_path(p) for p in task.target_paths}))
            lane = FleetLane(
                lane_id=f"lane-{task.task_id}",
                task_ids=(task.task_id,),
                writable_paths=paths if task.mutation else (),
                mutation=task.mutation,
                conflict_domain=_sha(paths)[:16] if task.mutation else "NO_EFFECT",
            )
            if task.mutation:
                for prior in lanes:
                    if prior.mutation and self._overlap(prior.writable_paths, lane.writable_paths):
                        serial.add((prior.lane_id, lane.lane_id))
            lanes.append(lane)

        indeg = {x.task_id: 0 for x in rows}
        graph: dict[str, set[str]] = defaultdict(set)
        for task in rows:
            for dep in task.depends_on:
                graph[dep].add(task.task_id)
                indeg[task.task_id] += 1
        ready = sorted(k for k, v in indeg.items() if v == 0)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for nxt in sorted(graph[node]):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
                    ready.sort()
        if len(order) != len(rows):
            raise ValueError("task dependency cycle")
        lane_by_task = {lane.task_ids[0]: lane.lane_id for lane in lanes}
        fan_in = tuple(lane_by_task[x] for x in order)
        lane_rows = tuple(lanes)
        serial_rows = tuple(sorted(serial))
        return FleetPlan(lane_rows, fan_in, serial_rows, _sha((tuple(asdict(x) for x in lane_rows), fan_in, serial_rows)))


class CheckKind(StrEnum):
    SYNTAX = "SYNTAX"
    COMPILE = "COMPILE"
    LINT = "LINT"
    TYPE = "TYPE"
    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"
    PROPERTY = "PROPERTY"
    FUZZ = "FUZZ"
    MUTATION = "MUTATION"
    SECURITY = "SECURITY"
    DEPENDENCY = "DEPENDENCY"
    SECRET_SCAN = "SECRET_SCAN"
    PERFORMANCE = "PERFORMANCE"
    REPRODUCIBLE_BUILD = "REPRODUCIBLE_BUILD"
    ROLLBACK = "ROLLBACK"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"


@dataclass(frozen=True, slots=True)
class CheckObservation:
    kind: CheckKind
    passed: bool
    evidence_ref: str
    independent: bool = False
    hard: bool = True


@dataclass(frozen=True, slots=True)
class SupercourtVerdict:
    status: str
    required: tuple[str, ...]
    missing: tuple[str, ...]
    failed: tuple[str, ...]
    independent_readback: bool
    evidence_refs: tuple[str, ...]
    verdict_sha256: str


class VerificationSupercourt:
    POLICIES = {
        "LOW": (CheckKind.SYNTAX, CheckKind.UNIT, CheckKind.SEMANTIC_READBACK),
        "MEDIUM": (CheckKind.SYNTAX, CheckKind.LINT, CheckKind.TYPE, CheckKind.UNIT, CheckKind.INTEGRATION, CheckKind.SEMANTIC_READBACK),
        "HIGH": (CheckKind.SYNTAX, CheckKind.LINT, CheckKind.TYPE, CheckKind.UNIT, CheckKind.INTEGRATION, CheckKind.SECURITY, CheckKind.SECRET_SCAN, CheckKind.ROLLBACK, CheckKind.SEMANTIC_READBACK, CheckKind.INDEPENDENT_REVIEW),
        "CRITICAL": (CheckKind.SYNTAX, CheckKind.COMPILE, CheckKind.LINT, CheckKind.TYPE, CheckKind.UNIT, CheckKind.INTEGRATION, CheckKind.PROPERTY, CheckKind.FUZZ, CheckKind.MUTATION, CheckKind.SECURITY, CheckKind.DEPENDENCY, CheckKind.SECRET_SCAN, CheckKind.PERFORMANCE, CheckKind.REPRODUCIBLE_BUILD, CheckKind.ROLLBACK, CheckKind.SEMANTIC_READBACK, CheckKind.INDEPENDENT_REVIEW),
    }

    def evaluate(self, risk: str, observations: Iterable[CheckObservation], *, extra_required: Iterable[CheckKind] = ()) -> SupercourtVerdict:
        key = str(risk).upper()
        if key not in self.POLICIES:
            raise ValueError("unknown risk")
        required = tuple(sorted({x.value for x in self.POLICIES[key]} | {CheckKind(x).value for x in extra_required}))
        rows = list(observations)
        by: dict[str, list[CheckObservation]] = defaultdict(list)
        for row in rows:
            by[row.kind.value].append(row)
        missing = tuple(sorted(kind for kind in required if not by.get(kind) or not any(x.evidence_ref.strip() for x in by[kind])))
        failed = tuple(sorted({x.kind.value for x in rows if x.hard and not x.passed}))
        independent_readback = any(
            x.kind in {CheckKind.SEMANTIC_READBACK, CheckKind.INDEPENDENT_REVIEW}
            and x.passed and x.independent and x.evidence_ref.strip()
            for x in rows
        )
        if failed:
            status = "REJECTED"
        elif missing:
            status = "INCOMPLETE"
        elif key in {"HIGH", "CRITICAL"} and not independent_readback:
            status = "INCOMPLETE_INDEPENDENCE"
        else:
            status = "PROVEN"
        refs = tuple(sorted({x.evidence_ref for x in rows if x.evidence_ref.strip()}))
        body = (status, required, missing, failed, independent_readback, refs)
        return SupercourtVerdict(status, required, missing, failed, independent_readback, refs, _sha(body))


class ClosureAction(StrEnum):
    REUSE_INTERNAL = "REUSE_INTERNAL"
    COMPOSE_INTERNAL = "COMPOSE_INTERNAL"
    HARVEST_MECHANISM = "HARVEST_MECHANISM"
    BUILD_SMALLEST_GAP = "BUILD_SMALLEST_GAP"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class ClosureCandidate:
    candidate_id: str
    source: str
    capabilities: tuple[str, ...]
    proof_strength: float
    risk: float
    provenance_ref: str


@dataclass(frozen=True, slots=True)
class ClosureDecision:
    gap_id: str
    action: ClosureAction
    selected: tuple[str, ...]
    residual: tuple[str, ...]
    proof_gates: tuple[str, ...]
    decision_sha256: str


class AutonomousCapabilityClosure:
    """Closes missing capability by reuse/compose/harvest/build while preserving proof and authority boundaries."""

    def decide(
        self,
        *,
        gap_id: str,
        required: Iterable[str],
        internal: Iterable[ClosureCandidate] = (),
        external: Iterable[ClosureCandidate] = (),
        max_risk: float = 0.5,
        min_proof: float = 0.5,
    ) -> ClosureDecision:
        req = set(required)
        if not gap_id.strip() or not req:
            raise ValueError("gap identity and requirements required")

        def admissible(rows: Iterable[ClosureCandidate]) -> list[ClosureCandidate]:
            out = []
            for c in rows:
                if c.risk <= max_risk and c.proof_strength >= min_proof and c.provenance_ref.strip():
                    out.append(c)
            return sorted(out, key=lambda c: (-len(req & set(c.capabilities)), -c.proof_strength, c.risk, c.candidate_id))

        internal_rows = admissible(internal)
        covered: set[str] = set()
        selected: list[str] = []
        for c in internal_rows:
            gain = req - covered
            if gain & set(c.capabilities):
                selected.append(c.candidate_id)
                covered |= set(c.capabilities)
            if req <= covered:
                action = ClosureAction.REUSE_INTERNAL if len(selected) == 1 else ClosureAction.COMPOSE_INTERNAL
                return self._decision(gap_id, action, selected, req - covered, ("CURRENT_SOURCE_READBACK", "REGRESSION", "SEMANTIC_READBACK"))
        if selected:
            residual = req - covered
            return self._decision(gap_id, ClosureAction.COMPOSE_INTERNAL, selected, residual, ("CURRENT_SOURCE_READBACK", "REGRESSION", "SEMANTIC_READBACK", "RESIDUAL_GAP_FALSIFIER"))

        external_rows = admissible(external)
        if external_rows:
            best = external_rows[0]
            residual = req - set(best.capabilities)
            return self._decision(gap_id, ClosureAction.HARVEST_MECHANISM, [best.candidate_id], residual, ("PRIMARY_EVIDENCE", "PROVENANCE", "CLEAN_ROOM_ABSTRACTION", "LOCAL_TESTS", "CFBE_CHALLENGER", "ROLLBACK"))
        return self._decision(gap_id, ClosureAction.BUILD_SMALLEST_GAP, (), req, ("SPEC", "FALSIFICATION", "UNIT", "INTEGRATION", "SECURITY", "ROLLBACK", "CFBE_CHALLENGER"))

    @staticmethod
    def _decision(gap_id: str, action: ClosureAction, selected: Iterable[str], residual: Iterable[str], gates: Iterable[str]) -> ClosureDecision:
        s = tuple(selected)
        r = tuple(sorted(residual))
        g = tuple(gates)
        return ClosureDecision(gap_id, action, s, r, g, _sha((gap_id, action.value, s, r, g)))


@dataclass(frozen=True, slots=True)
class ReadinessSignal:
    signal_id: str
    passed: bool
    proof_ref: str
    receiver: str


@dataclass(frozen=True, slots=True)
class SLOSReadinessVerdict:
    status: str
    missing: tuple[str, ...]
    failed: tuple[str, ...]
    receivers: tuple[str, ...]
    proof_refs: tuple[str, ...]
    verdict_sha256: str


class SLOSReadinessCourt:
    REQUIRED = (
        "SOURCE_ADMISSION",
        "LEAK_GUARD",
        "AIRLOCK",
        "REPOGRAPH",
        "WORKSPACE_FORGE",
        "CODING_FLEET",
        "VERIFICATION_SUPERCOURT",
        "CAPABILITY_CLOSURE",
        "ROLLBACK",
        "SEMANTIC_READBACK",
        "INDEPENDENT_ASSURANCE",
    )

    def evaluate(self, signals: Iterable[ReadinessSignal]) -> SLOSReadinessVerdict:
        rows = list(signals)
        by: dict[str, list[ReadinessSignal]] = defaultdict(list)
        for row in rows:
            by[row.signal_id].append(row)
        missing = tuple(sorted(x for x in self.REQUIRED if not by.get(x) or not any(y.proof_ref.strip() for y in by[x])))
        failed = tuple(sorted({x.signal_id for x in rows if not x.passed}))
        receivers = tuple(sorted({x.receiver for x in rows if x.receiver.strip()}))
        refs = tuple(sorted({x.proof_ref for x in rows if x.proof_ref.strip()}))
        if failed:
            status = "REJECTED"
        elif missing:
            status = "INCOMPLETE"
        elif len(receivers) < 2:
            status = "INCOMPLETE_INDEPENDENT_RECEIVER"
        else:
            status = "SLOS_ENGINEERING_RUNTIME_READY"
        return SLOSReadinessVerdict(status, missing, failed, receivers, refs, _sha((status, missing, failed, receivers, refs)))
