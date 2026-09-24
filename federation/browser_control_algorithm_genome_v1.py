from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

SCHEMA = "FUSE_BROWSER_CONTROL_ALGORITHM_GENOME_V1"
VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class BrowserControlAlgorithm:
    algorithm_id: str
    name: str
    category: str
    mechanism: str
    tags: tuple[str, ...]
    bindings: tuple[str, ...]
    maturity: str = "SOURCE_CANDIDATE"

    def score(self, text: str) -> int:
        haystack = text.lower()
        return sum(1 for tag in self.tags if tag.lower() in haystack)

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["tags"] = list(self.tags)
        row["bindings"] = list(self.bindings)
        return row


ALGORITHMS: tuple[BrowserControlAlgorithm, ...] = (
    BrowserControlAlgorithm("FBCP-001","Browser Carrier Census","ROUTING","Discover callable browser carriers and current capability state.",("carrier","census","browser","callable"),("FUSE_SOVEREIGN_PLANE","SOL_6_2","CAPABILITY_TRUTH")),
    BrowserControlAlgorithm("FBCP-002","Carrier Portfolio Election","ROUTING","Rank qualified browser carriers by capability, currentness, privacy, recovery and failure-domain diversity.",("carrier","portfolio","route","failover"),("PORTFOLIO_V2","SOL_6_2","FDOF")),
    BrowserControlAlgorithm("FBCP-003","Semantic UI Graph Builder","SEMANTICS","Represent interactive controls as semantic nodes instead of brittle coordinates.",("semantic","dom","accessibility","controls"),("SOL_6_2","FUSE_WORKSPACE")),
    BrowserControlAlgorithm("FBCP-004","Stable Control Resolver","SEMANTICS","Resolve controls from stable id, role, accessible name, text and href quorum.",("resolver","role","aria","stable"),("SOL_6_2","PROOFOS")),
    BrowserControlAlgorithm("FBCP-005","Intent to Browser Action Compiler","PLANNING","Compile owner intent into typed browser operations with expected readback.",("intent","action","compile","browser"),("MISSION_IR","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-006","Tab and Window Graph Manager","CONTROL","Create, activate, close and inspect browser tabs without making tab identity canonical mission state.",("tab","window","create","activate"),("SOL_6_2","CHATBRIDGE")),
    BrowserControlAlgorithm("FBCP-007","Verified Action Executor","PROOF","Require semantic readback before mutating browser command is verified.",("verify","readback","action","effect"),("SOL_6_2","PROOFOS","SICF")),
    BrowserControlAlgorithm("FBCP-008","Browser State Mirror","STATE","Persist compact browser state pointers outside the provider UI.",("state","mirror","tab","session"),("PORTABLE_STATE","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-009","UI Drift Self-Healer","RESILIENCE","Re-resolve controls when labels/DOM/layout change instead of retrying stale selectors.",("drift","selector","heal","ui"),("FAILURE_HARVEST","CFBE","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-010","Structured Site Tool Discovery","TOOLS","Prefer structured site tools/WebMCP over simulated UI control when available.",("webmcp","tool","site","structured"),("FIO","MCP","CAPABILITY_MARKET")),
    BrowserControlAlgorithm("FBCP-011","DOM Vision Fusion","SEMANTICS","Fuse DOM/accessibility and visual evidence, holding on material contradiction.",("dom","vision","fusion","contradiction"),("FUSE_WORKSPACE","PROOFOS")),
    BrowserControlAlgorithm("FBCP-012","Modal and Popup Resolver","CONTROL","Detect overlays/dialogs and route them through typed control handling.",("modal","dialog","popup","overlay"),("SOL_6_2","FUSE_WORKSPACE")),
    BrowserControlAlgorithm("FBCP-013","File Transfer Broker","ARTIFACTS","Bind upload/download operations to artifact identity, privacy and hash readback.",("upload","download","file","hash"),("ARTIFACT_VAULT","SICF","PROOFOS")),
    BrowserControlAlgorithm("FBCP-014","Signed-In Account Guard","SECURITY","Verify active account/workspace context before website-state action.",("account","profile","workspace","guard"),("FIO","SICF","SECURE_CAPABILITY_BOX")),
    BrowserControlAlgorithm("FBCP-015","Browser Permission Broker","AUTHORITY","Separate browser, site, file and consequential-action permissions.",("permission","authority","browser","site"),("FDOF","SICF")),
    BrowserControlAlgorithm("FBCP-016","Prompt Injection Boundary","SECURITY","Treat page text as untrusted observation and forbid it from mutating authority or mission goals.",("prompt","injection","page","untrusted"),("AEGIS_RED_TEAM","FDOF","SICF")),
    BrowserControlAlgorithm("FBCP-017","Session Reconnect Recovery","DURABILITY","Resume browser work after tab/browser/transport interruption without replaying committed effects.",("session","reconnect","recovery","resume"),("SOL_6_2","GENESIS","PORTABLE_STATE")),
    BrowserControlAlgorithm("FBCP-018","Direct New-Tab Route Resolver","CONTROL","Create a new ChatGPT tab directly when UI controls lack native link semantics.",("new","tab","chat","route"),("SOL_6_2","BROWSER_COMPANION")),
    BrowserControlAlgorithm("FBCP-019","Keyboard Command Driver","CONTROL","Use stable keyboard/browser commands when safer than pointer control.",("keyboard","shortcut","command","browser"),("FUSE_WORKSPACE","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-020","Browser Action Journal","STATE","Event-source browser command, authority, action and readback receipts.",("journal","event","action","readback"),("SOL_6_2","DELIVERY_JOURNAL","PROOFOS")),
    BrowserControlAlgorithm("FBCP-021","Cross-Carrier Browser Failover","RESILIENCE","Hydrate the same mission onto a healthy browser carrier after route-local failure.",("browser","failover","carrier","hydrate"),("SOL_6_2","CHATBRIDGE","GENESIS")),
    BrowserControlAlgorithm("FBCP-022","Browser Capability Twin","STATE","Maintain current per-carrier callable browser capabilities and failure domains.",("capability","twin","browser","currentness"),("CAPABILITY_TRUTH","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-023","Owner Takeover Bridge","CONTROL","Allow owner takeover/release without destroying durable agent state.",("owner","takeover","handoff","browser"),("FUSE_WORKSPACE","PORTABLE_STATE")),
    BrowserControlAlgorithm("FBCP-024","Browser Regression Court","PROOF","Continuously court critical browser flows after UI/browser changes.",("regression","browser","court","test"),("PROOFOS","REALITY_JUDGE","CFBE")),
    BrowserControlAlgorithm("FBCP-025","Action-Bound Authority Lease","AUTHORITY","Consume exact authority lease immediately before website-state browser effect.",("authority","lease","website","effect"),("FDOF","SOL_6_2","SICF")),
    BrowserControlAlgorithm("FBCP-026","Command Idempotency Envelope","EFFECTS","Reject reuse of one browser command id for different semantics.",("idempotency","command","collision","browser"),("SOL_6_2","SICF")),
    BrowserControlAlgorithm("FBCP-027","Semantic Readback Quorum","PROOF","Require expected state plus observed action signal before mutation verification.",("readback","quorum","semantic","verify"),("SOL_6_2","PROOFOS")),
    BrowserControlAlgorithm("FBCP-028","Stale Snapshot Invalidation","CURRENTNESS","Invalidate semantic snapshots after navigation, DOM epoch or tab identity change.",("snapshot","stale","currentness","dom"),("AECL","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-029","Tab Lease Epoch","CONCURRENCY","Fence concurrent agents from controlling one tab under stale ownership.",("tab","lease","epoch","fence"),("FDOF","SICF","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-030","Control Collision Domain","CONCURRENCY","Compile browser command conflict domains for tab, page region and website-effect target.",("collision","tab","control","concurrency"),("MISSION_IR","FDOF")),
    BrowserControlAlgorithm("FBCP-031","Locator Quorum","SEMANTICS","Require agreement across multiple semantic locator signals for sensitive controls.",("locator","quorum","semantic","sensitive"),("PROOFOS","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-032","Ambiguity Hold","SEMANTICS","Hold when top semantic targets are too close instead of guessing.",("ambiguous","target","hold","semantic"),("SOL_6_2","REALITY_JUDGE")),
    BrowserControlAlgorithm("FBCP-033","Account Context Fingerprint","SECURITY","Hash non-secret account/workspace context and bind it to browser action plans.",("account","fingerprint","context","workspace"),("SICF","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-034","Permission Drift Detector","SECURITY","Detect lost or widened browser/site permissions before control continues.",("permission","drift","browser","security"),("AECL","AEGIS_RED_TEAM")),
    BrowserControlAlgorithm("FBCP-035","Origin Policy Compiler","SECURITY","Compile explicit allowed origins per command class and reject redirects outside policy.",("origin","policy","redirect","url"),("FIO","SICF")),
    BrowserControlAlgorithm("FBCP-036","Navigation Redirect Court","PROOF","Verify final origin and route semantics after navigation or redirect.",("navigation","redirect","court","origin"),("PROOFOS","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-037","Download Completion Reconciler","ARTIFACTS","Reconcile browser download event, file identity, size and artifact digest.",("download","artifact","digest","reconcile"),("ARTIFACT_VAULT","PROOFOS")),
    BrowserControlAlgorithm("FBCP-038","Upload Privacy Gate","ARTIFACTS","Check privacy/matter scope before a browser upload command is authorized.",("upload","privacy","matter","file"),("FDOF","SICF","ARTIFACT_VAULT")),
    BrowserControlAlgorithm("FBCP-039","Browser Command Coalescer","PERFORMANCE","Collapse redundant queued browser reads/navigation requests while preserving semantics.",("coalesce","queue","browser","redundant"),("SOL_6_2","THROUGHPUT_INTELLIGENCE")),
    BrowserControlAlgorithm("FBCP-040","Adaptive Poll Backoff","PERFORMANCE","Adjust command polling frequency to activity and runtime reachability.",("poll","backoff","latency","runtime"),("THROUGHPUT_INTELLIGENCE","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-041","Control Latency Telemetry","OBSERVABILITY","Attribute queue, command, DOM and readback latency separately.",("latency","telemetry","browser","span"),("PROOFOS","OTEL","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-042","Browser Failure Fingerprint","LEARNING","Normalize browser failure fingerprints for changed-mechanism repair.",("failure","fingerprint","browser","repair"),("FAILURE_HARVEST","CFBE")),
    BrowserControlAlgorithm("FBCP-043","Shadow Semantic Resolver","LEARNING","Run a challenger resolver in shadow and compare target identity without effect.",("shadow","resolver","challenger","semantic"),("CFBE","PROOFOS")),
    BrowserControlAlgorithm("FBCP-044","Carrier Canary Tournament","LEARNING","Compare healthy carriers on no-effect browser tasks before promotion.",("carrier","canary","benchmark","browser"),("CFBE","PORTFOLIO_V2")),
    BrowserControlAlgorithm("FBCP-045","Cross-Device Browser Handoff","CONTINUITY","Hydrate browser mission pointers across owner-authorized devices without transferring secrets.",("device","handoff","browser","hydrate"),("FUSE_MOBILE","PORTABLE_STATE","CHATBRIDGE")),
    BrowserControlAlgorithm("FBCP-046","Command Deadline Budget","PERFORMANCE","Expire stale browser commands instead of executing outdated intent.",("deadline","ttl","command","stale"),("SOL_6_2","AECL")),
    BrowserControlAlgorithm("FBCP-047","Website Effect Replay Guard","EFFECTS","Never replay a website-state browser effect until provider/page readback resolves unknown effect.",("website","effect","replay","readback"),("SOL_6_2","FDOF","SICF")),
    BrowserControlAlgorithm("FBCP-048","DOM Mutation Epoch Tracker","CURRENTNESS","Increment page semantic epoch on material interactive-DOM change.",("dom","mutation","epoch","currentness"),("AECL","SOL_6_2")),
    BrowserControlAlgorithm("FBCP-049","Browser Version Compatibility Gate","CURRENTNESS","Revalidate companion behavior on browser/extension/runtime version changes.",("browser","version","compatibility","extension"),("AECL","PROOFOS")),
    BrowserControlAlgorithm("FBCP-050","Browser Control Value Ledger","LEARNING","Measure owner burden, recovery time, success rate and regressions per browser-control mechanism.",("value","owner","burden","browser"),("RAEFI","CFBE","VALUE_LEDGER")),
)


def validate_algorithms(
    algorithms: Sequence[BrowserControlAlgorithm] = ALGORITHMS,
) -> None:
    ids = [row.algorithm_id for row in algorithms]
    expected = [f"FBCP-{index:03d}" for index in range(1, len(algorithms) + 1)]
    if ids != expected:
        raise ValueError("browser control algorithm ids must be contiguous and monotonic")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate browser control algorithm id")
    if any(not row.bindings for row in algorithms):
        raise ValueError("every browser algorithm must bind to existing FUSE organs")


def select_algorithms(
    objective: str,
    *,
    limit: int = 12,
) -> tuple[BrowserControlAlgorithm, ...]:
    if limit <= 0:
        return ()
    ranked = sorted(
        ALGORITHMS,
        key=lambda row: (-row.score(objective), row.category, row.algorithm_id),
    )
    matched = [row for row in ranked if row.score(objective) > 0]
    if matched:
        return tuple(matched[:limit])
    selected: list[BrowserControlAlgorithm] = []
    seen: set[str] = set()
    for row in ranked:
        if row.category in seen:
            continue
        seen.add(row.category)
        selected.append(row)
        if len(selected) >= limit:
            break
    return tuple(selected)


def algorithm_summary() -> Mapping[str, object]:
    validate_algorithms()
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "algorithm_count": len(ALGORITHMS),
        "first_id": ALGORITHMS[0].algorithm_id,
        "last_id": ALGORITHMS[-1].algorithm_id,
        "categories": sorted({row.category for row in ALGORITHMS}),
        "authority_expansion": False,
        "new_controller": False,
        "new_truth_root": False,
        "truth_boundary": (
            "ALGORITHM_REGISTERED_NE_SOURCE_IMPLEMENTED; "
            "SOURCE_IMPLEMENTED_NE_BROWSER_INSTALLED; "
            "BROWSER_INSTALLED_NE_LIVE_CONTROL_VERIFIED; "
            "LIVE_CONTROL_VERIFIED_NE_OWNER_VALUE_VERIFIED"
        ),
    }
