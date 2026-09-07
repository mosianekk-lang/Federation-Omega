"""Federation Adobe Ω v1 clean-room capability fabric.

This module does not contain or emulate Adobe proprietary source code. It
models publicly documented creative/document capability contracts and routes
them across explicitly-proven local or provider backends.

Source presence is not runtime proof. Local dependency discovery is deliberately
capped at AVAILABLE_UNVERIFIED until a representative operation receives
semantic readback. Provider state must be injected from fresh provider evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import importlib.util
import json
import shutil
from typing import Iterable, Mapping, Sequence


BUILD_ID = "BUILD-AO-011"
SYSTEM_ID = "FEDERATION-ADOBE-OMEGA-V1"
VERSION = "1.0.0"


class CapabilityFamily(str, Enum):
    RASTER_IMAGE = "RASTER_IMAGE"
    SELECTION_MASKING = "SELECTION_MASKING"
    GENERATIVE_IMAGE = "GENERATIVE_IMAGE"
    LAYERED_DOCUMENT = "LAYERED_DOCUMENT"
    PHOTO_DEVELOP = "PHOTO_DEVELOP"
    DESIGN_TEMPLATE = "DESIGN_TEMPLATE"
    PDF_DOCUMENT = "PDF_DOCUMENT"
    ASSET_LIBRARY = "ASSET_LIBRARY"
    VIDEO_TIMELINE = "VIDEO_TIMELINE"
    AUDIO = "AUDIO"
    PROVENANCE_RIGHTS = "PROVENANCE_RIGHTS"
    AUTOMATION_ORCHESTRATION = "AUTOMATION_ORCHESTRATION"


class CapabilityMode(str, Enum):
    READ = "READ"
    TRANSFORM = "TRANSFORM"
    GENERATE = "GENERATE"
    MANAGE = "MANAGE"


class BackendKind(str, Enum):
    LOCAL = "LOCAL"
    FEDERATION = "FEDERATION"
    PROVIDER = "PROVIDER"


class BackendState(str, Enum):
    VERIFIED_OPERATIONAL = "VERIFIED_OPERATIONAL"
    AVAILABLE_UNVERIFIED = "AVAILABLE_UNVERIFIED"
    READ_ONLY = "READ_ONLY"
    CIRCUIT_HELD = "CIRCUIT_HELD"
    ENTITLEMENT_HELD = "ENTITLEMENT_HELD"
    LICENSE_HELD = "LICENSE_HELD"
    NOT_INSTALLED = "NOT_INSTALLED"
    UNAVAILABLE = "UNAVAILABLE"


class ProofLevel(str, Enum):
    NONE = "NONE"
    DISCOVERED = "DISCOVERED"
    EXECUTED = "EXECUTED"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    PERSISTENCE_ROLLBACK = "PERSISTENCE_ROLLBACK"


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    family: CapabilityFamily
    mode: CapabilityMode
    description: str
    proof_contract: str
    public_benchmark: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def validate(self) -> "CapabilitySpec":
        if not self.capability_id or "." not in self.capability_id:
            raise ValueError("capability_id must be namespaced")
        if not self.description or not self.proof_contract:
            raise ValueError(f"{self.capability_id} requires description and proof contract")
        return self


@dataclass(frozen=True)
class BackendSpec:
    backend_id: str
    kind: BackendKind
    capabilities: frozenset[str]
    priority: int
    sovereign: bool = False
    executables_any: tuple[str, ...] = ()
    python_modules_any: tuple[str, ...] = ()
    license_gate_required: bool = False
    license_note: str = ""
    notes: str = ""

    def validate(self, known_capabilities: frozenset[str]) -> "BackendSpec":
        unknown = self.capabilities - known_capabilities
        if unknown:
            raise ValueError(f"{self.backend_id} references unknown capabilities: {sorted(unknown)}")
        if self.kind is BackendKind.LOCAL and not (
            self.executables_any or self.python_modules_any or self.backend_id == "LOCAL_ASSET_CORE"
        ):
            raise ValueError(f"{self.backend_id} has no discovery contract")
        return self


@dataclass(frozen=True)
class BackendSnapshot:
    backend_id: str
    state: BackendState
    installed: bool
    license_accepted: bool = False
    semantic_readback_verified: bool = False
    proof_level: ProofLevel = ProofLevel.NONE
    observed_identity: str | None = None
    details: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return self.state in {
            BackendState.VERIFIED_OPERATIONAL,
            BackendState.AVAILABLE_UNVERIFIED,
            BackendState.READ_ONLY,
        }


@dataclass(frozen=True)
class RouteRequest:
    capability_id: str
    prefer_sovereign: bool = True
    allow_provider: bool = True
    require_semantic_readback: bool = False


@dataclass(frozen=True)
class RouteDecision:
    capability_id: str
    selected_backend: str | None
    mode: str
    state: BackendState | None
    proof_level: ProofLevel
    rejected: tuple[tuple[str, str], ...]
    open_builds: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ProofReceipt:
    capability_id: str
    backend_id: str
    proof_level: ProofLevel
    semantic_readback_verified: bool
    evidence_refs: tuple[str, ...]
    outcome_fingerprint: str

    @classmethod
    def issue(
        cls,
        *,
        capability_id: str,
        backend_id: str,
        proof_level: ProofLevel,
        semantic_readback_verified: bool,
        evidence_refs: Sequence[str],
        outcome: Mapping[str, object],
    ) -> "ProofReceipt":
        if proof_level in {ProofLevel.SEMANTIC_READBACK, ProofLevel.PERSISTENCE_ROLLBACK} and not semantic_readback_verified:
            raise ValueError("semantic proof level requires semantic readback")
        payload = {
            "capability_id": capability_id,
            "backend_id": backend_id,
            "proof_level": proof_level.value,
            "semantic_readback_verified": semantic_readback_verified,
            "evidence_refs": tuple(evidence_refs),
            "outcome": dict(outcome),
        }
        fingerprint = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        return cls(
            capability_id=capability_id,
            backend_id=backend_id,
            proof_level=proof_level,
            semantic_readback_verified=semantic_readback_verified,
            evidence_refs=tuple(evidence_refs),
            outcome_fingerprint=fingerprint,
        )


def _c(
    cid: str,
    family: CapabilityFamily,
    mode: CapabilityMode,
    description: str,
    proof: str,
    *benchmarks: str,
    tags: tuple[str, ...] = (),
) -> CapabilitySpec:
    return CapabilitySpec(cid, family, mode, description, proof, tuple(benchmarks), tags).validate()


_CAPABILITY_LIST: tuple[CapabilitySpec, ...] = (
    _c("image.resize_crop", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Resize, crop, rotate and reframe raster images.", "Output dimensions/pixels match requested geometry.", "Photoshop"),
    _c("image.format_convert", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Convert supported raster formats with controlled quality.", "Decoded output format and dimensions read back.", "Photoshop"),
    _c("image.tone_color", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Exposure, contrast, highlights, shadows, HSL, vibrance and color-temperature adjustment.", "Requested adjustment set plus output histogram/metadata readback.", "Photoshop", "Lightroom"),
    _c("image.blur_sharpen", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Gaussian/lens blur and sharpening.", "Filter parameters plus output artifact readback.", "Photoshop"),
    _c("image.noise_grain", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Noise, grain and texture transforms.", "Transform parameters plus output artifact readback.", "Photoshop"),
    _c("image.overlay_composite", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Color overlays and multi-image compositing.", "Layer/composite manifest plus pixel output readback.", "Photoshop"),
    _c("image.auto_straighten", CapabilityFamily.RASTER_IMAGE, CapabilityMode.TRANSFORM, "Automatic geometric straightening and perspective correction.", "Detected transform plus corrected geometry readback.", "Lightroom"),
    _c("select.subject", CapabilityFamily.SELECTION_MASKING, CapabilityMode.READ, "Detect and mask the primary subject.", "Mask dimensions, non-empty area and source fingerprint readback.", "Photoshop"),
    _c("select.object_prompt", CapabilityFamily.SELECTION_MASKING, CapabilityMode.READ, "Prompt-guided object/region selection.", "Mask and selected-region evidence readback.", "Photoshop"),
    _c("select.remove_background", CapabilityFamily.SELECTION_MASKING, CapabilityMode.TRANSFORM, "Isolate subject and remove/replace background.", "Alpha/background result plus subject-preservation check.", "Photoshop"),
    _c("select.mask_ops", CapabilityFamily.SELECTION_MASKING, CapabilityMode.TRANSFORM, "Invert, combine, refine and apply masks.", "Mask algebra and target-region readback.", "Photoshop"),
    _c("image.vectorize", CapabilityFamily.SELECTION_MASKING, CapabilityMode.TRANSFORM, "Convert suitable raster artwork into vector paths.", "Vector document/path count and render comparison.", "Illustrator", "Photoshop"),
    _c("gen.image", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Generate an image from a text/image conditioning request.", "Generated asset ID/hash, model/license identity and semantic review.", "Firefly"),
    _c("gen.expand", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Generatively expand image canvas.", "Original-region preservation plus expanded output readback.", "Firefly"),
    _c("gen.fill", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Generatively fill a masked region.", "Mask-targeted change and preserved-region comparison.", "Firefly"),
    _c("gen.instruct_edit", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Instruction-driven image edit.", "Instruction/result semantic adjudication plus source-preservation evidence.", "Firefly", "Photoshop"),
    _c("gen.object_composite", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Composite a described/generated object into a scene.", "Object presence, placement and output artifact readback.", "Firefly"),
    _c("gen.similar_variation", CapabilityFamily.GENERATIVE_IMAGE, CapabilityMode.GENERATE, "Produce controlled visual variations/similar images.", "Source linkage, variation parameters and output hashes.", "Firefly"),
    _c("layer.document_manifest", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.READ, "Read structured document/layer tree, metadata and thumbnails.", "Layer tree, document metadata and source identity readback.", "Photoshop API"),
    _c("layer.mutate", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Add, edit, delete, move and reorder layers.", "Post-operation layer tree exactly matches requested mutation.", "Photoshop API"),
    _c("layer.adjustment", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Create and edit adjustment layers.", "Adjustment parameters and rendered-result readback.", "Photoshop API"),
    _c("layer.smart_object", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Manage linked/embedded smart-object-like assets.", "Reference identity, transform and render readback.", "Photoshop API"),
    _c("layer.mask_group", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Manage layer masks and groups.", "Hierarchy/mask state plus render readback.", "Photoshop API"),
    _c("layer.artboards", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Create and manage artboards/canvases.", "Artboard manifest and rendered outputs read back.", "Photoshop API"),
    _c("layer.actions_scripts", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.MANAGE, "Execute reusable deterministic action/script pipelines.", "Action identity, parameters, terminal state and output manifest.", "Photoshop API"),
    _c("layer.composite_export", CapabilityFamily.LAYERED_DOCUMENT, CapabilityMode.TRANSFORM, "Render layered content into flattened deliverables.", "Output format, dimensions and source-manifest linkage.", "Photoshop API"),
    _c("photo.auto_tone", CapabilityFamily.PHOTO_DEVELOP, CapabilityMode.TRANSFORM, "Automatic exposure/tone balancing.", "Applied tone parameters plus output histogram/metadata.", "Lightroom"),
    _c("photo.preset", CapabilityFamily.PHOTO_DEVELOP, CapabilityMode.TRANSFORM, "Apply a named photo-development preset.", "Preset identity/version plus output artifact readback.", "Lightroom"),
    _c("photo.xmp_edit", CapabilityFamily.PHOTO_DEVELOP, CapabilityMode.TRANSFORM, "Apply portable XMP-style develop parameters.", "Parameter manifest plus output artifact readback.", "Lightroom"),
    _c("photo.exposure_color", CapabilityFamily.PHOTO_DEVELOP, CapabilityMode.TRANSFORM, "Fine exposure/color/HSL/vibrance adjustment.", "Requested parameters plus output readback.", "Lightroom"),
    _c("photo.sharp_noise_lens", CapabilityFamily.PHOTO_DEVELOP, CapabilityMode.TRANSFORM, "Sharpening, noise reduction and lens/optics correction.", "Applied controls plus output quality/metadata readback.", "Lightroom"),
    _c("design.template_search", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.READ, "Search reusable design templates.", "Template IDs, previews and query provenance.", "Adobe Express"),
    _c("design.create_edit", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Create/edit a reusable visual design document.", "Document identity and post-edit readback.", "Adobe Express"),
    _c("design.fill_text", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Fill/replace template text.", "Text content readback in target document.", "Adobe Express"),
    _c("design.replace_image", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Replace a design image/visual element.", "Target element and replacement readback.", "Adobe Express"),
    _c("design.background_color", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Change design background color.", "Background value and rendered preview readback.", "Adobe Express"),
    _c("design.animate", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Apply page/element animation.", "Animation preset/timeline readback.", "Adobe Express"),
    _c("design.resize_export", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.TRANSFORM, "Resize/adapt and export designs for channels.", "Output dimensions/format and design lineage.", "Adobe Express"),
    _c("design.brand_assets", CapabilityFamily.DESIGN_TEMPLATE, CapabilityMode.MANAGE, "Apply reusable brand colors/fonts/logos where licensed.", "Brand asset identities and output conformance.", "Adobe Express", "Creative Cloud Libraries"),
    _c("pdf.create", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.GENERATE, "Create PDF from supported source content.", "PDF parses; page count/metadata read back.", "Acrobat"),
    _c("pdf.ocr", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.TRANSFORM, "Add searchable OCR text layer to scanned PDFs.", "Searchable text and page mapping read back.", "Acrobat"),
    _c("pdf.extract", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.READ, "Extract structured text/tables/figures/markdown.", "Page/element structure with source page coordinates.", "Acrobat"),
    _c("pdf.export_office", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.TRANSFORM, "Export PDFs to editable office formats.", "Target file format opens and source page/content mapping is checked.", "Acrobat"),
    _c("pdf.compress", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.TRANSFORM, "Reduce PDF size without unintended content loss.", "Size delta plus page/content integrity readback.", "Acrobat"),
    _c("pdf.page_organize", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.MANAGE, "Combine, split, reorder, rotate and delete PDF pages.", "Page sequence/count exactly read back.", "Acrobat"),
    _c("pdf.redact_highlight", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.MANAGE, "Redact or highlight specified content.", "Target strings/regions absent or highlighted after render/text readback.", "Acrobat"),
    _c("pdf.edit_annotate", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.MANAGE, "Edit visible PDF content and annotations.", "Edited content/annotation manifest read back.", "Acrobat"),
    _c("pdf.properties", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.READ, "Read PDF page count, metadata, encryption/signature and structure properties.", "Independent parsed property result.", "Acrobat"),
    _c("pdf.accessibility", CapabilityFamily.PDF_DOCUMENT, CapabilityMode.TRANSFORM, "Tag/structure PDFs for accessibility workflows.", "Tag tree and accessibility validation result.", "Acrobat"),
    _c("asset.store", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Store immutable creative assets with content hash.", "Asset ID/hash and persistence readback.", "Creative Cloud"),
    _c("asset.search", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.READ, "Search assets by metadata/text/tags.", "Stable result IDs plus query provenance.", "Creative Cloud"),
    _c("asset.library_elements", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Manage reusable library elements such as colors, graphics, templates and styles.", "Library/element IDs and representation readback.", "Creative Cloud Libraries"),
    _c("asset.renditions", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Generate/manage previews and alternate renditions.", "Rendition metadata/hash readback.", "Creative Cloud Libraries"),
    _c("asset.versioning", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Maintain asset versions and lineage.", "Version chain and parent/source hashes.", "Creative Cloud"),
    _c("asset.scopes", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Represent private/shared/public access scopes without silently granting authority.", "Policy state plus target access test.", "Creative Cloud"),
    _c("asset.metadata_provenance", CapabilityFamily.ASSET_LIBRARY, CapabilityMode.MANAGE, "Persist searchable metadata, rights and provenance.", "Metadata/provenance record hash linked to asset.", "Creative Cloud"),
    _c("video.transcode_resize", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.TRANSFORM, "Transcode and resize video deliverables.", "Codec/container/dimensions/duration readback.", "Premiere"),
    _c("video.smart_reframe", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.TRANSFORM, "Reframe video for target aspect while preserving subject.", "Frame geometry and subject-visibility sample readback.", "Premiere"),
    _c("video.scene_detect", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.READ, "Detect scene/shot boundaries.", "Timecode boundary list plus representative frame evidence.", "Premiere"),
    _c("video.timeline_edit", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.MANAGE, "Represent and edit clips/tracks/transitions on a portable timeline.", "Timeline serialization and rendered result linkage.", "Premiere"),
    _c("video.captions", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.MANAGE, "Create/synchronize captions/subtitles.", "Caption text/timecode and render readback.", "Premiere"),
    _c("video.render_export", CapabilityFamily.VIDEO_TIMELINE, CapabilityMode.TRANSFORM, "Render/export timeline to target deliverable.", "Output media properties and timeline-source hash linkage.", "Premiere"),
    _c("audio.enhance", CapabilityFamily.AUDIO, CapabilityMode.TRANSFORM, "Speech cleanup, loudness/denoise/enhancement pipeline.", "Audio properties plus objective/semantic quality checks.", "Premiere", "Adobe Podcast"),
    _c("audio.transcribe", CapabilityFamily.AUDIO, CapabilityMode.READ, "Transcribe speech with timestamped segments.", "Segment timestamps/text and source hash linkage.", "Premiere"),
    _c("rights.license_gate", CapabilityFamily.PROVENANCE_RIGHTS, CapabilityMode.READ, "Determine whether a backend/model/asset license is explicitly admitted for the mission.", "License identity, source and allow/hold decision.", "Content Credentials"),
    _c("rights.provenance_manifest", CapabilityFamily.PROVENANCE_RIGHTS, CapabilityMode.MANAGE, "Attach provenance/lineage metadata to generated or transformed assets.", "Manifest hash and asset binding readback.", "Content Credentials"),
    _c("rights.content_hash", CapabilityFamily.PROVENANCE_RIGHTS, CapabilityMode.READ, "Compute stable content fingerprints for lineage and deduplication.", "Independent hash recomputation.", "Creative Cloud"),
    _c("orchestration.mission_compile", CapabilityFamily.AUTOMATION_ORCHESTRATION, CapabilityMode.MANAGE, "Compile natural-language creative intent into typed operations and proof contracts.", "Typed plan validates against capability registry.", "Adobe for ChatGPT"),
    _c("orchestration.batch", CapabilityFamily.AUTOMATION_ORCHESTRATION, CapabilityMode.MANAGE, "Batch safe independent creative operations with collision controls.", "Per-item terminal receipts and deterministic fan-in.", "Adobe for ChatGPT"),
    _c("orchestration.failover", CapabilityFamily.AUTOMATION_ORCHESTRATION, CapabilityMode.MANAGE, "Route around unavailable providers without lowering required outcome silently.", "Primary/fallback route decision plus final proof.", "Adobe for ChatGPT"),
    _c("orchestration.health_circuit", CapabilityFamily.AUTOMATION_ORCHESTRATION, CapabilityMode.MANAGE, "Track backend health and circuit-break repeated failures.", "Fresh snapshot and failure-fingerprint state.", "Adobe for ChatGPT"),
    _c("orchestration.semantic_readback", CapabilityFamily.AUTOMATION_ORCHESTRATION, CapabilityMode.READ, "Adjudicate output against requested semantic target.", "Evidence-bound semantic verdict.", "Adobe for ChatGPT"),
)

ADOBE_OMEGA_CAPABILITIES: dict[str, CapabilitySpec] = {
    spec.capability_id: spec for spec in _CAPABILITY_LIST
}


def _ids(*prefixes: str) -> frozenset[str]:
    return frozenset(
        cid for cid in ADOBE_OMEGA_CAPABILITIES
        if any(cid.startswith(prefix) for prefix in prefixes)
    )


BACKENDS: dict[str, BackendSpec] = {
    "LOCAL_RASTER": BackendSpec(
        "LOCAL_RASTER", BackendKind.LOCAL,
        _ids("image.") | frozenset({"photo.auto_tone", "photo.exposure_color", "photo.sharp_noise_lens"}),
        priority=10, sovereign=True,
        executables_any=("vips", "magick", "convert"),
        python_modules_any=("cv2", "PIL"),
        license_note="Each installed engine retains its own upstream license.",
        notes="Raster/color/geometry adapter family; exact operation support is runtime-tested per capability.",
    ),
    "LOCAL_SEGMENTATION": BackendSpec(
        "LOCAL_SEGMENTATION", BackendKind.LOCAL,
        _ids("select."),
        priority=12, sovereign=True,
        executables_any=("rembg",),
        python_modules_any=("rembg", "sam2"),
        license_note="Runtime must record the selected engine/model license before promotion.",
    ),
    "LOCAL_GENERATIVE": BackendSpec(
        "LOCAL_GENERATIVE", BackendKind.LOCAL,
        _ids("gen."),
        priority=20, sovereign=True,
        python_modules_any=("diffusers",),
        license_gate_required=True,
        license_note="Library license is not model license; exact model/checkpoint license must be admitted.",
    ),
    "LOCAL_PDF": BackendSpec(
        "LOCAL_PDF", BackendKind.LOCAL,
        _ids("pdf."),
        priority=8, sovereign=True,
        executables_any=("qpdf", "ocrmypdf"),
        python_modules_any=("pikepdf",),
        license_note="Use installed component licenses as declared upstream; preserve attribution where required.",
    ),
    "LOCAL_VIDEO": BackendSpec(
        "LOCAL_VIDEO", BackendKind.LOCAL,
        _ids("video.") | _ids("audio."),
        priority=15, sovereign=True,
        executables_any=("ffmpeg", "ffprobe"),
        python_modules_any=("opentimelineio", "scenedetect"),
        license_note="FFmpeg build configuration/license must be inspected; codec patent/licensing remains deployment-specific.",
    ),
    "LOCAL_ASSET_CORE": BackendSpec(
        "LOCAL_ASSET_CORE", BackendKind.LOCAL,
        _ids("asset.") | _ids("rights.") | _ids("orchestration."),
        priority=5, sovereign=True,
        license_note="Stdlib control-plane foundation; storage/index adapters still require runtime proof.",
        notes="Built-in metadata/router contracts exist in source but are not auto-promoted to VERIFIED_OPERATIONAL.",
    ),
    "ADOBE_ACROBAT_NATIVE": BackendSpec(
        "ADOBE_ACROBAT_NATIVE", BackendKind.PROVIDER,
        _ids("pdf."),
        priority=40, sovereign=False,
        notes="Optional provider lane. State must be injected from fresh Adobe Acrobat evidence.",
    ),
    "ADOBE_EXPRESS_NATIVE": BackendSpec(
        "ADOBE_EXPRESS_NATIVE", BackendKind.PROVIDER,
        _ids("design."),
        priority=50, sovereign=False,
        notes="Optional provider lane. Read/write entitlement is evaluated from fresh provider evidence.",
    ),
    "ADOBE_UNIFIED_NATIVE": BackendSpec(
        "ADOBE_UNIFIED_NATIVE", BackendKind.PROVIDER,
        frozenset(ADOBE_OMEGA_CAPABILITIES),
        priority=60, sovereign=False,
        notes="Optional Adobe unified connector. Never assumed healthy from installation alone.",
    ),
    "FEDERATION_IMAGE_PROVIDER": BackendSpec(
        "FEDERATION_IMAGE_PROVIDER", BackendKind.FEDERATION,
        _ids("gen."),
        priority=30, sovereign=False,
        license_gate_required=True,
        notes="Generic governed image-generation adapter; provider/model identity and license are supplied at runtime.",
    ),
}


ROUTABLE_STATES = {
    BackendState.VERIFIED_OPERATIONAL,
    BackendState.AVAILABLE_UNVERIFIED,
    BackendState.READ_ONLY,
}


def validate_registry() -> None:
    if len(ADOBE_OMEGA_CAPABILITIES) != len(_CAPABILITY_LIST):
        raise ValueError("duplicate capability_id")
    known = frozenset(ADOBE_OMEGA_CAPABILITIES)
    for spec in ADOBE_OMEGA_CAPABILITIES.values():
        spec.validate()
    for backend in BACKENDS.values():
        backend.validate(known)
    missing_families = set(CapabilityFamily) - {c.family for c in ADOBE_OMEGA_CAPABILITIES.values()}
    if missing_families:
        raise ValueError(f"capability families have no contract: {sorted(x.value for x in missing_families)}")


def probe_local_backends(
    *,
    license_acceptance: Iterable[str] = (),
    which=shutil.which,
    find_spec=importlib.util.find_spec,
) -> dict[str, BackendSnapshot]:
    """Discover local dependency presence without promoting it to verified runtime.

    A discovered executable/module yields AVAILABLE_UNVERIFIED. A license-gated
    backend yields LICENSE_HELD until its exact runtime/model license is admitted.
    """
    accepted = frozenset(license_acceptance)
    snapshots: dict[str, BackendSnapshot] = {}
    for backend in BACKENDS.values():
        if backend.kind is not BackendKind.LOCAL:
            continue
        if backend.backend_id == "LOCAL_ASSET_CORE":
            snapshots[backend.backend_id] = BackendSnapshot(
                backend.backend_id,
                BackendState.AVAILABLE_UNVERIFIED,
                installed=True,
                license_accepted=True,
                proof_level=ProofLevel.DISCOVERED,
                details=("stdlib control-plane source present; runtime persistence unverified",),
            )
            continue
        found_exec = tuple(name for name in backend.executables_any if which(name))
        found_modules = tuple(name for name in backend.python_modules_any if find_spec(name) is not None)
        installed = bool(found_exec or found_modules)
        license_ok = (not backend.license_gate_required) or backend.backend_id in accepted
        if not installed:
            state = BackendState.NOT_INSTALLED
        elif not license_ok:
            state = BackendState.LICENSE_HELD
        else:
            state = BackendState.AVAILABLE_UNVERIFIED
        snapshots[backend.backend_id] = BackendSnapshot(
            backend.backend_id,
            state,
            installed=installed,
            license_accepted=license_ok,
            semantic_readback_verified=False,
            proof_level=ProofLevel.DISCOVERED if installed else ProofLevel.NONE,
            details=(
                f"executables={','.join(found_exec) or '-'}",
                f"modules={','.join(found_modules) or '-'}",
            ),
        )
    return snapshots


class AdobeOmegaRouter:
    """Proof-aware local-first router over the Adobe Ω capability graph."""

    def __init__(
        self,
        *,
        capabilities: Mapping[str, CapabilitySpec] = ADOBE_OMEGA_CAPABILITIES,
        backends: Mapping[str, BackendSpec] = BACKENDS,
    ):
        self.capabilities = dict(capabilities)
        self.backends = dict(backends)
        validate_registry()

    @staticmethod
    def _eligible_for_mode(spec: CapabilitySpec, snapshot: BackendSnapshot) -> bool:
        if snapshot.state is BackendState.READ_ONLY and spec.mode is not CapabilityMode.READ:
            return False
        return snapshot.state in ROUTABLE_STATES

    def route(
        self,
        request: RouteRequest,
        snapshots: Mapping[str, BackendSnapshot],
    ) -> RouteDecision:
        spec = self.capabilities.get(request.capability_id)
        if spec is None:
            raise KeyError(f"unknown capability: {request.capability_id}")

        rejected: list[tuple[str, str]] = []
        candidates: list[tuple[tuple[int, int, int, int], BackendSpec, BackendSnapshot]] = []
        for backend in self.backends.values():
            if request.capability_id not in backend.capabilities:
                continue
            snapshot = snapshots.get(backend.backend_id)
            if snapshot is None:
                rejected.append((backend.backend_id, "NO_FRESH_SNAPSHOT"))
                continue
            if backend.kind is BackendKind.PROVIDER and not request.allow_provider:
                rejected.append((backend.backend_id, "PROVIDER_DISABLED_BY_REQUEST"))
                continue
            if backend.license_gate_required and not snapshot.license_accepted:
                rejected.append((backend.backend_id, "LICENSE_NOT_ADMITTED"))
                continue
            if not self._eligible_for_mode(spec, snapshot):
                rejected.append((backend.backend_id, f"STATE_{snapshot.state.value}"))
                continue
            if request.require_semantic_readback and not snapshot.semantic_readback_verified:
                rejected.append((backend.backend_id, "SEMANTIC_READBACK_REQUIRED"))
                continue

            sovereign_rank = 0 if (request.prefer_sovereign and backend.sovereign) else 1
            verified_rank = 0 if snapshot.state is BackendState.VERIFIED_OPERATIONAL else 1
            kind_rank = {BackendKind.LOCAL: 0, BackendKind.FEDERATION: 1, BackendKind.PROVIDER: 2}[backend.kind]
            candidates.append(((sovereign_rank, verified_rank, kind_rank, backend.priority), backend, snapshot))

        if not candidates:
            gap = f"{BUILD_ID}:{request.capability_id}"
            return RouteDecision(
                capability_id=request.capability_id,
                selected_backend=None,
                mode="BUILD_REQUIRED",
                state=None,
                proof_level=ProofLevel.NONE,
                rejected=tuple(sorted(rejected)),
                open_builds=(gap,),
                reason="No eligible backend has the required current state, license and proof.",
            )

        _, backend, snapshot = min(candidates, key=lambda item: item[0])
        mode = (
            "SOVEREIGN_LOCAL"
            if backend.kind is BackendKind.LOCAL and backend.sovereign
            else "FEDERATION_FALLBACK"
            if backend.kind is BackendKind.FEDERATION
            else "OPTIONAL_PROVIDER"
        )
        return RouteDecision(
            capability_id=request.capability_id,
            selected_backend=backend.backend_id,
            mode=mode,
            state=snapshot.state,
            proof_level=snapshot.proof_level,
            rejected=tuple(sorted(rejected)),
            open_builds=(),
            reason="Minimum sufficient eligible backend selected without trust transfer.",
        )


def capability_family_counts() -> dict[str, int]:
    counts = {family.value: 0 for family in CapabilityFamily}
    for spec in ADOBE_OMEGA_CAPABILITIES.values():
        counts[spec.family.value] += 1
    return counts


def parity_report(
    snapshots: Mapping[str, BackendSnapshot],
    *,
    allow_provider: bool = True,
) -> dict[str, object]:
    """Return a conservative current parity view.

    FULL_PARITY is true only when every capability can be routed to a backend
    whose semantic readback is already verified. This function never converts
    source/dependency discovery into runtime parity.
    """
    router = AdobeOmegaRouter()
    routed = 0
    semantic_verified = 0
    gaps: list[str] = []
    for cid in ADOBE_OMEGA_CAPABILITIES:
        basic = router.route(RouteRequest(cid, allow_provider=allow_provider), snapshots)
        if basic.selected_backend is not None:
            routed += 1
        strong = router.route(
            RouteRequest(cid, allow_provider=allow_provider, require_semantic_readback=True),
            snapshots,
        )
        if strong.selected_backend is not None:
            semantic_verified += 1
        else:
            gaps.append(cid)
    total = len(ADOBE_OMEGA_CAPABILITIES)
    return {
        "system_id": SYSTEM_ID,
        "version": VERSION,
        "total_capabilities": total,
        "routed_capabilities": routed,
        "semantic_verified_capabilities": semantic_verified,
        "gap_capabilities": tuple(gaps),
        "full_parity": semantic_verified == total,
        "truth_boundary": "Source/discovery is not runtime proof; full parity requires semantic readback per capability.",
    }


validate_registry()
