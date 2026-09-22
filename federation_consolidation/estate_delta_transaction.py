from __future__ import annotations

import base64
import codecs
from datetime import datetime
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence
import unicodedata
from urllib.parse import quote, unquote


SCHEMA = "FEDERATION-ESTATE-DELTA-TRANSACTION-1"
REGISTER_ID = "FEDERATION-ESTATE-DELTA-REGISTER"
PUBLIC_SCHEMA = "FEDERATION-ESTATE-DELTA-REGISTER-PUBLIC-1"
ROUTE_CATALOG_SCHEMA = "FEDERATION-ESTATE-OBSERVATION-ROUTES-1"
CANONICALIZATION = "UTF8_JSON_SORT_KEYS_COMPACT_SEPARATORS_ENSURE_ASCII_FALSE"
EXPECTED_SCHEMA_CANONICAL_SHA256 = "e90bd53e990482c4c283be5afc48e3a894dbb519016b400c051ad8ece49f91c0"
BOUNDED_SCOPE_CLAIM_TEXT = (
    "Bounded census of the connected and callable Federation estate at the observation time; "
    "inaccessible accounts, unsupported recursion and unproven provider execution remain "
    "outside the claim."
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
OPAQUE_PRIVATE_ID = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{33,}(?![A-Za-z0-9_-])")
UTC_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$")
SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{2,127}$")
TRANSACTION_ID = re.compile(r"^FEDERATION-ESTATE-(?:CENSUS|DELTA|CORRECTION)-[0-9]{8}-[0-9]{3}$")
MISSION_ID = re.compile(r"^FEDERATION-ESTATE-[A-Z0-9-]{3,64}-[0-9]{8}$")
BASELINE_ID = re.compile(r"^EFSL-[0-9]{8}-[0-9]{3}$")
SOURCE_ID = re.compile(r"^SRC:[A-Z][A-Z0-9-]{2,47}-[0-9]{8}$")
SNAPSHOT_ID = re.compile(r"^SNAP:[A-Z][A-Z0-9-]{2,63}-[0-9]{3}$")
SUBJECT_ID = re.compile(r"^(?:SURFACE|PROVIDER):[A-Z][A-Z0-9-]{1,63}$")
BOUNDARY_ID = re.compile(r"^BOUNDARY:[A-Z][A-Z0-9-]{1,79}$")
CONTRADICTION_ID = re.compile(r"^CONTRADICTION:[A-Z][A-Z0-9-]{1,79}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"https://(?:docs|drive)\.google\.com/(?:[^\s\"']+/){1,4}[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"https://(?:(?:docs|drive)\.google\.com|drive\.usercontent\.google\.com)/"
        r"[^\s\"']*[?&](?:id|file_?id)=[A-Za-z0-9_-]{20,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"https://(?:(?:docs|drive)\.google\.com|drive\.usercontent\.google\.com)/"
        r"[^\s\"']*(?:%3f|%26)(?:id|file_?id)%3d[A-Za-z0-9_-]{20,}",
        re.IGNORECASE,
    ),
)
PROHIBITED_KEYS = {
    "token", "secret", "password", "api_key", "credential_value", "private_key",
    "drive_id", "spreadsheet_id", "queue_id", "project_id", "project_number",
    "service_account", "email", "message_id", "account_id", "private_locator",
}
EVIDENCE_RANK = {
    "PROVIDER_NATIVE_READBACK": 50,
    "CONNECTED_APP_READBACK": 40,
    "REPOSITORY_EXACT_HEAD": 40,
    "PRIVATE_CORPUS_CENSUS": 30,
    "DERIVED_ABSENCE_OF_REQUIRED_PROOF": 10,
    "HISTORICAL_CLAIM": 0,
}
INPUT_SOURCE_CLASSES = {
    "DERIVED_CENSUS_MANIFEST", "FIDELITY_REPORT", "BOUNDED_CLAIM_GATE",
    "TOTALITY_REJECTION_GATE", "DRIFT_READBACK",
}
INPUT_LOCATOR_STATES = {
    "BUNDLED_IMMUTABLE", "PRIVATE_POINTER_WITHHELD", "SESSION_ARTIFACT_NOT_PUBLISHED",
}
INPUT_PROOF_STATES = {"READBACK_VERIFIED", "DERIVED_VERIFIED", "HISTORICAL_UNRESOLVED"}
SNAPSHOT_PROOF_STATES = {
    "READBACK_VERIFIED", "ACTIVE_SCOPED", "PARTIAL_PROVEN", "UNVERIFIED",
    "HISTORICAL_UNRESOLVED",
}
PROJECTION_PROOF_STATES = {"READBACK_VERIFIED", "ACTIVE_SCOPED", "PARTIAL_PROVEN", "UNVERIFIED"}
SURFACE_LABELS = {
    "GITHUB": "GitHub",
    "GOOGLE_DRIVE": "Google Drive",
    "LIBRARY": "Library",
    "GMAIL": "Gmail",
    "CLOUD_CONTROL": "Cloud control",
    "CAPABILITY_FABRIC": "Capability Fabric",
    "CANVA": "Canva",
    "SITES": "Sites",
    "AUTOMATIONS": "Automations",
    "GEMINI": "Gemini",
}
EVIDENCE_PROOF_STATES = {
    "PROVIDER_NATIVE_READBACK": {"READBACK_VERIFIED"},
    "CONNECTED_APP_READBACK": {"READBACK_VERIFIED", "ACTIVE_SCOPED", "PARTIAL_PROVEN"},
    "REPOSITORY_EXACT_HEAD": {"READBACK_VERIFIED"},
    "PRIVATE_CORPUS_CENSUS": {"READBACK_VERIFIED", "PARTIAL_PROVEN"},
    "DERIVED_ABSENCE_OF_REQUIRED_PROOF": {"UNVERIFIED", "PARTIAL_PROVEN"},
    "HISTORICAL_CLAIM": {"HISTORICAL_UNRESOLVED"},
}
STATE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
PUBLIC_POINTER_TRUTH_BOUNDARY = (
    "This source contract locates and validates a future external immutable census transaction. "
    "It is not the transaction, does not prove publication or provider execution, and must remain "
    "PREPARED until an approved external artifact is written and independently read back."
)
PUBLIC_POINTER_RULES = {
    "append_only": True,
    "correction_events_replace_rewrites": True,
    "latest_provider_native_readback_wins": True,
    "historical_claims_retained_as_lineage": True,
    "unresolved_boundaries_required_for_partial_state": True,
    "totality_inference_allowed": False,
    "provider_authority_inferred_from_storage": False,
}
REGISTRY_COLLISION_NOTE = (
    "Two private continuity registry projections disagree; both remain preserved, "
    "unselected and non-authoritative pending governed readback."
)
REGISTRY_COLLISION_BUILD = {
    "build_id": "AO-CRA-FEDREG-COLLISION-001",
    "state": "UNRESOLVED_ENGINEERING_BUILD",
    "owner_engine": "FORMATION_ENGINE",
    "private_projection_aliases": [
        "FEDERATION_CONTINUITY_REGISTRY_A",
        "FEDERATION_CONTINUITY_REGISTRY_B",
    ],
    "private_projection_version_state": "WITHHELD_PENDING_AUTHORIZED_READBACK",
    "private_projection_hash_state": "WITHHELD_PENDING_AUTHORIZED_READBACK",
    "disagreement_state": "CONTENT_AND_SUPERSESSION_UNRESOLVED",
    "desired_capability": "Resolve one current continuity projection without deleting or trusting either candidate by presence alone.",
    "dependencies": [
        "CURRENT_LOGICAL_HASH_READBACK",
        "PRIVATE_ALIAS_RESOLUTION",
        "SUPERSESSION_EVIDENCE",
    ],
    "workaround": "QUARANTINE_BOTH_NO_SELECTION",
    "implementation_tasks": [
        "Resolve both private aliases in one authorized read-only session.",
        "Compare versions, logical hashes, scope and supersession evidence.",
        "Preserve the non-selected projection and publish only a public-safe resolution state.",
    ],
    "security_privacy_limits": [
        "NO_PRIVATE_POINTER_IN_PUBLIC_SOURCE",
        "NO_SECRET_VALUE_ACCESS",
        "NO_TRUST_TRANSFER",
    ],
    "tests": [
        "BOTH_ALIASES_READ_BACK",
        "LOGICAL_HASHES_RECOMPUTED",
        "NON_SELECTED_PROJECTION_PRESERVED",
    ],
    "acceptance_criteria": [
        "One projection is selected only by current source or explicit supersession evidence.",
        "The rejected projection remains preserved and queryable.",
        "No route, provider or execution authority is inherited from resolution.",
    ],
    "next_executable_action": "Run an authorized A0 read-only logical-hash comparison through the private alias resolver.",
    "capability_change_trigger": "Both aliases and current logical hashes are available in one governed read-only session.",
    "closure_proof": "Current source-native readback or explicit owner supersession selects one projection while proving preservation of the other.",
    "authority_ceiling": "A0",
}
CFBE_COMPATIBILITY = {
    "reference_state": "REFERENCE_ONLY_UNMERGED",
    "reference_pr": 618,
    "reference_head_sha": "90bfb9b43a9d1c2abade2b8269339342a3357d5a",
    "estate_snapshot_schema": "CFBE-ACF-ESTATE-SNAPSHOT-V1",
    "compiled_intent_schema": "CFBE-ACF-COMPILED-INTENT-V1",
    "provider_projection_state": "SOURCE_REGISTERED_NOT_RUNTIME_BOUND",
    "static_route_hash_is_runtime_fingerprint": False,
    "proof_receipt_inherited": False,
}
ROUTE_DISCOVERY_ADAPTER = {
    "source_path": "federation_resource_discovery.py",
    "discovery_order": ["capabilities", "commands", "source", "receipts"],
    "binding_state": "ADAPTER_REQUIRED_NOT_RUNTIME_BOUND",
    "route_exhaustion_inherited": False,
    "provider_execution_inherited": False,
    "proof_receipt_inherited": False,
}
PUBLIC_CURRENT_TRANSACTION_CONTRACT = {
    "required_fields": [
        "transaction_id", "sequence", "observed_at", "canonical_status", "event_hash", "availability",
    ],
    "allowed_availability": "APPROVED_EXTERNAL_IMMUTABLE_EVIDENCE_PLANE",
}
ROUTE_CONTRACTS = {
    "FEDERATION_CENSUS_A0": {
        "intents": ["estate census", "federation census", "federation estate census"],
        "capability": "federation-census",
        "proof_action_id": "FEDERATION-CENSUS-A0-READBACK",
        "required_readbacks": [
            "BOUNDED_SCOPE_DECLARATION", "PAGINATION_CLOSURE_OR_BOUNDARY",
            "SOURCE_HASHES", "UNRESOLVED_BOUNDARIES",
        ],
    },
    "PROVIDER_OBSERVATION_A0": {
        "intents": [
            "provider observation", "provider status observation", "provider verification observation",
        ],
        "capability": "provider-observation",
        "proof_action_id": "PROVIDER-OBSERVATION-A0-READBACK",
        "required_readbacks": [
            "AUTHENTICATION_STATE", "CONFIGURATION_STATE", "PROVIDER_NATIVE_READBACK",
            "SEMANTIC_EXECUTION_STATE", "TRANSPORT_STATE",
        ],
    },
}
MANIFEST_SUBJECTS = {
    "github": {"SURFACE:GITHUB"},
    "googleDrive": {"SURFACE:GOOGLE-DRIVE"},
    "library": {"SURFACE:LIBRARY"},
    "gmail": {"SURFACE:GMAIL"},
    "cloudControl": {
        "SURFACE:CLOUD-ESTATE", "SURFACE:CLOUD-OPERATOR", "SURFACE:GEMINI",
        "SURFACE:OWNER-OAUTH-APPS-SCRIPT", "SURFACE:WIF",
    },
    "capabilityFabric": {"SURFACE:CAPABILITY-FABRIC"},
    "canva": {"SURFACE:CANVA"},
    "sites": {"SURFACE:SITES"},
    "automations": {"SURFACE:AUTOMATIONS"},
}
SUBJECT_PROOF_HOLD = {
    "SURFACE:AUTOMATIONS": ("PARTIAL_PROVEN", True),
    "SURFACE:CANVA": ("ACTIVE_SCOPED", False),
    "SURFACE:CAPABILITY-FABRIC": ("PARTIAL_PROVEN", True),
    "SURFACE:CLOUD-ESTATE": ("PARTIAL_PROVEN", True),
    "SURFACE:CLOUD-OPERATOR": ("READBACK_VERIFIED", True),
    "SURFACE:GEMINI": ("UNVERIFIED", True),
    "SURFACE:GITHUB": ("READBACK_VERIFIED", True),
    "SURFACE:GMAIL": ("PARTIAL_PROVEN", True),
    "SURFACE:GOOGLE-DRIVE": ("PARTIAL_PROVEN", True),
    "SURFACE:LIBRARY": ("READBACK_VERIFIED", True),
    "SURFACE:OWNER-OAUTH-APPS-SCRIPT": ("READBACK_VERIFIED", False),
    "SURFACE:SITES": ("READBACK_VERIFIED", False),
    "SURFACE:WIF": ("READBACK_VERIFIED", True),
}
SUBJECT_EVIDENCE_CLASS = {
    "SURFACE:AUTOMATIONS": "CONNECTED_APP_READBACK",
    "SURFACE:CANVA": "CONNECTED_APP_READBACK",
    "SURFACE:CAPABILITY-FABRIC": "CONNECTED_APP_READBACK",
    "SURFACE:CLOUD-ESTATE": "CONNECTED_APP_READBACK",
    "SURFACE:CLOUD-OPERATOR": "PROVIDER_NATIVE_READBACK",
    "SURFACE:GEMINI": "DERIVED_ABSENCE_OF_REQUIRED_PROOF",
    "SURFACE:GITHUB": "REPOSITORY_EXACT_HEAD",
    "SURFACE:GMAIL": "CONNECTED_APP_READBACK",
    "SURFACE:GOOGLE-DRIVE": "PRIVATE_CORPUS_CENSUS",
    "SURFACE:LIBRARY": "CONNECTED_APP_READBACK",
    "SURFACE:OWNER-OAUTH-APPS-SCRIPT": "CONNECTED_APP_READBACK",
    "SURFACE:SITES": "CONNECTED_APP_READBACK",
    "SURFACE:WIF": "PROVIDER_NATIVE_READBACK",
}
SUBJECT_SURFACE = {
    "SURFACE:AUTOMATIONS": "AUTOMATIONS",
    "SURFACE:CANVA": "CANVA",
    "SURFACE:CAPABILITY-FABRIC": "CAPABILITY_FABRIC",
    "SURFACE:CLOUD-ESTATE": "CLOUD_CONTROL",
    "SURFACE:CLOUD-OPERATOR": "CLOUD_CONTROL",
    "SURFACE:GEMINI": "GEMINI",
    "SURFACE:GITHUB": "GITHUB",
    "SURFACE:GMAIL": "GMAIL",
    "SURFACE:GOOGLE-DRIVE": "GOOGLE_DRIVE",
    "SURFACE:LIBRARY": "LIBRARY",
    "SURFACE:OWNER-OAUTH-APPS-SCRIPT": "CLOUD_CONTROL",
    "SURFACE:SITES": "SITES",
    "SURFACE:WIF": "CLOUD_CONTROL",
}
SUBJECT_INPUT_SOURCE_CLASSES = {
    subject_id: {"DERIVED_CENSUS_MANIFEST"} for subject_id in SUBJECT_SURFACE
}
SUBJECT_INPUT_SOURCE_CLASSES["SURFACE:WIF"] = {
    "DERIVED_CENSUS_MANIFEST", "DRIFT_READBACK",
}
SUBJECT_BOUNDARY_IDS = {
    "SURFACE:AUTOMATIONS": {"BOUNDARY:AUTOMATION-REGISTRY-TOTALITY"},
    "SURFACE:CANVA": {"BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS"},
    "SURFACE:CAPABILITY-FABRIC": {"BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS"},
    "SURFACE:CLOUD-ESTATE": {"BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS"},
    "SURFACE:CLOUD-OPERATOR": {"BOUNDARY:OPERATOR-ACTION-SEMANTICS"},
    "SURFACE:GEMINI": {"BOUNDARY:DIRECT-GEMINI"},
    "SURFACE:GITHUB": {
        "BOUNDARY:PROVIDER-NATIVE-BRANCH-PROTECTION",
        "BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS",
        "BOUNDARY:WIF-REPOSITORY-TRUST",
    },
    "SURFACE:GMAIL": {"BOUNDARY:DIRECT-GEMINI"},
    "SURFACE:GOOGLE-DRIVE": {
        "BOUNDARY:EXACT-EFSL-LEDGER", "BOUNDARY:WHOLE-DRIVE-RECURSION",
    },
    "SURFACE:LIBRARY": {"BOUNDARY:WHOLE-DRIVE-RECURSION"},
    "SURFACE:OWNER-OAUTH-APPS-SCRIPT": set(),
    "SURFACE:SITES": {"BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS"},
    "SURFACE:WIF": {"BOUNDARY:WIF-REPOSITORY-TRUST"},
}
SUBJECT_SNAPSHOT_ID = {
    subject_id: "SNAP:" + subject_id.removeprefix("SURFACE:") + "-001"
    for subject_id in SUBJECT_SURFACE
}
GENESIS_INPUT_LABELS = {
    "BOUNDED_CLAIM_GATE": "BOUNDED-CLAIM",
    "DERIVED_CENSUS_MANIFEST": "CENSUS-MANIFEST",
    "DRIFT_READBACK": "DRIFT-READBACK",
    "FIDELITY_REPORT": "OIFA-FIDELITY",
    "TOTALITY_REJECTION_GATE": "TOTALITY-GATE",
}
BOUNDARY_CONTRACTS = {
    "BOUNDARY:AUTOMATION-REGISTRY-TOTALITY": {
        "description": "Automation registry totality semantics",
        "closure_evidence": "Provider-native exhaustive automation registry readback with total-count semantics.",
    },
    "BOUNDARY:DIRECT-GEMINI": {
        "description": "Direct Gemini provider authentication, model, quota, usage and latency",
        "closure_evidence": "Provider-native authenticated model identity, nonce-bound semantic output, quota and usage readback, and measured latency.",
    },
    "BOUNDARY:EXACT-EFSL-LEDGER": {
        "description": "Exact EFSL JSON ledger location and fresh hash",
        "closure_evidence": "Exact immutable ledger readback and current content hash.",
    },
    "BOUNDARY:OPERATOR-ACTION-SEMANTICS": {
        "description": "Authenticated operator action semantics",
        "closure_evidence": "Authenticated zero-effect dry-run action with semantic response readback.",
    },
    "BOUNDARY:PROVIDER-NATIVE-BRANCH-PROTECTION": {
        "description": "Provider-native branch protection",
        "closure_evidence": "Current repository ruleset and branch-protection readback.",
    },
    "BOUNDARY:SURFACES-OUTSIDE-CONNECTED-ACCOUNTS": {
        "description": "Surfaces outside connected or accessible accounts",
        "closure_evidence": "Authorized account inventory and closed pagination per provider.",
    },
    "BOUNDARY:WHOLE-DRIVE-RECURSION": {
        "description": "Whole-Drive zero-keyword recursive census",
        "closure_evidence": "Authorized recursive Drive traversal with pagination closure.",
    },
    "BOUNDARY:WIF-REPOSITORY-TRUST": {
        "description": "WIF token exchange and repository trust",
        "closure_evidence": "Provider-native pool, provider, binding, repository trust and successful exchange readback.",
    },
}
MANIFEST_METRIC_PATHS = {
    ("SURFACE:GITHUB", "INSTALLED_ACCOUNTS"): ("surfaces", "github", "installedAccounts"),
    ("SURFACE:GITHUB", "ACCESSIBLE_REPOSITORIES"): ("surfaces", "github", "accessibleRepositories"),
    ("SURFACE:GITHUB", "REPOSITORY_PAGINATION_CLOSED"): ("surfaces", "github", "repositoryPaginationClosed"),
    ("SURFACE:GITHUB", "MAIN_COMMIT"): ("surfaces", "github", "mainCommit"),
    ("SURFACE:GITHUB", "TREE_SHA"): ("surfaces", "github", "tree"),
    ("SURFACE:GITHUB", "TREE_TRUNCATED"): ("surfaces", "github", "treeTruncated"),
    ("SURFACE:GITHUB", "TREE_ITEMS"): ("surfaces", "github", "treeItems"),
    ("SURFACE:GITHUB", "BLOBS"): ("surfaces", "github", "blobs"),
    ("SURFACE:GITHUB", "TREES"): ("surfaces", "github", "trees"),
    ("SURFACE:GITHUB", "SUBMODULES"): ("surfaces", "github", "submodules"),
    ("SURFACE:GITHUB", "TOP_LEVEL_SYSTEM_DIRECTORIES"): ("surfaces", "github", "topLevelSystemDirectories"),
    ("SURFACE:GITHUB", "TRACKED_WORKFLOW_YAMLS"): ("surfaces", "github", "trackedWorkflowYamls"),
    ("SURFACE:GITHUB", "REGISTERED_WORKFLOWS"): ("surfaces", "github", "registeredWorkflows"),
    ("SURFACE:GITHUB", "ACTIVE_WORKFLOWS"): ("surfaces", "github", "activeWorkflows"),
    ("SURFACE:GITHUB", "MANUALLY_DISABLED_WORKFLOWS"): ("surfaces", "github", "manuallyDisabledWorkflows"),
    ("SURFACE:GITHUB", "REGISTERED_BUT_DELETED_WORKFLOW_PATHS"): ("surfaces", "github", "registeredButDeletedWorkflowPaths"),
    ("SURFACE:GITHUB", "OPEN_ISSUES"): ("surfaces", "github", "openIssues"),
    ("SURFACE:GITHUB", "OPEN_PULL_REQUESTS"): ("surfaces", "github", "openPullRequests"),
    ("SURFACE:GITHUB", "RELEASES"): ("surfaces", "github", "releases"),
    ("SURFACE:GITHUB", "TAGS"): ("surfaces", "github", "tags"),
    ("SURFACE:GITHUB", "LEAK_GUARD"): ("surfaces", "github", "exactHeadControls", "leakGuard"),
    ("SURFACE:GITHUB", "BUBBLES_COMMAND_BUS"): ("surfaces", "github", "exactHeadControls", "bubblesCommandBus"),
    ("SURFACE:GITHUB", "PHOENIX_EMERGENCY_FREEZE"): ("surfaces", "github", "exactHeadControls", "phoenixEmergencyFreeze"),
    ("SURFACE:GITHUB", "FEDERATION_AIRLOCK"): ("surfaces", "github", "exactHeadControls", "federationAirlock"),
    ("SURFACE:GITHUB", "PROVIDER_ADMISSION_STATUS"): ("surfaces", "github", "providerAdmission", "status"),
    ("SURFACE:GITHUB", "PROVIDER_ADMISSION_REASON"): ("surfaces", "github", "providerAdmission", "reason"),
    ("SURFACE:GITHUB", "PROVIDER_CALLS"): ("surfaces", "github", "providerAdmission", "providerCalls"),
    ("SURFACE:GOOGLE-DRIVE", "CLOSED_NAMED_SEARCHES"): ("surfaces", "googleDrive", "closedNamedSearches"),
    ("SURFACE:GOOGLE-DRIVE", "FEDERATION_OMEGA_STABLE_IDS"): ("surfaces", "googleDrive", "federationOmegaStableIds"),
    ("SURFACE:GOOGLE-DRIVE", "SECONDARY_BRAIN_STABLE_IDS"): ("surfaces", "googleDrive", "secondaryBrainStableIds"),
    ("SURFACE:GOOGLE-DRIVE", "POST_SNAPSHOT_CHANGED_STABLE_IDS"): ("surfaces", "googleDrive", "postSnapshotChangedStableIds"),
    ("SURFACE:GOOGLE-DRIVE", "POST_SNAPSHOT_CREATED_STABLE_IDS"): ("surfaces", "googleDrive", "postSnapshotCreatedStableIds"),
    ("SURFACE:GOOGLE-DRIVE", "OLDER_STABLE_IDS_MODIFIED_POST_SNAPSHOT"): ("surfaces", "googleDrive", "olderStableIdsModifiedPostSnapshot"),
    ("SURFACE:GOOGLE-DRIVE", "LINEAGE_SIGNAL_TITLES"): ("surfaces", "googleDrive", "lineageSignalTitles"),
    ("SURFACE:GOOGLE-DRIVE", "EXACT_EFSL_JSON_REDISCOVERED"): ("surfaces", "googleDrive", "exactEfslJsonRediscovered"),
    ("SURFACE:GOOGLE-DRIVE", "WHOLE_DRIVE_RECURSION_RUN"): ("surfaces", "googleDrive", "wholeDriveRecursionRun"),
    ("SURFACE:GOOGLE-DRIVE", "SURFACE_INDEX_REVISION"): ("surfaces", "googleDrive", "surfaceIndexRevision"),
    ("SURFACE:GOOGLE-DRIVE", "SURFACE_INDEX_EXPANDED_ROWS"): ("surfaces", "googleDrive", "surfaceIndexExpandedRows"),
    ("SURFACE:LIBRARY", "LIBRARY_PAGINATION_CLOSED"): ("surfaces", "library", "ownedListingPaginationClosed"),
    ("SURFACE:LIBRARY", "PAGES"): ("surfaces", "library", "pages"),
    ("SURFACE:LIBRARY", "ITEMS"): ("surfaces", "library", "items"),
    ("SURFACE:LIBRARY", "FOLDERS"): ("surfaces", "library", "folders"),
    ("SURFACE:LIBRARY", "FILES"): ("surfaces", "library", "files"),
    ("SURFACE:LIBRARY", "RELEVANT_CONTINUITY_SEARCH_RESULTS"): ("surfaces", "library", "relevantContinuitySearchResults"),
    ("SURFACE:LIBRARY", "MOUNTED_GOOGLE_DRIVE_RECURSION_SUPPORTED"): ("surfaces", "library", "mountedGoogleDriveRecursionSupported"),
    ("SURFACE:GMAIL", "LINEAGE_SWEEP"): ("surfaces", "gmail", "lineageSweep"),
    ("SURFACE:GMAIL", "DIRECT_GEMINI_SUCCESS_RECEIPT_FOUND"): ("surfaces", "gmail", "directGeminiSuccessReceiptFound"),
    ("SURFACE:GMAIL", "CURRENT_FAILURE_CLUSTER_OBSERVED"): ("surfaces", "gmail", "currentFailureClusterObserved"),
    ("SURFACE:GMAIL", "BACKUP_EMAIL_WITH_EXECUTABLE_ARCHIVE_BLOCKED"): ("surfaces", "gmail", "backupEmailWithExecutableArchiveBlocked"),
    ("SURFACE:CLOUD-OPERATOR", "OPERATOR_HEALTH"): ("surfaces", "cloudControl", "operatorHealth"),
    ("SURFACE:CLOUD-OPERATOR", "OPERATOR_SERVICE"): ("surfaces", "cloudControl", "operatorService"),
    ("SURFACE:OWNER-OAUTH-APPS-SCRIPT", "ARCHITRON_COMMANDS_LAST_ROW"): ("surfaces", "cloudControl", "architronCommandsLastRow"),
    ("SURFACE:OWNER-OAUTH-APPS-SCRIPT", "ARCHITRON_COMMANDS_LAST_ROW_STATUS"): ("surfaces", "cloudControl", "architronCommandsLastRowStatus"),
    ("SURFACE:OWNER-OAUTH-APPS-SCRIPT", "CLOUDOPS_LOG_LAST_ROW"): ("surfaces", "cloudControl", "cloudOpsLogLastRow"),
    ("SURFACE:OWNER-OAUTH-APPS-SCRIPT", "CLOUDOPS_TRIGGER_AUTH_MODE"): ("surfaces", "cloudControl", "cloudOpsTriggerAuthMode"),
    ("SURFACE:OWNER-OAUTH-APPS-SCRIPT", "CLOUDOPS_TRIGGER_PENDING"): ("surfaces", "cloudControl", "cloudOpsTriggerPending"),
    ("SURFACE:CLOUD-ESTATE", "CLOUD_ESTATE_PROJECTS"): ("surfaces", "cloudControl", "cloudEstateProjects"),
    ("SURFACE:CLOUD-ESTATE", "CLOUD_ESTATE_API_CALLS"): ("surfaces", "cloudControl", "cloudEstateApiCalls"),
    ("SURFACE:CLOUD-ESTATE", "CLOUD_ESTATE_CURRENT_RECEIPT_ROWS"): ("surfaces", "cloudControl", "cloudEstateCurrentReceiptRows"),
    ("SURFACE:CLOUD-ESTATE", "CLOUD_ESTATE_SCOPED_BLOCKERS"): ("surfaces", "cloudControl", "cloudEstateScopedBlockers"),
    ("SURFACE:WIF", "WIF_POOL_STATE"): ("surfaces", "cloudControl", "wifPool"),
    ("SURFACE:WIF", "WIF_PROVIDER_STATE"): ("surfaces", "cloudControl", "wifProvider"),
    ("SURFACE:WIF", "WORKLOAD_IDENTITY_USER_BOUND"): ("surfaces", "cloudControl", "workloadIdentityUserBound"),
    ("SURFACE:WIF", "TOKEN_EXCHANGE_PERFORMED"): ("surfaces", "cloudControl", "tokenExchangePerformed"),
    ("SURFACE:WIF", "PROVIDER_RECEIPT_TAB_EXISTS"): ("surfaces", "cloudControl", "providerReceiptTabExists"),
    ("SURFACE:WIF", "DIRECT_GEMINI_CANARY_INSTALLED"): ("surfaces", "cloudControl", "directGeminiCanaryInstalled"),
    ("SURFACE:GEMINI", "DIRECT_GEMINI_CANARY_INSTALLED"): ("surfaces", "cloudControl", "directGeminiCanaryInstalled"),
    ("SURFACE:GEMINI", "DIRECT_GEMINI_SUCCESS_RECEIPT_FOUND"): ("surfaces", "gmail", "directGeminiSuccessReceiptFound"),
    ("SURFACE:CAPABILITY-FABRIC", "EXECUTOR_SKILLS"): ("surfaces", "capabilityFabric", "executorSkills"),
    ("SURFACE:CAPABILITY-FABRIC", "ORCHESTRATOR_SKILLS"): ("surfaces", "capabilityFabric", "orchestratorSkills"),
    ("SURFACE:CAPABILITY-FABRIC", "CALLABLE_TOOL_CONTRACTS"): ("surfaces", "capabilityFabric", "callableToolContracts"),
    ("SURFACE:CAPABILITY-FABRIC", "CACHED_SKILLS"): ("surfaces", "capabilityFabric", "cachedSkills"),
    ("SURFACE:CAPABILITY-FABRIC", "CACHED_TOOL_CONTRACTS"): ("surfaces", "capabilityFabric", "cachedToolContracts"),
    ("SURFACE:CAPABILITY-FABRIC", "CACHED_REGISTRY_CURRENT"): ("surfaces", "capabilityFabric", "cachedRegistryCurrent"),
    ("SURFACE:CAPABILITY-FABRIC", "FEDERATION_CENSUS_ROUTE_EXISTS"): ("surfaces", "capabilityFabric", "federationCensusRouteExists"),
    ("SURFACE:CAPABILITY-FABRIC", "PROVIDER_OBSERVATION_ROUTE_EXISTS"): ("surfaces", "capabilityFabric", "providerObservationRouteExists"),
    ("SURFACE:CANVA", "SOVARA_SEARCH_RESULTS"): ("surfaces", "canva", "sovaraSearchResults"),
    ("SURFACE:CANVA", "FEDERATION_OMEGA_DESIGN_RESULTS"): ("surfaces", "canva", "federationOmegaDesignResults"),
    ("SURFACE:CANVA", "BRAND_KITS_OBSERVED"): ("surfaces", "canva", "brandKitsObserved"),
    ("SURFACE:SITES", "OWNED_SITES"): ("surfaces", "sites", "ownedSites"),
    ("SURFACE:SITES", "SITES_PAGINATION_CLOSED"): ("surfaces", "sites", "paginationClosed"),
    ("SURFACE:AUTOMATIONS", "BOUNDED_LIST_RESULT_COUNT"): ("surfaces", "automations", "boundedListResultCount"),
    ("SURFACE:AUTOMATIONS", "REPORTED_COMPLETED_COUNT"): ("surfaces", "automations", "reportedCompletedCount"),
    ("SURFACE:AUTOMATIONS", "REPORTED_PAUSED_COUNT"): ("surfaces", "automations", "reportedPausedCount"),
    ("SURFACE:AUTOMATIONS", "AUTOMATION_TOTALITY_CLAIMED"): ("surfaces", "automations", "totalityClaimed"),
}
SAFE_METRIC_NAMES = {
    "ACCESSIBLE_REPOSITORIES", "ACTIVE_WORKFLOWS", "ARCHITRON_COMMANDS_LAST_ROW",
    "ARCHITRON_COMMANDS_LAST_ROW_STATUS",
    "AUTOMATION_TOTALITY_CLAIMED", "BACKUP_EMAIL_WITH_EXECUTABLE_ARCHIVE_BLOCKED",
    "BLOBS", "BOUNDED_LIST_RESULT_COUNT", "BRAND_KITS_OBSERVED", "BUBBLES_COMMAND_BUS",
    "CACHED_REGISTRY_CURRENT", "CACHED_SKILLS", "CACHED_TOOL_CONTRACTS",
    "CALLABLE_TOOL_CONTRACTS", "CLOSED_NAMED_SEARCHES", "CLOUDOPS_LOG_LAST_ROW",
    "CLOUDOPS_TRIGGER_AUTH_MODE", "CLOUDOPS_TRIGGER_PENDING", "CLOUD_ESTATE_API_CALLS",
    "CLOUD_ESTATE_CURRENT_RECEIPT_ROWS",
    "CLOUD_ESTATE_PROJECTS", "CLOUD_ESTATE_SCOPED_BLOCKERS", "CURRENT_FAILURE_CLUSTER_OBSERVED",
    "DIRECT_CANARY_INSTALLED", "DIRECT_GEMINI_CANARY_INSTALLED",
    "DIRECT_GEMINI_SUCCESS_RECEIPT_FOUND", "EXACT_EFSL_JSON_REDISCOVERED", "EXECUTOR_SKILLS",
    "FEDERATION_AIRLOCK", "FEDERATION_CENSUS_ROUTE_EXISTS", "FEDERATION_OMEGA_DESIGN_RESULTS",
    "FEDERATION_OMEGA_STABLE_IDS", "FILES", "FOLDERS", "INSTALLED_ACCOUNTS", "ITEMS", "LEAK_GUARD",
    "LIBRARY_PAGINATION_CLOSED", "LINEAGE_SIGNAL_TITLES", "LINEAGE_SWEEP", "MAIN_COMMIT",
    "MANUALLY_DISABLED_WORKFLOWS", "MOUNTED_GOOGLE_DRIVE_RECURSION_SUPPORTED",
    "OLDER_STABLE_IDS_MODIFIED_POST_SNAPSHOT", "OPEN_ISSUES", "OPEN_PULL_REQUESTS",
    "OPERATOR_HEALTH", "OPERATOR_SERVICE", "ORCHESTRATOR_SKILLS", "OWNED_SITES", "PAGES",
    "PHOENIX_EMERGENCY_FREEZE", "POOL_PRESENT", "POST_SNAPSHOT_CHANGED_STABLE_IDS",
    "POST_SNAPSHOT_CREATED_STABLE_IDS", "PROVIDER_ADMISSION_REASON", "PROVIDER_ADMISSION_STATUS",
    "PROVIDER_CALLS", "PROVIDER_OBSERVATION_ROUTE_EXISTS", "PROVIDER_PRESENT",
    "PROVIDER_RECEIPT_TAB_EXISTS", "REGISTERED_BUT_DELETED_WORKFLOW_PATHS",
    "REPOSITORY_PAGINATION_CLOSED",
    "REGISTERED_WORKFLOWS", "RELEASES", "RELEVANT_CONTINUITY_SEARCH_RESULTS",
    "REPORTED_COMPLETED_COUNT", "REPORTED_PAUSED_COUNT", "SECONDARY_BRAIN_STABLE_IDS",
    "SITES_PAGINATION_CLOSED", "SOVARA_SEARCH_RESULTS", "SUBMODULES", "SURFACE_INDEX_EXPANDED_ROWS",
    "SURFACE_INDEX_REVISION", "TAGS", "TOKEN_EXCHANGE_PERFORMED", "TOP_LEVEL_SYSTEM_DIRECTORIES",
    "TRACKED_WORKFLOW_YAMLS", "TREE_ITEMS", "TREE_SHA", "TREE_TRUNCATED", "TREES",
    "WHOLE_DRIVE_RECURSION_RUN", "WIF_POOL_STATE", "WIF_PROVIDER_STATE",
    "WORKLOAD_IDENTITY_USER_BOUND",
}


class EstateDeltaError(ValueError):
    """Raised when an estate transaction is structurally or semantically invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def bounded_truth_boundary(observed_at: str) -> str:
    return (
        "This transaction proves only the named connected and callable bounded scope at "
        f"{observed_at}; it is not whole-estate, runtime-activation or "
        "provider-execution proof."
    )


def _decoded_text_forms(value: str) -> list[str]:
    initial = unicodedata.normalize("NFKC", value)
    forms = [initial]
    frontier = [initial]
    for _ in range(4):
        next_frontier: list[str] = []
        for current in frontier:
            candidates = [unicodedata.normalize("NFKC", unquote(current))]
            if re.fullmatch(r"[A-Za-z0-9_+/=-]{8,}", current):
                try:
                    padded = current + "=" * (-len(current) % 4)
                    decoded_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
                    decoded_text = unicodedata.normalize("NFKC", decoded_bytes.decode("utf-8"))
                    if decoded_text and all(character.isprintable() for character in decoded_text):
                        candidates.append(decoded_text)
                except (ValueError, UnicodeDecodeError):
                    pass
            if re.fullmatch(r"[A-Z2-7=]{8,}", current):
                try:
                    padded = current + "=" * (-len(current) % 8)
                    decoded_bytes = base64.b32decode(padded.encode("ascii"), casefold=True)
                    decoded_text = unicodedata.normalize("NFKC", decoded_bytes.decode("utf-8"))
                    if decoded_text and all(character.isprintable() for character in decoded_text):
                        candidates.append(decoded_text)
                except (ValueError, UnicodeDecodeError):
                    pass
            if len(current) % 2 == 0 and re.fullmatch(r"[0-9A-Fa-f]{8,}", current):
                try:
                    decoded_text = unicodedata.normalize(
                        "NFKC", bytes.fromhex(current).decode("utf-8")
                    )
                    if decoded_text and all(character.isprintable() for character in decoded_text):
                        candidates.append(decoded_text)
                except (ValueError, UnicodeDecodeError):
                    pass
            for candidate in candidates:
                if candidate not in forms:
                    forms.append(candidate)
                    next_frontier.append(candidate)
        if not next_frontier:
            break
        frontier = next_frontier
    return forms


def _iter_text_values(value: Any, path: str = "transaction"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _iter_text_values(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            yield from _iter_text_values(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    leading_zeroes = len(value) - len(value.lstrip(b"\0"))
    return "1" * leading_zeroes + (encoded or "1")


def _known_private_text_forms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value)
    raw = normalized.encode("utf-8")
    base64_standard = base64.b64encode(raw).decode("ascii")
    base64_urlsafe = base64.urlsafe_b64encode(raw).decode("ascii")
    base32_value = base64.b32encode(raw).decode("ascii")
    forms = {
        normalized,
        normalized[::-1],
        codecs.encode(normalized, "rot_13"),
        quote(normalized, safe=""),
        base64_standard,
        base64_standard.rstrip("="),
        base64_urlsafe,
        base64_urlsafe.rstrip("="),
        base32_value,
        base32_value.rstrip("="),
        base64.b85encode(raw).decode("ascii"),
        base64.a85encode(raw).decode("ascii"),
        _base58_encode(raw),
        raw.hex(),
        raw.hex().upper(),
    }
    return {
        decoded.casefold()
        for form in forms
        for decoded in _decoded_text_forms(form)
        if decoded
    }


def reject_private_or_secret_material(value: Any, path: str = "transaction") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in PROHIBITED_KEYS:
                raise EstateDeltaError(f"prohibited private or secret field: {path}.{key}")
            reject_private_or_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            reject_private_or_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str):
        decoded_forms = _decoded_text_forms(value)
        if any(pattern.search(item) for item in decoded_forms for pattern in SECRET_PATTERNS):
            raise EstateDeltaError(f"secret-shaped value prohibited at {path}")
        lowered = " ".join(decoded_forms).casefold()
        if any(host in lowered for host in (
            "drive.google.com", "docs.google.com", "drive.usercontent.google.com",
            "www.googleapis.com/drive/",
        )):
            raise EstateDeltaError(f"private provider locator prohibited at {path}")
        free_text = any(path.endswith("." + key) for key in (
            "claim_text", "description", "closure_evidence", "earlier_claim",
            "truth_boundary", "registry_collision_note",
        ))
        metric_value = ".metrics[" in path and path.endswith(".value")
        if free_text and any(OPAQUE_PRIVATE_ID.search(item) for item in decoded_forms):
            raise EstateDeltaError(f"opaque private identifier prohibited at {path}")
        if metric_value and any(OPAQUE_PRIVATE_ID.search(item) for item in decoded_forms):
            safe_code = bool(STATE.fullmatch(decoded_forms[-1]) and "_" in decoded_forms[-1])
            if not safe_code and not HEX40.fullmatch(decoded_forms[-1]) and not HEX64.fullmatch(decoded_forms[-1]):
                raise EstateDeltaError(f"opaque private identifier prohibited at {path}")


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        raise EstateDeltaError("timestamps must use UTC Z form with seconds")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EstateDeltaError(f"invalid timestamp: {value}") from exc


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise EstateDeltaError(
            f"{path} keys mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )


def _require_sorted_unique(items: Sequence[str], path: str) -> None:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise EstateDeltaError(f"{path} must be a list")
    if not all(isinstance(item, str) and item for item in items):
        raise EstateDeltaError(f"{path} must contain nonempty strings")
    if list(items) != sorted(items) or len(items) != len(set(items)):
        raise EstateDeltaError(f"{path} must be sorted and unique")


def _index_unique(rows: Sequence[Mapping[str, Any]], key: str, path: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise EstateDeltaError(f"{path} must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise EstateDeltaError(f"{path} entries must be objects")
        identity = row.get(key)
        if not isinstance(identity, str) or not SAFE_ID.fullmatch(identity):
            raise EstateDeltaError(f"invalid {path}.{key}: {identity}")
        if identity in result:
            raise EstateDeltaError(f"duplicate {path}.{key}: {identity}")
        result[identity] = row
    if list(result) != sorted(result):
        raise EstateDeltaError(f"{path} must be sorted by {key}")
    return result


def _winner(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any] | None, str]:
    provider = [row for row in rows if row["evidence_class"] == "PROVIDER_NATIVE_READBACK"]
    if provider:
        return max(provider, key=lambda row: (_utc(str(row["observed_at"])), row["snapshot_id"])), "LATEST_PROVIDER_NATIVE_READBACK"
    current = [row for row in rows if row["evidence_class"] != "HISTORICAL_CLAIM"]
    if not current:
        return None, "NO_PROVIDER_READBACK_HOLD"
    winner = max(
        current,
        key=lambda row: (EVIDENCE_RANK[row["evidence_class"]], _utc(str(row["observed_at"])), row["snapshot_id"]),
    )
    if winner["evidence_class"] == "DERIVED_ABSENCE_OF_REQUIRED_PROOF":
        return winner, "NO_PROVIDER_READBACK_HOLD"
    return winner, "HIGHEST_CURRENT_EVIDENCE"


def validate_transaction(transaction: Mapping[str, Any]) -> dict[str, Any]:
    _require_exact_keys(transaction, {"body", "integrity"}, "transaction")
    reject_private_or_secret_material(transaction)
    body = transaction["body"]
    integrity = transaction["integrity"]
    if not isinstance(body, Mapping) or not isinstance(integrity, Mapping):
        raise EstateDeltaError("body and integrity must be objects")
    required_body = {
        "schema", "transaction_id", "register_id", "sequence", "event_type", "mission_id",
        "authority", "occurred_at", "observed_at", "artifact_classification", "scope",
        "lineage", "inputs", "surface_snapshots", "projections", "contradictions",
        "unresolved_boundaries", "effects", "privacy", "completion",
    }
    _require_exact_keys(body, required_body, "body")
    _require_exact_keys(
        integrity,
        {"canonicalization", "body_sha256", "previous_event_hash", "event_hash"},
        "integrity",
    )
    if body["schema"] != SCHEMA or body["register_id"] != REGISTER_ID:
        raise EstateDeltaError("transaction schema or register mismatch")
    if not isinstance(body["transaction_id"], str) or not TRANSACTION_ID.fullmatch(body["transaction_id"]):
        raise EstateDeltaError("transaction ID is invalid")
    if not isinstance(body["mission_id"], str) or not MISSION_ID.fullmatch(body["mission_id"]):
        raise EstateDeltaError("mission ID is invalid")
    if body["event_type"] not in {"CENSUS_SNAPSHOT", "CENSUS_DELTA", "CORRECTION", "SUPERSESSION"}:
        raise EstateDeltaError("event type is invalid")
    if body["authority"] != "A0_READ_ONLY":
        raise EstateDeltaError("estate census authority must remain A0_READ_ONLY")
    if body["artifact_classification"] != "PUBLIC_SAFE_PRIVATE_POINTERS_REDACTED":
        raise EstateDeltaError("public-safe classification required")
    occurred_at = _utc(str(body["occurred_at"]))
    observed_at = _utc(str(body["observed_at"]))
    if occurred_at > observed_at:
        raise EstateDeltaError("transaction occurrence cannot follow observation")
    if type(body["sequence"]) is not int or body["sequence"] < 1:
        raise EstateDeltaError("sequence must be a positive integer")

    expected_hash = canonical_sha256(body)
    if integrity["canonicalization"] != CANONICALIZATION:
        raise EstateDeltaError("canonicalization mismatch")
    if integrity["body_sha256"] != expected_hash:
        raise EstateDeltaError("body SHA-256 mismatch")
    previous_hash = integrity["previous_event_hash"]
    if body["sequence"] == 1:
        if previous_hash is not None or body["lineage"]["previous_transaction_id"] is not None:
            raise EstateDeltaError("genesis transaction cannot claim a chain parent")
    elif not isinstance(previous_hash, str) or not HEX64.fullmatch(previous_hash):
        raise EstateDeltaError("non-genesis transaction requires a previous event hash")
    event_material = {"body": body, "body_hash": expected_hash, "previous_event_hash": previous_hash}
    if integrity["event_hash"] != canonical_sha256(event_material):
        raise EstateDeltaError("event hash mismatch")

    scope = body["scope"]
    _require_exact_keys(
        scope,
        {"scope_label", "claim_text", "canonical_status", "totality_claimed", "expected_sources",
         "inspected_to_end", "all_expected_bounded_sources_enumerated"},
        "scope",
    )
    if scope["scope_label"] != "CONNECTED_CALLABLE_BOUNDED_CENSUS":
        raise EstateDeltaError("scope label mismatch")
    if scope["canonical_status"] != "PARTIAL_PROVEN" or scope["totality_claimed"] is not False:
        raise EstateDeltaError("bounded census cannot claim totality")
    _require_sorted_unique(scope["expected_sources"], "scope.expected_sources")
    _require_sorted_unique(scope["inspected_to_end"], "scope.inspected_to_end")
    if not scope["expected_sources"] or not scope["inspected_to_end"]:
        raise EstateDeltaError("bounded coverage source sets must not be empty")
    if scope["claim_text"] != BOUNDED_SCOPE_CLAIM_TEXT:
        raise EstateDeltaError("transaction claim text is not the canonical bounded claim")
    if not isinstance(scope["all_expected_bounded_sources_enumerated"], bool):
        raise EstateDeltaError("bounded coverage flag must be boolean")
    if scope["all_expected_bounded_sources_enumerated"] and scope["expected_sources"] != scope["inspected_to_end"]:
        raise EstateDeltaError("bounded coverage closure sets differ")

    lineage = body["lineage"]
    _require_exact_keys(lineage, {"previous_transaction_id", "historical_baselines"}, "lineage")
    if not isinstance(lineage["historical_baselines"], list):
        raise EstateDeltaError("historical baselines must be a list")
    previous_transaction_id = lineage["previous_transaction_id"]
    if body["sequence"] > 1 and (
        not isinstance(previous_transaction_id, str)
        or not TRANSACTION_ID.fullmatch(previous_transaction_id)
    ):
        raise EstateDeltaError("non-genesis transaction requires a valid previous transaction ID")
    for baseline in lineage["historical_baselines"]:
        _require_exact_keys(
            baseline,
            {"baseline_id", "claimed_sha256", "verification_state", "chain_parent"},
            "lineage.historical_baselines",
        )
        if (
            not isinstance(baseline["baseline_id"], str)
            or not BASELINE_ID.fullmatch(baseline["baseline_id"])
            or not isinstance(baseline["claimed_sha256"], str)
            or not HEX64.fullmatch(baseline["claimed_sha256"])
        ):
            raise EstateDeltaError("historical baseline identity or hash is invalid")
        if baseline["verification_state"] != "HISTORICAL_REFERENCE_UNRESOLVED" or baseline["chain_parent"] is not False:
            raise EstateDeltaError("unresolved historical baseline cannot become a chain parent")

    inputs = _index_unique(body["inputs"], "source_id", "inputs")
    if not inputs:
        raise EstateDeltaError("at least one census input is required")
    for source in inputs.values():
        _require_exact_keys(
            source,
            {"source_id", "source_class", "observed_at", "content_sha256", "locator_state", "proof_state"},
            "inputs",
        )
        if not SOURCE_ID.fullmatch(source["source_id"]):
            raise EstateDeltaError("input source ID is outside the public alias namespace")
        source_observed_at = _utc(str(source["observed_at"]))
        if source_observed_at > observed_at:
            raise EstateDeltaError("input observation cannot postdate the transaction")
        if not isinstance(source["content_sha256"], str) or not HEX64.fullmatch(source["content_sha256"]):
            raise EstateDeltaError("input content SHA-256 is invalid")
        if source["source_class"] not in INPUT_SOURCE_CLASSES:
            raise EstateDeltaError("input source class is invalid")
        if source["locator_state"] not in INPUT_LOCATOR_STATES:
            raise EstateDeltaError("input locator state is invalid")
        if source["proof_state"] not in INPUT_PROOF_STATES:
            raise EstateDeltaError("input proof state is invalid")
    boundaries = _index_unique(body["unresolved_boundaries"], "boundary_id", "unresolved_boundaries")
    if not boundaries:
        raise EstateDeltaError("PARTIAL_PROVEN requires named unresolved boundaries")
    for boundary in boundaries.values():
        _require_exact_keys(
            boundary,
            {"boundary_id", "description", "state", "material_to_totality", "closure_evidence", "avoidable_user_task"},
            "unresolved_boundaries",
        )
        if not BOUNDARY_ID.fullmatch(boundary["boundary_id"]):
            raise EstateDeltaError("boundary ID is outside the public alias namespace")
        if boundary["state"] != "OPEN" or boundary["material_to_totality"] is not True:
            raise EstateDeltaError("unresolved boundaries must remain open and material to totality")
        if boundary["avoidable_user_task"] is not False:
            raise EstateDeltaError("avoidable user tasks are prohibited")
        if not isinstance(boundary["description"], str) or not boundary["description"].strip():
            raise EstateDeltaError("boundary description is required")
        if not isinstance(boundary["closure_evidence"], str) or not boundary["closure_evidence"].strip():
            raise EstateDeltaError("boundary closure evidence is required")

    snapshots = _index_unique(body["surface_snapshots"], "snapshot_id", "surface_snapshots")
    by_subject: dict[str, list[Mapping[str, Any]]] = {}
    for snapshot in snapshots.values():
        _require_exact_keys(
            snapshot,
            {"snapshot_id", "subject_id", "surface", "evidence_class", "observed_at", "proof_state",
             "state", "input_source_ids", "metrics", "boundary_ids"},
            "surface_snapshots",
        )
        if not SNAPSHOT_ID.fullmatch(snapshot["snapshot_id"]):
            raise EstateDeltaError("snapshot ID is outside the public alias namespace")
        if not isinstance(snapshot["subject_id"], str) or not SUBJECT_ID.fullmatch(snapshot["subject_id"]):
            raise EstateDeltaError("snapshot subject ID is invalid")
        snapshot_observed_at = _utc(str(snapshot["observed_at"]))
        if snapshot_observed_at > observed_at:
            raise EstateDeltaError("surface observation cannot postdate the transaction")
        if snapshot["surface"] not in SURFACE_LABELS:
            raise EstateDeltaError("unsupported surface")
        if snapshot["evidence_class"] not in EVIDENCE_RANK:
            raise EstateDeltaError("unsupported evidence class")
        if snapshot["proof_state"] not in SNAPSHOT_PROOF_STATES:
            raise EstateDeltaError("unsupported surface proof state")
        if snapshot["proof_state"] not in EVIDENCE_PROOF_STATES[snapshot["evidence_class"]]:
            raise EstateDeltaError("surface proof state is incompatible with evidence class")
        if not isinstance(snapshot["state"], str) or not STATE.fullmatch(snapshot["state"]):
            raise EstateDeltaError("surface state is invalid")
        _require_sorted_unique(snapshot["input_source_ids"], f"{snapshot['snapshot_id']}.input_source_ids")
        _require_sorted_unique(snapshot["boundary_ids"], f"{snapshot['snapshot_id']}.boundary_ids")
        if not snapshot["input_source_ids"]:
            raise EstateDeltaError("surface snapshot requires an input source")
        if not set(snapshot["input_source_ids"]).issubset(inputs):
            raise EstateDeltaError("snapshot references an unknown input")
        if not set(snapshot["boundary_ids"]).issubset(boundaries):
            raise EstateDeltaError("snapshot references an unknown boundary")
        metric_names = [metric["name"] for metric in snapshot["metrics"]]
        _require_sorted_unique(metric_names, f"{snapshot['snapshot_id']}.metrics")
        for metric in snapshot["metrics"]:
            _require_exact_keys(metric, {"name", "value"}, f"{snapshot['snapshot_id']}.metrics")
            if metric["name"] not in SAFE_METRIC_NAMES:
                raise EstateDeltaError(f"metric is not public-safe: {metric['name']}")
            value = metric["value"]
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise EstateDeltaError("metric values must be JSON scalars")
            if isinstance(value, float) and not math.isfinite(value):
                raise EstateDeltaError("metric numbers must be finite")
            if isinstance(value, str):
                if metric["name"] in {"MAIN_COMMIT", "TREE_SHA"}:
                    if not HEX40.fullmatch(value):
                        raise EstateDeltaError("public source commit and tree metrics must be SHA-1 text")
                elif metric["name"] == "OPERATOR_SERVICE":
                    if value != "federation-omega-operator":
                        raise EstateDeltaError("operator service metric must use the public service alias")
                elif not STATE.fullmatch(value):
                    raise EstateDeltaError("string metric is outside the public state-code contract")
        by_subject.setdefault(snapshot["subject_id"], []).append(snapshot)

    projections = _index_unique(body["projections"], "subject_id", "projections")
    if any(not SUBJECT_ID.fullmatch(subject_id) for subject_id in projections):
        raise EstateDeltaError("projection subject ID is outside the public alias namespace")
    if set(projections) != set(by_subject):
        raise EstateDeltaError("every observed subject requires exactly one projection")
    for subject_id, rows in by_subject.items():
        winner, rule = _winner(rows)
        projection = projections[subject_id]
        _require_exact_keys(
            projection,
            {"subject_id", "state", "proof_state", "selection_rule", "winning_snapshot_id", "hold"},
            "projections",
        )
        expected_id = winner["snapshot_id"] if winner else None
        if projection["selection_rule"] != rule or projection["winning_snapshot_id"] != expected_id:
            raise EstateDeltaError(f"projection winner mismatch for {subject_id}")
        if projection["proof_state"] not in PROJECTION_PROOF_STATES:
            raise EstateDeltaError(f"projection proof state is invalid for {subject_id}")
        if not isinstance(projection["state"], str) or not STATE.fullmatch(projection["state"]):
            raise EstateDeltaError(f"projection state is invalid for {subject_id}")
        if not isinstance(projection["hold"], bool):
            raise EstateDeltaError(f"projection hold must be boolean for {subject_id}")
        if winner and (projection["state"] != winner["state"] or projection["proof_state"] != winner["proof_state"]):
            raise EstateDeltaError(f"projection state mismatch for {subject_id}")
        if rule == "NO_PROVIDER_READBACK_HOLD" and projection["hold"] is not True:
            raise EstateDeltaError(f"provider-proof gap must hold {subject_id}")
    contradictions = _index_unique(body["contradictions"], "contradiction_id", "contradictions")
    for item in contradictions.values():
        _require_exact_keys(
            item,
            {"contradiction_id", "subject_id", "earlier_claim", "current_snapshot_id", "disposition", "affects_totality"},
            "contradictions",
        )
        if not CONTRADICTION_ID.fullmatch(item["contradiction_id"]):
            raise EstateDeltaError("contradiction ID is outside the public alias namespace")
        if not SUBJECT_ID.fullmatch(str(item["subject_id"])):
            raise EstateDeltaError("contradiction subject ID is outside the public alias namespace")
        if not SNAPSHOT_ID.fullmatch(str(item["current_snapshot_id"])):
            raise EstateDeltaError("contradiction snapshot ID is outside the public alias namespace")
        if item["current_snapshot_id"] not in snapshots:
            raise EstateDeltaError("contradiction references an unknown current snapshot")
        if item["subject_id"] != snapshots[item["current_snapshot_id"]]["subject_id"]:
            raise EstateDeltaError("contradiction subject does not match its current snapshot")
        if item["disposition"] not in {"SUPERSEDED_RETAINED", "OPEN_CONFLICT"}:
            raise EstateDeltaError("contradiction disposition is invalid")
        if not isinstance(item["affects_totality"], bool):
            raise EstateDeltaError("contradiction totality flag must be boolean")
        if not isinstance(item["earlier_claim"], str) or not item["earlier_claim"].strip():
            raise EstateDeltaError("contradiction earlier claim is required")
    unresolved_contradictions = sum(
        item["disposition"] == "OPEN_CONFLICT" for item in contradictions.values()
    )
    completion = body["completion"]
    _require_exact_keys(
        completion,
        {"status", "totality_allowed", "unresolved_boundary_count", "unresolved_contradiction_count",
         "independent_check_state", "truth_boundary"},
        "completion",
    )
    if completion["status"] != "PARTIAL_PROVEN" or completion["totality_allowed"] is not False:
        raise EstateDeltaError("completion must remain PARTIAL_PROVEN")
    if type(completion["unresolved_boundary_count"]) is not int:
        raise EstateDeltaError("unresolved boundary count must be an integer")
    if type(completion["unresolved_contradiction_count"]) is not int:
        raise EstateDeltaError("unresolved contradiction count must be an integer")
    if completion["unresolved_boundary_count"] != len(boundaries):
        raise EstateDeltaError("unresolved boundary count mismatch")
    if completion["unresolved_contradiction_count"] != unresolved_contradictions:
        raise EstateDeltaError("unresolved contradiction count mismatch")
    if completion["independent_check_state"] not in {"PASSED_BOUNDED_SCOPE", "OPEN"}:
        raise EstateDeltaError("independent check state is invalid")
    if completion["truth_boundary"] != bounded_truth_boundary(body["observed_at"]):
        raise EstateDeltaError("transaction truth boundary is not canonically bounded")
    effects = body["effects"]
    _require_exact_keys(
        effects,
        {"mutation_count", "external_effect_count", "provider_mutation_performed", "email_sent", "cost_incurred"},
        "effects",
    )
    if not (
        type(effects["mutation_count"]) is int and effects["mutation_count"] == 0
        and type(effects["external_effect_count"]) is int and effects["external_effect_count"] == 0
        and effects["provider_mutation_performed"] is False
        and effects["email_sent"] is False
        and type(effects["cost_incurred"]) is int and effects["cost_incurred"] == 0
    ):
        raise EstateDeltaError("A0 census effects must be exactly zero")
    privacy = body["privacy"]
    _require_exact_keys(
        privacy,
        {"credential_value_recorded", "private_provider_identifier_recorded", "private_locator_count", "redaction_policy"},
        "privacy",
    )
    if not (
        privacy["credential_value_recorded"] is False
        and privacy["private_provider_identifier_recorded"] is False
        and type(privacy["private_locator_count"]) is int and privacy["private_locator_count"] == 0
        and privacy["redaction_policy"] == "ALIASES_COUNTS_STATES_AND_HASHES_ONLY"
    ):
        raise EstateDeltaError("privacy boundary mismatch")
    return {
        "state": "VALID_STRUCTURAL_BOUNDED_TRANSACTION",
        "transaction_id": body["transaction_id"],
        "body_sha256": expected_hash,
        "event_hash": integrity["event_hash"],
        "surface_count": len(snapshots),
        "boundary_count": len(boundaries),
    }


def validate_public_pointer(pointer: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "version", "register_id", "classification", "transaction_contract_path",
        "validator_path", "private_artifact_alias", "publication_state", "current_transaction",
        "current_transaction_contract", "rules", "credential_value_recorded",
        "private_provider_identifier_recorded", "private_locator_recorded",
        "provider_mutation_performed", "route_catalog_path", "route_registration_state",
        "route_discovery_adapter_state", "registry_collision_state",
        "registry_collision_build_id", "cfbe_compatibility_state", "truth_boundary",
    }
    _require_exact_keys(pointer, expected, "public_pointer")
    reject_private_or_secret_material(pointer, "public_pointer")
    if pointer["schema"] != PUBLIC_SCHEMA or pointer["register_id"] != REGISTER_ID:
        raise EstateDeltaError("public pointer schema or register mismatch")
    if pointer["version"] != "1.0.0":
        raise EstateDeltaError("public pointer version mismatch")
    if pointer["classification"] != "PUBLIC_SAFE_CONTRACT_PRIVATE_POINTERS_REDACTED":
        raise EstateDeltaError("public pointer classification mismatch")
    if pointer["transaction_contract_path"] != "federation_consolidation/data/estate_delta_transaction_v1.schema.json":
        raise EstateDeltaError("public pointer transaction contract path mismatch")
    if pointer["validator_path"] != "federation_consolidation/estate_delta_transaction.py":
        raise EstateDeltaError("public pointer validator path mismatch")
    if pointer["route_catalog_path"] != "federation_consolidation/data/estate_observation_route_catalog_v1.json":
        raise EstateDeltaError("public pointer route catalog path mismatch")
    if pointer["private_artifact_alias"] != "FEDERATION_ESTATE_DELTA_PRIVATE_V1":
        raise EstateDeltaError("public pointer private artifact alias mismatch")
    if pointer["current_transaction_contract"] != PUBLIC_CURRENT_TRANSACTION_CONTRACT:
        raise EstateDeltaError("public pointer current transaction contract mismatch")
    if pointer["rules"] != PUBLIC_POINTER_RULES:
        raise EstateDeltaError("public pointer rules mismatch")
    if pointer["truth_boundary"] != PUBLIC_POINTER_TRUTH_BOUNDARY:
        raise EstateDeltaError("public pointer truth boundary mismatch")
    if pointer["route_registration_state"] != "SOURCE_IMPLEMENTED_RUNTIME_UNVERIFIED":
        raise EstateDeltaError("public pointer cannot claim runtime route activation")
    if pointer["route_discovery_adapter_state"] != "ADAPTER_REQUIRED_NOT_RUNTIME_BOUND":
        raise EstateDeltaError("public pointer route discovery adapter state mismatch")
    if pointer["registry_collision_state"] != "QUARANTINED_REGISTRY_COLLISION":
        raise EstateDeltaError("continuity registry collision must remain quarantined")
    if pointer["registry_collision_build_id"] != "AO-CRA-FEDREG-COLLISION-001":
        raise EstateDeltaError("continuity registry collision build ID mismatch")
    if pointer["cfbe_compatibility_state"] != "REFERENCE_ONLY_UNMERGED":
        raise EstateDeltaError("unmerged CFBE reference cannot become a source dependency")
    if any(pointer[field] is not False for field in (
        "credential_value_recorded", "private_provider_identifier_recorded",
        "private_locator_recorded", "provider_mutation_performed",
    )):
        raise EstateDeltaError("public pointer weakens the privacy or authority boundary")
    current = pointer["current_transaction"]
    if current is not None:
        raise EstateDeltaError("canonical public source must remain alias-only with no current transaction receipt")
    if pointer["publication_state"] != "PREPARED_EXTERNAL_PUBLICATION_PENDING":
        raise EstateDeltaError("alias-only pointer must remain prepared and pending")
    return {"state": "VALID_PUBLIC_POINTER", "publication_state": pointer["publication_state"]}


def _normalize_intent(intent: str) -> str:
    if not isinstance(intent, str):
        raise EstateDeltaError("intent must be text")
    normalized = " ".join(intent.casefold().split())
    if not normalized:
        raise EstateDeltaError("intent must not be empty")
    return normalized


def validate_route_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "version", "publication_state", "registry_collision_state",
        "registry_collision_note", "registry_collision_build", "selector_contract",
        "cfbe_compatibility", "route_discovery_adapter", "routes",
    }
    _require_exact_keys(catalog, expected, "route_catalog")
    reject_private_or_secret_material(catalog, "route_catalog")
    if catalog["schema"] != ROUTE_CATALOG_SCHEMA:
        raise EstateDeltaError("route catalog schema mismatch")
    if catalog["version"] != "1.0.0":
        raise EstateDeltaError("route catalog version mismatch")
    if catalog["publication_state"] != "SOURCE_IMPLEMENTED_RUNTIME_UNVERIFIED":
        raise EstateDeltaError("route catalog cannot claim runtime activation")
    if catalog["registry_collision_state"] != "QUARANTINED_REGISTRY_COLLISION":
        raise EstateDeltaError("continuity registry collision must remain quarantined")
    if catalog["registry_collision_note"] != REGISTRY_COLLISION_NOTE:
        raise EstateDeltaError("continuity registry collision note is not contract-bound")
    if catalog["registry_collision_build"] != REGISTRY_COLLISION_BUILD:
        raise EstateDeltaError("continuity registry AO-CRA build contract differs")

    selector = catalog["selector_contract"]
    _require_exact_keys(
        selector,
        {"normalization", "match", "unknown_intent", "ambiguous_intent", "provider_execution_inherited"},
        "route_catalog.selector_contract",
    )
    if selector != {
        "normalization": "UNICODE_CASEFOLD_TRIM_COLLAPSE_WHITESPACE",
        "match": "EXACT_NORMALIZED_INTENT_ONLY",
        "unknown_intent": "NO_SOURCE_ROUTE",
        "ambiguous_intent": "AMBIGUOUS_SOURCE_ROUTE",
        "provider_execution_inherited": False,
    }:
        raise EstateDeltaError("selector contract weakens deterministic fail-closed routing")

    compatibility = catalog["cfbe_compatibility"]
    _require_exact_keys(compatibility, set(CFBE_COMPATIBILITY), "route_catalog.cfbe_compatibility")
    if compatibility != CFBE_COMPATIBILITY:
        raise EstateDeltaError("CFBE compatibility boundary mismatch")
    adapter = catalog["route_discovery_adapter"]
    _require_exact_keys(adapter, set(ROUTE_DISCOVERY_ADAPTER), "route_catalog.route_discovery_adapter")
    if adapter != ROUTE_DISCOVERY_ADAPTER:
        raise EstateDeltaError("current-main route discovery adapter boundary mismatch")

    routes = catalog["routes"]
    if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes, bytearray)):
        raise EstateDeltaError("routes must be a list")
    route_index = _index_unique(routes, "route_id", "routes")
    if set(route_index) != {"FEDERATION_CENSUS_A0", "PROVIDER_OBSERVATION_A0"}:
        raise EstateDeltaError("exact federation observation routes are required")

    intent_owners: dict[str, str] = {}
    route_keys = {
        "route_id", "intents", "capability", "proof_action_id", "authority_ceiling",
        "effectful", "dry_run", "maximum_incremental_cost", "maximum_user_burden",
        "recurring_cost", "activation_state", "proof_stage", "required_readbacks",
        "prohibited_actions",
    }
    for route_id, route in route_index.items():
        _require_exact_keys(route, route_keys, f"routes.{route_id}")
        intents = [_normalize_intent(item) for item in route["intents"]]
        _require_sorted_unique(intents, f"routes.{route_id}.intents")
        if route["intents"] != intents:
            raise EstateDeltaError("route intents must already be normalized")
        for intent in intents:
            if intent in intent_owners:
                raise EstateDeltaError("AMBIGUOUS_SOURCE_ROUTE")
            intent_owners[intent] = route_id
        contract = ROUTE_CONTRACTS[route_id]
        if route["intents"] != contract["intents"]:
            raise EstateDeltaError(f"route intents are not contract-bound for {route_id}")
        if route["capability"] != contract["capability"]:
            raise EstateDeltaError(f"route capability is not contract-bound for {route_id}")
        if route["proof_action_id"] != contract["proof_action_id"]:
            raise EstateDeltaError(f"route proof action is not contract-bound for {route_id}")
        if route["required_readbacks"] != contract["required_readbacks"]:
            raise EstateDeltaError(f"route readbacks are not contract-bound for {route_id}")
        if route["authority_ceiling"] != "A0" or route["effectful"] is not False or route["dry_run"] is not True:
            raise EstateDeltaError("observation routes must remain dry-run A0 and non-effectful")
        if any(type(route[field]) is not int or route[field] != 0 for field in (
            "maximum_incremental_cost", "maximum_user_burden", "recurring_cost"
        )):
            raise EstateDeltaError("observation routes must remain zero-cost and zero-burden")
        if route["activation_state"] != "SOURCE_REGISTERED_NOT_RUNTIME_BOUND" or route["proof_stage"] != "DISCOVERED":
            raise EstateDeltaError("source routes cannot claim runtime or provider proof")
        _require_sorted_unique(route["required_readbacks"], f"routes.{route_id}.required_readbacks")
        _require_sorted_unique(route["prohibited_actions"], f"routes.{route_id}.prohibited_actions")
        required_prohibitions = {
            "COMMUNICATION", "DEPLOYMENT", "IAM_MUTATION", "MODEL_CALL",
            "PROVIDER_MUTATION", "TOKEN_EXCHANGE",
        }
        if set(route["prohibited_actions"]) != required_prohibitions:
            raise EstateDeltaError("observation route prohibition set is incomplete")

    if intent_owners.get("federation census") != "FEDERATION_CENSUS_A0":
        raise EstateDeltaError("exact federation census intent is unbound")
    if intent_owners.get("provider observation") != "PROVIDER_OBSERVATION_A0":
        raise EstateDeltaError("exact provider observation intent is unbound")
    return {
        "state": "VALID_SOURCE_ROUTE_CATALOG_RUNTIME_UNVERIFIED",
        "route_count": len(route_index),
        "route_catalog_sha256": canonical_sha256(catalog),
    }


def select_observation_route(intent: str, catalog: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_route_catalog(catalog)
    normalized = _normalize_intent(intent)
    matches = [route for route in catalog["routes"] if normalized in route["intents"]]
    if not matches:
        raise EstateDeltaError("NO_SOURCE_ROUTE")
    if len(matches) != 1:
        raise EstateDeltaError("AMBIGUOUS_SOURCE_ROUTE")
    route = matches[0]
    return {
        "state": "SOURCE_ROUTE_SELECTED_RUNTIME_UNVERIFIED",
        "intent": normalized,
        "route_id": route["route_id"],
        "capability": route["capability"],
        "route_definition_hash": canonical_sha256(route),
        "route_catalog_sha256": validation["route_catalog_sha256"],
        "activation_state": route["activation_state"],
        "route_discovery_adapter_state": catalog["route_discovery_adapter"]["binding_state"],
        "provider_execution_inherited": False,
        "proof_receipt_inherited": False,
    }


def validate_schema_alignment(schema: Mapping[str, Any]) -> dict[str, Any]:
    if canonical_sha256(schema) != EXPECTED_SCHEMA_CANONICAL_SHA256:
        raise EstateDeltaError("transaction schema canonical digest drifted from validator")
    try:
        definitions = schema["$defs"]
        body = schema["properties"]["body"]
        body_properties = body["properties"]
        snapshot = definitions["surfaceSnapshot"]["properties"]
        source = definitions["input"]["properties"]
        projection = definitions["projection"]["properties"]
    except (KeyError, TypeError) as exc:
        raise EstateDeltaError("transaction schema structure mismatch") from exc
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise EstateDeltaError("transaction JSON Schema dialect mismatch")
    if schema.get("additionalProperties") is not False or schema.get("required") != ["body", "integrity"]:
        raise EstateDeltaError("transaction schema root is not closed-world")
    expected_body_fields = {
        "schema", "transaction_id", "register_id", "sequence", "event_type", "mission_id",
        "authority", "occurred_at", "observed_at", "artifact_classification", "scope",
        "lineage", "inputs", "surface_snapshots", "projections", "contradictions",
        "unresolved_boundaries", "effects", "privacy", "completion",
    }
    if set(body.get("required", [])) != expected_body_fields or body.get("additionalProperties") is not False:
        raise EstateDeltaError("transaction schema body fields drifted from validator")
    checks = (
        (set(source["source_class"].get("enum", [])), INPUT_SOURCE_CLASSES, "input source classes"),
        (set(source["locator_state"].get("enum", [])), INPUT_LOCATOR_STATES, "input locator states"),
        (set(source["proof_state"].get("enum", [])), INPUT_PROOF_STATES, "input proof states"),
        (set(snapshot["surface"].get("enum", [])), set(SURFACE_LABELS), "surfaces"),
        (set(snapshot["evidence_class"].get("enum", [])), set(EVIDENCE_RANK), "evidence classes"),
        (set(snapshot["proof_state"].get("enum", [])), SNAPSHOT_PROOF_STATES, "snapshot proof states"),
        (set(projection["proof_state"].get("enum", [])), PROJECTION_PROOF_STATES, "projection proof states"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise EstateDeltaError(f"transaction schema {label} drifted from validator")
    if definitions["utcTimestamp"].get("pattern") != UTC_TIMESTAMP.pattern:
        raise EstateDeltaError("transaction schema timestamp pattern drifted from validator")
    identifier_patterns = {
        "missionId": MISSION_ID,
        "transactionId": TRANSACTION_ID,
        "baselineId": BASELINE_ID,
        "sourceId": SOURCE_ID,
        "snapshotId": SNAPSHOT_ID,
        "subjectId": SUBJECT_ID,
        "boundaryId": BOUNDARY_ID,
        "contradictionId": CONTRADICTION_ID,
    }
    for definition_name, validator_pattern in identifier_patterns.items():
        if definitions.get(definition_name, {}).get("pattern") != validator_pattern.pattern:
            raise EstateDeltaError(
                f"transaction schema {definition_name} pattern drifted from validator"
            )
    if body_properties["schema"].get("const") != SCHEMA or body_properties["register_id"].get("const") != REGISTER_ID:
        raise EstateDeltaError("transaction schema identity drifted from validator")
    return {"state": "SCHEMA_VALIDATOR_ALIGNED", "schema": SCHEMA}


def _lookup_path(value: Mapping[str, Any], path: Sequence[str]) -> tuple[bool, Any]:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _manifest_value(manifest: Mapping[str, Any], *path: str) -> Any:
    exists, value = _lookup_path(manifest, path)
    if not exists:
        raise EstateDeltaError("source manifest state field missing: " + ".".join(path))
    return value


def _require_object(value: Any, keys: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EstateDeltaError(f"{path} must be an object")
    _require_exact_keys(value, keys, path)
    return value


def _require_nonempty_text_list(value: Any, path: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise EstateDeltaError(f"{path} must be a nonempty text list")
    return value


def _validate_claim_gate_semantics(gate: Any, *, bounded: bool) -> None:
    label = "bounded claim gate" if bounded else "totality rejection gate"
    value = _require_object(gate, {
        "claim", "declaredStatus", "claimScope", "sourceCoverage", "candidateTests",
        "authority", "evidence", "requirements", "counterexampleSearch", "fruit",
        "independentCheckPassed",
    }, label)
    coverage = _require_object(value["sourceCoverage"], {
        "allExpectedSourcesEnumerated", "manifestCurrent", "expected", "inspectedToEnd",
    }, f"{label}.sourceCoverage")
    candidate = _require_object(value["candidateTests"], {
        "executedAgainstCandidate", "allPassed", "failures",
    }, f"{label}.candidateTests")
    authority = _require_object(value["authority"], {
        "canonicalSourceResolved", "conflictsResolved", "supersessionResolved",
    }, f"{label}.authority")
    evidence = _require_object(value["evidence"], {
        "current", "independentReadback", "contradictions", "unknowns",
    }, f"{label}.evidence")
    requirements = _require_object(value["requirements"], {
        "criticalTotal", "criticalProven",
    }, f"{label}.requirements")
    critical_total = requirements.get("criticalTotal")
    critical_proven = requirements.get("criticalProven")
    if not (
        type(critical_total) is int
        and type(critical_proven) is int
        and critical_total > 0
        and 0 <= critical_proven < critical_total
    ):
        raise EstateDeltaError(f"{label} critical requirement counts are not partial")
    counterexample = _require_object(value["counterexampleSearch"], {
        "performed", "findings",
    }, f"{label}.counterexampleSearch")
    fruit = _require_object(value["fruit"], {"expected", "observed"}, f"{label}.fruit")
    expected_fruit = _require_nonempty_text_list(fruit["expected"], f"{label}.fruit.expected")
    observed_fruit = _require_nonempty_text_list(fruit["observed"], f"{label}.fruit.observed")
    if expected_fruit != observed_fruit:
        raise EstateDeltaError(f"{label} expected and observed fruit differ")
    if authority != {
        "canonicalSourceResolved": False,
        "conflictsResolved": False,
        "supersessionResolved": False,
    }:
        raise EstateDeltaError(f"{label} authority semantics differ")
    if evidence.get("current") is not True or evidence.get("independentReadback") is not True:
        raise EstateDeltaError(f"{label} current independent evidence semantics differ")
    if counterexample.get("performed") is not True:
        raise EstateDeltaError(f"{label} counterexample search was not performed")
    if candidate.get("executedAgainstCandidate") is not True:
        raise EstateDeltaError(f"{label} candidate tests were not executed")

    if bounded:
        if not (
            value["claim"]
            == "A current bounded census covers the connected and callable Federation surfaces listed in scope, with unresolved boundaries named."
            and value["declaredStatus"] == "PARTIAL"
            and isinstance(value["claimScope"], str)
            and "accessible" in value["claimScope"].casefold()
            and coverage.get("allExpectedSourcesEnumerated") is True
            and coverage.get("manifestCurrent") is True
            and candidate.get("allPassed") is True
            and candidate.get("failures") == []
            and evidence.get("contradictions") == []
            and isinstance(evidence.get("unknowns"), list)
            and bool(evidence["unknowns"])
            and counterexample.get("findings") == []
            and value["independentCheckPassed"] is True
        ):
            raise EstateDeltaError("bounded claim gate role semantics differ")
    else:
        expected = coverage.get("expected")
        inspected = coverage.get("inspectedToEnd")
        if not (
            value["claim"]
            == "The full Federation estate has been exhaustively swept and everything is known."
            and value["declaredStatus"] == "COMPREHENSIVE"
            and isinstance(value["claimScope"], str)
            and "Universal current Federation estate" in value["claimScope"]
            and coverage.get("allExpectedSourcesEnumerated") is False
            and coverage.get("manifestCurrent") is False
            and isinstance(expected, list)
            and isinstance(inspected, list)
            and bool(expected)
            and bool(inspected)
            and not set(expected).issubset(set(inspected))
            and candidate.get("allPassed") is False
            and bool(candidate.get("failures"))
            and bool(evidence.get("contradictions"))
            and bool(evidence.get("unknowns"))
            and bool(counterexample.get("findings"))
            and value["independentCheckPassed"] is False
        ):
            raise EstateDeltaError("totality rejection gate role semantics differ")


def _validate_drift_semantics(
    drift: Any, manifest: Mapping[str, Any]
) -> tuple[set[str], list[str]]:
    value = _require_object(drift, {
        "intent", "queue", "schema", "transport", "capability", "authority", "artifact",
        "lineage", "rollback", "counterfactual",
    }, "drift readback")
    intent = _require_object(value["intent"], {"mutationRequested"}, "drift.intent")
    queue = _require_object(
        value["queue"], {"configuredId", "liveProcessorId", "triggerFresh"}, "drift.queue"
    )
    schema = _require_object(
        value["schema"], {"declaredFingerprint", "liveFingerprint"}, "drift.schema"
    )
    transport = _require_object(value["transport"], {"success"}, "drift.transport")
    capability = _require_object(value["capability"], {
        "action", "enabled", "expectedFields", "actualResponse", "recentResponses",
        "lastProvenAt", "expiryHours",
    }, "drift.capability")
    actual = _require_object(capability["actualResponse"], {
        "projectId", "projectNumber", "poolStatus", "providerStatus", "receiptSha256",
    }, "drift.capability.actualResponse")
    authority = _require_object(
        value["authority"], {"required", "current", "checkedAt"}, "drift.authority"
    )
    artifact = _require_object(
        value["artifact"], {"retrievable", "declaredHash", "calculatedHash"}, "drift.artifact"
    )
    lineage = _require_object(value["lineage"], {"sourceHash"}, "drift.lineage")
    rollback = _require_object(
        value["rollback"], {"symbolic", "revision", "imageDigest", "viable"}, "drift.rollback"
    )
    counterfactual = _require_object(
        value["counterfactual"], {"expectedChanges", "observedChanges"}, "drift.counterfactual"
    )
    queue_id = queue.get("configuredId")
    claimed_receipt_digest = artifact.get("declaredHash")
    receipt_digest_is_hex = bool(
        isinstance(claimed_receipt_digest, str)
        and re.fullmatch(r"[0-9a-f]{40,64}", claimed_receipt_digest)
    )
    if not (
        intent.get("mutationRequested") is False
        and isinstance(queue_id, str)
        and bool(queue_id)
        and queue.get("liveProcessorId") == queue_id
        and queue.get("triggerFresh") is True
        and schema == {"declaredFingerprint": None, "liveFingerprint": None}
        and transport.get("success") is True
        and capability.get("action") == "SOVARA_WIF_INVENTORY_V1"
        and capability.get("enabled") is True
        and capability.get("expectedFields")
        == ["projectId", "projectNumber", "poolStatus", "providerStatus", "receiptSha256"]
        and capability.get("recentResponses") == []
        and capability.get("expiryHours") == 24
        and authority.get("required") == ["OWNER_OAUTH_READ_ONLY"]
        and authority.get("current") == ["OWNER_OAUTH_READ_ONLY"]
        and artifact.get("retrievable") is True
        and receipt_digest_is_hex
        and artifact.get("calculatedHash") == artifact["declaredHash"]
        and lineage.get("sourceHash") == artifact["declaredHash"]
        and actual.get("receiptSha256") == artifact["declaredHash"]
        and rollback == {"symbolic": False, "revision": None, "imageDigest": None, "viable": None}
        and counterfactual == {"expectedChanges": [], "observedChanges": []}
    ):
        raise EstateDeltaError("drift readback role semantics differ")
    if _utc(str(capability.get("lastProvenAt"))) > _utc(str(manifest.get("observedAtUtc"))):
        raise EstateDeltaError("drift proof postdates the census manifest")
    if _utc(str(authority.get("checkedAt"))) > _utc(str(manifest.get("observedAtUtc"))):
        raise EstateDeltaError("drift authority check postdates the census manifest")

    cloud = (manifest.get("surfaces") or {}).get("cloudControl")
    if isinstance(cloud, Mapping) and not (
        actual.get("projectId") == cloud.get("wifProjectId")
        and actual.get("projectNumber") == cloud.get("wifProjectNumber")
        and actual.get("poolStatus") == cloud.get("wifPool")
        and actual.get("providerStatus") == cloud.get("wifProvider")
        and actual.get("receiptSha256") == cloud.get("wifReceiptSha256")
    ):
        raise EstateDeltaError("drift readback differs from manifest WIF evidence")
    private_values = {
        item for item in (
            queue_id,
            actual.get("projectId"),
            actual.get("projectNumber"),
        ) if isinstance(item, str) and item
    }
    anomalies = [] if HEX64.fullmatch(str(claimed_receipt_digest)) else [
        "DRIFT_RECEIPT_DIGEST_LENGTH_NONSTANDARD"
    ]
    return private_values, anomalies


def _validate_oifa_semantics(
    report: Any,
    manifest: Mapping[str, Any],
    source_payload_bytes: Mapping[str, bytes],
    supporting_payloads: Mapping[str, bytes | str] | None,
) -> None:
    expected_keys = {
        "mission_id", "input_hashes", "overall_fidelity_status", "owner_instruction_coverage",
        "cadence_due", "material_gaps", "contradictions", "hard_gates", "recommended_handoff",
        "release_authority", "owner_objective_test", "two_product_test",
        "assessor_centrality_test", "narrative_test", "applicant_theory_test",
        "proof_discipline_test", "relevance_test", "replacement_completeness_test",
        "continuity_test", "cadence_test", "lawful_route_test", "sovereignty_test",
    }
    value = _require_object(report, expected_keys, "OIFA fidelity report")
    input_hashes = _require_object(value["input_hashes"], {
        "formation_packet", "foresight_plan", "drift_packet", "totality_packet",
        "bounded_packet", "evidence_manifest",
    }, "OIFA.input_hashes")
    for label, digest in input_hashes.items():
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise EstateDeltaError(f"OIFA input hash is invalid: {label}")
    role_to_source_class = {
        "drift_packet": "DRIFT_READBACK",
        "totality_packet": "TOTALITY_REJECTION_GATE",
        "bounded_packet": "BOUNDED_CLAIM_GATE",
        "evidence_manifest": "DERIVED_CENSUS_MANIFEST",
    }
    for role, source_class in role_to_source_class.items():
        if input_hashes[role] != hashlib.sha256(source_payload_bytes[source_class]).hexdigest():
            raise EstateDeltaError(f"OIFA source hash binding differs: {role}")
    if supporting_payloads is None or set(supporting_payloads) != {
        "formation_packet", "foresight_plan",
    }:
        raise EstateDeltaError("OIFA supporting payload set is incomplete")
    parsed_support: dict[str, Mapping[str, Any]] = {}
    for role in ("formation_packet", "foresight_plan"):
        payload = supporting_payloads[role]
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            payload_bytes = payload
        else:
            raise EstateDeltaError(f"OIFA supporting payload must be bytes or text: {role}")
        if input_hashes[role] != hashlib.sha256(payload_bytes).hexdigest():
            raise EstateDeltaError(f"OIFA supporting payload hash differs: {role}")
        try:
            parsed = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EstateDeltaError(f"OIFA supporting payload is not UTF-8 JSON: {role}") from exc
        if not isinstance(parsed, Mapping):
            raise EstateDeltaError(f"OIFA supporting payload must contain an object: {role}")
        parsed_support[role] = parsed

    formation = parsed_support["formation_packet"]
    formation_mission = formation.get("mission")
    formation_action = formation.get("proposedAction")
    formation_pending = formation.get("pendingActions")
    if not (
        isinstance(formation_mission, Mapping)
        and isinstance(formation_action, Mapping)
        and formation_pending == []
        and formation_mission.get("id") == manifest.get("missionId")
        and formation_mission.get("stopRequested") is False
        and formation_action.get("missionId") == manifest.get("missionId")
        and formation_action.get("missionVersion") == formation_mission.get("version")
        and formation_action.get("authorityClass") == "A0"
        and formation_action.get("estimatedCost") == 0
        and formation_action.get("recurringCost") == 0
        and formation_action.get("estimatedUserBurden") == 0
        and formation_action.get("manualUserTasks", []) == []
        and formation_action.get("avoidableUserOrchestration") is False
        and formation_action.get("reversible") is True
    ):
        raise EstateDeltaError("Formation supporting packet semantics differ")
    constraints = formation_mission.get("constraints")
    if not (
        isinstance(constraints, Mapping)
        and constraints.get("authorizedClasses") == ["A0"]
        and constraints.get("maximumCost") == 0
        and constraints.get("zeroNewRecurringCost") is True
        and constraints.get("maximumUserBurden") == 0
        and constraints.get("manualUserTasksAllowed") is False
        and constraints.get("externalWritesAllowed") is False
        and constraints.get("externalCommunicationsAllowed") is False
    ):
        raise EstateDeltaError("Formation supporting packet constraints differ")

    foresight = parsed_support["foresight_plan"]
    foresight_mission = foresight.get("mission")
    horizons = foresight.get("horizons")
    if not (
        isinstance(foresight_mission, Mapping)
        and foresight_mission.get("id") == manifest.get("missionId")
        and foresight_mission.get("version") == formation_mission.get("version")
        and foresight.get("activationMode") == "FULL"
        and foresight.get("authorityExpansion") is False
        and foresight.get("runtimeState") == "ON_DEMAND_GOVERNED"
        and foresight.get("stopState") == "ACTIVE"
        and foresight.get("visibleLedgerRequired") is True
        and foresight.get("fanInCount") == 1
        and foresight.get("lanes") == ["PRIMARY_EXECUTOR", "TWIN_FORESIGHT_VERIFIER"]
        and isinstance(horizons, list)
        and len(horizons) == 50
        and [item.get("horizon") for item in horizons if isinstance(item, Mapping)]
        == list(range(1, 51))
    ):
        raise EstateDeltaError("foresight supporting plan semantics differ")
    instructions = value["owner_instruction_coverage"]
    if not isinstance(instructions, list) or not instructions:
        raise EstateDeltaError("OIFA owner instruction coverage is empty")
    instruction_states: list[str] = []
    for item in instructions:
        row = _require_object(item, {"instruction", "source", "state"}, "OIFA instruction")
        if not all(isinstance(row[key], str) and row[key].strip() for key in ("instruction", "source")):
            raise EstateDeltaError("OIFA instruction provenance is incomplete")
        instruction_states.append(str(row["state"]))
    if "CONFLICT_ESCALATED" not in instruction_states or not set(instruction_states).issubset({
        "PRESENT", "CONFLICT_ESCALATED",
    }):
        raise EstateDeltaError("OIFA instruction coverage states differ")
    _require_nonempty_text_list(value["material_gaps"], "OIFA.material_gaps")
    _require_nonempty_text_list(value["contradictions"], "OIFA.contradictions")
    hard_gates = _require_nonempty_text_list(value["hard_gates"], "OIFA.hard_gates")
    joined_gates = " ".join(hard_gates).casefold()
    if not all(term in joined_gates for term in ("universal", "gemini", "wif", "no mutation")):
        raise EstateDeltaError("OIFA hard-gate semantics differ")
    if not (
        value.get("mission_id") == manifest.get("missionId")
        and value.get("overall_fidelity_status") == "PARTIAL"
        and value.get("cadence_due") is False
        and isinstance(value.get("recommended_handoff"), str)
        and "immutable delta register" in value["recommended_handoff"].casefold()
        and value.get("release_authority") == "NONE"
    ):
        raise EstateDeltaError("OIFA mission or release semantics differ")
    status_fields = expected_keys - {
        "mission_id", "input_hashes", "overall_fidelity_status", "owner_instruction_coverage",
        "cadence_due", "material_gaps", "contradictions", "hard_gates", "recommended_handoff",
        "release_authority",
    }
    for field in status_fields:
        check = _require_object(value[field], {"status", "basis"}, f"OIFA.{field}")
        expected_status = "PARTIAL" if field == "replacement_completeness_test" else "VERIFIED"
        if check.get("status") != expected_status or not isinstance(check.get("basis"), str) or not check["basis"].strip():
            raise EstateDeltaError(f"OIFA assessment semantics differ: {field}")


def _reject_known_private_source_values(
    transaction: Mapping[str, Any],
    manifest: Mapping[str, Any],
    drift_private_values: set[str],
) -> None:
    private_values = set(drift_private_values)
    for path in (
        ("surfaces", "googleDrive", "surfaceIndexId"),
        ("surfaces", "cloudControl", "wifProjectId"),
        ("surfaces", "cloudControl", "wifProjectNumber"),
        ("surfaces", "cloudControl", "operatorReadyRevision"),
        ("surfaces", "cloudControl", "architronReadyRevision"),
        ("surfaces", "cloudControl", "architronNewestCreatedRevision"),
    ):
        exists, source_value = _lookup_path(manifest, path)
        if exists and isinstance(source_value, str) and source_value:
            private_values.add(source_value)
    normalized_private_values = set().union(
        *(_known_private_text_forms(private) for private in private_values)
    )
    digest_or_time_fields = {
        "body_sha256", "event_hash", "previous_event_hash", "content_sha256",
        "claimed_sha256", "occurred_at", "observed_at",
    }
    for path, value in _iter_text_values(transaction):
        if path.rsplit(".", 1)[-1] in digest_or_time_fields:
            continue
        decoded_forms = [form.casefold() for form in _decoded_text_forms(value)]
        if any(private in decoded for private in normalized_private_values for decoded in decoded_forms):
            raise EstateDeltaError("transaction contains a known private source identifier")


def _expected_subject_states(manifest: Mapping[str, Any], subjects: set[str]) -> dict[str, str]:
    expected: dict[str, str] = {}
    if "SURFACE:AUTOMATIONS" in subjects:
        if _manifest_value(manifest, "surfaces", "automations", "totalityClaimed") is not False:
            raise EstateDeltaError("automation source state is incompatible with bounded observation")
        expected["SURFACE:AUTOMATIONS"] = "BOUNDED_LIST_ONLY"
    if "SURFACE:CANVA" in subjects:
        expected["SURFACE:CANVA"] = str(_manifest_value(manifest, "surfaces", "canva", "state"))
    if "SURFACE:CAPABILITY-FABRIC" in subjects:
        fabric = _manifest_value(manifest, "surfaces", "capabilityFabric")
        if not isinstance(fabric, Mapping) or any(
            not isinstance(fabric.get(field), bool)
            for field in (
                "cachedRegistryCurrent", "federationCensusRouteExists",
                "providerObservationRouteExists",
            )
        ):
            raise EstateDeltaError("capability fabric source state is not a bounded Boolean observation")
        registry_state = "CURRENT" if fabric["cachedRegistryCurrent"] else "STALE"
        route_count = sum(
            (fabric["federationCensusRouteExists"], fabric["providerObservationRouteExists"])
        )
        route_state = ("ROUTES_ABSENT", "ROUTES_PARTIAL", "ROUTES_PRESENT")[route_count]
        expected["SURFACE:CAPABILITY-FABRIC"] = f"CACHED_REGISTRY_{registry_state}_{route_state}"
    if "SURFACE:CLOUD-ESTATE" in subjects:
        expected["SURFACE:CLOUD-ESTATE"] = str(_manifest_value(manifest, "state", "cloudEstate"))
    if "SURFACE:CLOUD-OPERATOR" in subjects:
        expected["SURFACE:CLOUD-OPERATOR"] = str(
            _manifest_value(manifest, "surfaces", "cloudControl", "operatorHealth")
        )
    if "SURFACE:GEMINI" in subjects:
        expected["SURFACE:GEMINI"] = str(_manifest_value(manifest, "state", "gemini"))
    if "SURFACE:GITHUB" in subjects:
        repository_state = str(_manifest_value(manifest, "state", "repositoryCi"))
        admission_state = str(
            _manifest_value(manifest, "surfaces", "github", "providerAdmission", "status")
        )
        expected["SURFACE:GITHUB"] = repository_state + "_PROVIDER_ADMISSION_" + admission_state
    if "SURFACE:GMAIL" in subjects:
        gmail = _manifest_value(manifest, "surfaces", "gmail")
        lineage_state = gmail.get("lineageSweep") if isinstance(gmail, Mapping) else None
        failure_observed = (
            gmail.get("currentFailureClusterObserved") if isinstance(gmail, Mapping) else None
        )
        if (
            not isinstance(lineage_state, str)
            or not STATE.fullmatch(lineage_state)
            or not isinstance(failure_observed, bool)
        ):
            raise EstateDeltaError("Gmail source state is not a bounded lineage observation")
        failure_state = "FAILURE_CLUSTER_PRESENT" if failure_observed else "NO_FAILURE_CLUSTER_OBSERVED"
        expected["SURFACE:GMAIL"] = f"{lineage_state}_{failure_state}"
    if "SURFACE:GOOGLE-DRIVE" in subjects:
        drive = _manifest_value(manifest, "surfaces", "googleDrive")
        named_searches = drive.get("closedNamedSearches") if isinstance(drive, Mapping) else None
        whole_recursion = drive.get("wholeDriveRecursionRun") if isinstance(drive, Mapping) else None
        if type(named_searches) is not int or named_searches < 0 or not isinstance(whole_recursion, bool):
            raise EstateDeltaError("Drive source state is not a bounded search observation")
        search_state = "NAMED_SEARCHES_CLOSED" if named_searches > 0 else "NO_NAMED_SEARCH_CLOSURE"
        recursion_state = "WHOLE_DRIVE_CLOSED" if whole_recursion else "WHOLE_DRIVE_OPEN"
        expected["SURFACE:GOOGLE-DRIVE"] = f"{search_state}_{recursion_state}"
    if "SURFACE:LIBRARY" in subjects:
        library = _manifest_value(manifest, "surfaces", "library")
        listing_closed = (
            library.get("ownedListingPaginationClosed") if isinstance(library, Mapping) else None
        )
        recursion_supported = (
            library.get("mountedGoogleDriveRecursionSupported") if isinstance(library, Mapping) else None
        )
        if not isinstance(listing_closed, bool) or not isinstance(recursion_supported, bool):
            raise EstateDeltaError("Library source state is not a bounded listing observation")
        listing_state = "OWNED_LISTING_CLOSED" if listing_closed else "OWNED_LISTING_OPEN"
        recursion_state = (
            "MOUNTED_DRIVE_RECURSION_SUPPORTED"
            if recursion_supported
            else "MOUNTED_DRIVE_RECURSION_UNSUPPORTED"
        )
        expected["SURFACE:LIBRARY"] = f"{listing_state}_{recursion_state}"
    if "SURFACE:OWNER-OAUTH-APPS-SCRIPT" in subjects:
        expected["SURFACE:OWNER-OAUTH-APPS-SCRIPT"] = str(
            _manifest_value(manifest, "state", "ownerOauthAppsScript")
        )
    if "SURFACE:SITES" in subjects:
        sites = _manifest_value(manifest, "surfaces", "sites")
        owned_sites = sites.get("ownedSites") if isinstance(sites, Mapping) else None
        pagination_closed = sites.get("paginationClosed") if isinstance(sites, Mapping) else None
        if type(owned_sites) is not int or owned_sites < 0 or not isinstance(pagination_closed, bool):
            raise EstateDeltaError("Sites source state is not a bounded listing observation")
        if pagination_closed:
            expected["SURFACE:SITES"] = "NO_OWNED_SITES" if owned_sites == 0 else "OWNED_SITES_PRESENT"
        else:
            expected["SURFACE:SITES"] = "OWNED_SITES_LISTING_OPEN"
    if "SURFACE:WIF" in subjects:
        expected["SURFACE:WIF"] = str(_manifest_value(manifest, "state", "wif"))
    return expected


def validate_genesis_transaction_against_manifest(
    transaction: Mapping[str, Any],
    manifest: Mapping[str, Any],
    bounded_claim: Mapping[str, Any],
    source_payloads: Mapping[str, bytes | str] | None = None,
    supporting_payloads: Mapping[str, bytes | str] | None = None,
) -> dict[str, Any]:
    if supporting_payloads is None and source_payloads is not None:
        supporting_payloads = getattr(source_payloads, "supporting_payloads", None)
    structural = validate_transaction(transaction)
    body = transaction["body"]
    if body["mission_id"] != manifest.get("missionId"):
        raise EstateDeltaError("transaction mission does not match source census mission")
    if body["observed_at"] != manifest.get("observedAtUtc") or body["occurred_at"] != manifest.get("observedAtUtc"):
        raise EstateDeltaError("transaction observation time does not match source census")
    if body["authority"] != manifest.get("authority"):
        raise EstateDeltaError("transaction authority does not match source census")
    if body["scope"]["canonical_status"] != manifest.get("canonicalStatus"):
        raise EstateDeltaError("transaction status does not match source census")
    if manifest.get("mutations") != []:
        raise EstateDeltaError("source census contains mutations")
    observation_date = str(manifest.get("observedAtUtc", ""))[:10].replace("-", "")
    expected_transaction_id = f"FEDERATION-ESTATE-CENSUS-{observation_date}-001"
    if not (
        body["transaction_id"] == expected_transaction_id
        and body["sequence"] == 1
        and body["event_type"] == "CENSUS_SNAPSHOT"
    ):
        raise EstateDeltaError("transaction identity differs from census-genesis profile")
    if body["lineage"]["previous_transaction_id"] is not None:
        raise EstateDeltaError("census genesis cannot claim a lineage parent")
    if body["scope"]["claim_text"] != BOUNDED_SCOPE_CLAIM_TEXT:
        raise EstateDeltaError("transaction claim text is not the canonical bounded claim")
    expected_truth_boundary = bounded_truth_boundary(body["observed_at"])
    if body["completion"]["truth_boundary"] != expected_truth_boundary:
        raise EstateDeltaError("transaction truth boundary is not canonically bounded")

    source_coverage = bounded_claim.get("sourceCoverage") or {}
    expected = sorted(source_coverage.get("expected") or [])
    inspected = sorted(source_coverage.get("inspectedToEnd") or [])
    if body["scope"]["expected_sources"] != expected:
        raise EstateDeltaError("transaction expected coverage differs from bounded claim")
    if body["scope"]["inspected_to_end"] != inspected:
        raise EstateDeltaError("transaction inspected coverage differs from bounded claim")
    if body["scope"]["all_expected_bounded_sources_enumerated"] is not source_coverage.get("allExpectedSourcesEnumerated"):
        raise EstateDeltaError("transaction coverage closure differs from bounded claim")

    manifest_surfaces = manifest.get("surfaces") or {}
    expected_subjects: set[str] = set()
    for surface_key, subjects in MANIFEST_SUBJECTS.items():
        if surface_key in manifest_surfaces:
            expected_subjects.update(subjects)
    snapshots_by_id = {row["snapshot_id"]: row for row in body["surface_snapshots"]}
    projections = {row["subject_id"]: row for row in body["projections"]}
    inputs = {item["source_id"]: item for item in body["inputs"]}
    if set(projections) != expected_subjects:
        raise EstateDeltaError("transaction subjects do not match source manifest surfaces")
    if len(body["surface_snapshots"]) != len(expected_subjects):
        raise EstateDeltaError("census-genesis profile requires exactly one snapshot per subject")
    snapshots: dict[str, Mapping[str, Any]] = {}
    for subject_id, projection in projections.items():
        snapshot = snapshots_by_id.get(projection["winning_snapshot_id"])
        if snapshot is None or snapshot["subject_id"] != subject_id:
            raise EstateDeltaError("projection winner is unavailable for manifest fidelity")
        if snapshot["snapshot_id"] != SUBJECT_SNAPSHOT_ID[subject_id]:
            raise EstateDeltaError(f"transaction snapshot identity differs from census profile: {subject_id}")
        snapshots[subject_id] = snapshot

    expected_states = _expected_subject_states(manifest, expected_subjects)
    if set(expected_states) != expected_subjects:
        raise EstateDeltaError("manifest state projection does not cover every subject")
    for subject_id in sorted(expected_subjects):
        snapshot = snapshots[subject_id]
        projection = projections[subject_id]
        expected_proof, expected_hold = SUBJECT_PROOF_HOLD[subject_id]
        expected_evidence_class = SUBJECT_EVIDENCE_CLASS[subject_id]
        expected_state = expected_states[subject_id]
        actual_input_classes = {
            inputs[source_id]["source_class"] for source_id in snapshot["input_source_ids"]
        }
        if snapshot["surface"] != SUBJECT_SURFACE[subject_id]:
            raise EstateDeltaError(f"transaction surface differs from manifest contract: {subject_id}")
        if snapshot["observed_at"] != manifest["observedAtUtc"]:
            raise EstateDeltaError(f"transaction winner observation is stale: {subject_id}")
        if snapshot["evidence_class"] != expected_evidence_class:
            raise EstateDeltaError(f"transaction evidence class differs from manifest contract: {subject_id}")
        if actual_input_classes != SUBJECT_INPUT_SOURCE_CLASSES[subject_id]:
            raise EstateDeltaError(f"transaction input-source classes differ from manifest contract: {subject_id}")
        if set(snapshot["boundary_ids"]) != SUBJECT_BOUNDARY_IDS[subject_id]:
            raise EstateDeltaError(f"transaction boundary assignment differs from manifest contract: {subject_id}")
        if (
            snapshot["state"] != expected_state
            or projection["state"] != expected_state
            or snapshot["proof_state"] != expected_proof
            or projection["proof_state"] != expected_proof
            or projection["hold"] is not expected_hold
        ):
            raise EstateDeltaError(f"transaction state/proof/hold differs from manifest: {subject_id}")

    expected_metrics: dict[tuple[str, str], Any] = {}
    for key, path in MANIFEST_METRIC_PATHS.items():
        if key[0] not in expected_subjects:
            continue
        exists, expected_value = _lookup_path(manifest, path)
        if exists:
            expected_metrics[key] = expected_value
    actual_metrics: dict[tuple[str, str], Any] = {}
    for subject_id, snapshot in snapshots.items():
        for metric in snapshot["metrics"]:
            key = (subject_id, metric["name"])
            if key in actual_metrics:
                raise EstateDeltaError("duplicate subject metric")
            actual_metrics[key] = metric["value"]
    if set(actual_metrics) != set(expected_metrics):
        missing = sorted(f"{subject}:{name}" for subject, name in set(expected_metrics) - set(actual_metrics))
        extra = sorted(f"{subject}:{name}" for subject, name in set(actual_metrics) - set(expected_metrics))
        raise EstateDeltaError(f"transaction metric coverage mismatch: missing={missing} extra={extra}")
    for key, expected_value in expected_metrics.items():
        actual_value = actual_metrics[key]
        if type(actual_value) is not type(expected_value) or actual_value != expected_value:
            raise EstateDeltaError(f"transaction metric differs from manifest: {key[0]}:{key[1]}")

    required_boundary_ids = set().union(
        *(SUBJECT_BOUNDARY_IDS[subject_id] for subject_id in expected_subjects)
    )
    expected_boundaries = [
        {
            "boundary_id": boundary_id,
            "description": BOUNDARY_CONTRACTS[boundary_id]["description"],
            "state": "OPEN",
            "material_to_totality": True,
            "closure_evidence": BOUNDARY_CONTRACTS[boundary_id]["closure_evidence"],
            "avoidable_user_task": False,
        }
        for boundary_id in sorted(required_boundary_ids)
    ]
    if body["unresolved_boundaries"] != expected_boundaries:
        raise EstateDeltaError("transaction boundary records differ from census-genesis profile")
    manifest_boundaries = sorted(str(item) for item in manifest.get("unresolvedBoundaries") or [])
    transaction_boundaries = sorted(item["description"] for item in expected_boundaries)
    if transaction_boundaries != manifest_boundaries:
        raise EstateDeltaError("transaction boundaries differ from source manifest")

    if body["completion"]["independent_check_state"] != "PASSED_BOUNDED_SCOPE":
        raise EstateDeltaError("census-genesis independent bounded check is not passed")

    expected_inputs: dict[str, dict[str, Any]] = {}
    for source_class, label in GENESIS_INPUT_LABELS.items():
        source_id = f"SRC:{label}-{observation_date}"
        expected_inputs[source_id] = {
            "source_id": source_id,
            "source_class": source_class,
            "observed_at": manifest["observedAtUtc"],
            "locator_state": "SESSION_ARTIFACT_NOT_PUBLISHED",
            "proof_state": "DERIVED_VERIFIED",
        }
    if set(inputs) != set(expected_inputs):
        raise EstateDeltaError("transaction inputs differ from census-genesis source set")
    for source_id, expected_input in expected_inputs.items():
        actual_without_hash = {
            key: value for key, value in inputs[source_id].items() if key != "content_sha256"
        }
        if actual_without_hash != expected_input:
            raise EstateDeltaError(f"transaction input metadata differs from census profile: {source_id}")

    if source_payloads is not None:
        if set(source_payloads) != set(inputs):
            raise EstateDeltaError("source payload set does not match transaction inputs")
        parsed_sources: dict[str, Any] = {}
        payload_bytes_by_source_id: dict[str, bytes] = {}
        for source_id, payload in source_payloads.items():
            if isinstance(payload, str):
                payload_bytes = payload.encode("utf-8")
            elif isinstance(payload, bytes):
                payload_bytes = payload
            else:
                raise EstateDeltaError(f"source payload must be bytes or text: {source_id}")
            actual_hash = hashlib.sha256(payload_bytes).hexdigest()
            if inputs[source_id]["content_sha256"] != actual_hash:
                raise EstateDeltaError(f"source payload hash mismatch: {source_id}")
            try:
                parsed_sources[source_id] = json.loads(payload_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EstateDeltaError(f"source payload is not UTF-8 JSON: {source_id}") from exc
            payload_bytes_by_source_id[source_id] = payload_bytes
        parsed_by_class = {
            inputs[source_id]["source_class"]: parsed_sources[source_id]
            for source_id in parsed_sources
        }
        payload_bytes_by_class = {
            inputs[source_id]["source_class"]: payload_bytes_by_source_id[source_id]
            for source_id in payload_bytes_by_source_id
        }
        manifest_source_id = next(
            source_id for source_id, item in inputs.items()
            if item["source_class"] == "DERIVED_CENSUS_MANIFEST"
        )
        bounded_source_id = next(
            source_id for source_id, item in inputs.items()
            if item["source_class"] == "BOUNDED_CLAIM_GATE"
        )
        if canonical_json(parsed_sources[manifest_source_id]) != canonical_json(manifest):
            raise EstateDeltaError("supplied manifest object differs from hashed source payload")
        if canonical_json(parsed_sources[bounded_source_id]) != canonical_json(bounded_claim):
            raise EstateDeltaError("supplied bounded claim differs from hashed source payload")
        _validate_claim_gate_semantics(
            parsed_by_class["BOUNDED_CLAIM_GATE"], bounded=True
        )
        _validate_claim_gate_semantics(
            parsed_by_class["TOTALITY_REJECTION_GATE"], bounded=False
        )
        drift_private_values, source_anomalies = _validate_drift_semantics(
            parsed_by_class["DRIFT_READBACK"], manifest
        )
        oifa_report = parsed_by_class["FIDELITY_REPORT"]
        _validate_oifa_semantics(
            oifa_report, manifest, payload_bytes_by_class, supporting_payloads,
        )
        continuity_basis = str(
            (oifa_report.get("continuity_test") or {}).get("basis", "")
        ).casefold()
        if "baseline" in continuity_basis and not body["lineage"]["historical_baselines"]:
            raise EstateDeltaError("source continuity evidence requires retained historical lineage")
        contradiction_source_text = " ".join(
            str(item) for item in oifa_report.get("contradictions") or []
        ).casefold()
        for item in body["contradictions"]:
            subject_label = item["subject_id"].split(":", 1)[-1]
            canonical_claim = (
                f"Historical records described the {subject_label} route as active or verified."
            )
            if item["earlier_claim"] != canonical_claim:
                raise EstateDeltaError(
                    "genesis contradiction claim is outside the canonical public-safe template"
                )
            subject_token = subject_label.replace("-", " ").casefold()
            if subject_token not in contradiction_source_text:
                raise EstateDeltaError("transaction contradiction is not anchored in the OIFA source")
        if "SURFACE:WIF" in expected_subjects and "wif" in contradiction_source_text:
            wif_rows = [
                item for item in body["contradictions"]
                if item["subject_id"] == "SURFACE:WIF"
            ]
            if not (
                len(wif_rows) == 1
                and wif_rows[0]["current_snapshot_id"] == SUBJECT_SNAPSHOT_ID["SURFACE:WIF"]
                and wif_rows[0]["disposition"] == "SUPERSEDED_RETAINED"
                and wif_rows[0]["affects_totality"] is True
            ):
                raise EstateDeltaError("WIF source contradiction is not retained conservatively")
        _reject_known_private_source_values(
            transaction, manifest, drift_private_values
        )
        fidelity_state = "VALID_GENESIS_PROJECTION_FIDELITY_AND_SOURCE_BUNDLE"
    else:
        fidelity_state = "VALID_GENESIS_PROJECTION_FIDELITY_SOURCE_BUNDLE_UNCHECKED"
        source_anomalies = ["SOURCE_BYTES_UNCHECKED"]
    return {
        "state": fidelity_state,
        "transaction_id": structural["transaction_id"],
        "metric_count": len(actual_metrics),
        "subject_count": len(snapshots),
        "boundary_count": len(transaction_boundaries),
        "source_anomalies": source_anomalies,
        "event_hash": structural["event_hash"],
    }


def verify_chain(transactions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not transactions:
        raise EstateDeltaError("empty transaction chain is unproven")
    ordered = sorted(transactions, key=lambda item: item["body"]["sequence"])
    previous_hash: str | None = None
    previous_transaction_id: str | None = None
    seen_ids: set[str] = set()
    for expected_sequence, transaction in enumerate(ordered, start=1):
        result = validate_transaction(transaction)
        body = transaction["body"]
        if body["sequence"] != expected_sequence:
            raise EstateDeltaError("transaction sequence gap")
        if body["transaction_id"] in seen_ids:
            raise EstateDeltaError("duplicate transaction ID")
        if transaction["integrity"]["previous_event_hash"] != previous_hash:
            raise EstateDeltaError("previous event hash chain mismatch")
        if body["lineage"]["previous_transaction_id"] != previous_transaction_id:
            raise EstateDeltaError("previous transaction ID lineage mismatch")
        seen_ids.add(body["transaction_id"])
        previous_hash = result["event_hash"]
        previous_transaction_id = body["transaction_id"]
    return {
        "state": "VALID_STRUCTURAL_CHAIN",
        "transaction_count": len(ordered),
        "head_event_hash": previous_hash,
    }
