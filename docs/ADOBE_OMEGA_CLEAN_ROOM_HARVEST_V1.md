# Federation Adobe Ω v1 — Clean-Room Capability Harvest and Sovereign Runtime Contract

**System ID:** `FEDERATION-ADOBE-OMEGA-V1`  
**AO-CRA build:** `BUILD-AO-011`  
**Authority ceiling:** `A1_INTERNAL`  
**External-effect default:** `false`  
**Status represented by this document:** source/design contract only. Runtime capability is proved separately per backend and per operation.

## 1. Objective

Federation Adobe Ω is a provider-neutral creative/document operating layer designed to preserve the useful workflow capabilities associated with Adobe's public product/API surface without depending on a single Adobe connector or copying Adobe proprietary implementation.

The clean-room rule is strict:

- harvest public behavior, public API contracts, open standards and observable workflow semantics;
- do not copy Adobe source code, private protocols, reverse-engineered secrets, protected implementation details or credential material;
- do not impersonate Adobe products or claim Adobe compatibility beyond tested formats/contracts;
- do not bypass provider entitlement, licensing, DRM, access control or account policy;
- retain upstream license/provenance obligations for every third-party engine and every model/checkpoint;
- source code, installed dependencies and provider installation are not runtime proof.

Adobe remains an optional provider cell. Adobe Ω owns the mission-level capability contract and can route to local, Federation or provider backends only when each backend is freshly eligible.

## 2. Why this build exists

The live provider evidence that triggered `BUILD-AO-011` showed a fragmented Adobe estate:

| Provider lane | Fresh observed behavior | Adobe Ω treatment |
|---|---|---|
| Adobe web account | authenticated/healthy | account health only; does not imply connector authority |
| Standalone Acrobat | create + properties readback verified | optional verified PDF provider lane |
| Adobe Express | template search works | optional read/discovery lane |
| Adobe Express edit | account-type entitlement denial | `ENTITLEMENT_HELD` for writes |
| Unified Adobe / Photoshop / Firefly / Creative Cloud | MCP transport probe HTTP 403 | `CIRCUIT_HELD` until fresh recovery proof |
| Separate Photoshop/Lightroom connectors | not exposed as current independent lanes | no fabricated route |

The design goal is therefore not “replace Adobe with one clone.” It is to make each useful capability a typed, independently testable contract with multiple eligible implementations.

## 3. Public capability harvest

The following families are derived from public Adobe product/API behavior and mapped into provider-neutral contracts in `federation/adobe_omega_v1.py`.

### 3.1 Raster image / Photoshop-class transforms

Harvested behavior:

- resize, crop, rotate and reframe;
- format conversion;
- exposure/contrast/highlights/shadows/HSL/vibrance/color-temperature adjustment;
- blur/sharpen, noise/grain and overlays;
- composite generation;
- automatic crop/straighten/perspective-like correction.

Public benchmark family: Photoshop / Photoshop API / Lightroom-style develop controls.

In-house route candidates:

- `libvips` for high-throughput, low-memory image transforms;
- ImageMagick for broad format/transformation coverage;
- OpenCV/Pillow adapters for deterministic image/CV primitives where appropriate.

### 3.2 Selection, masks and subject isolation

Harvested behavior:

- select subject;
- prompt-guided object/region selection;
- remove/replace background;
- invert/combine/refine masks;
- vectorization of suitable artwork.

In-house route candidates:

- `rembg` for background isolation;
- SAM-family adapters for promptable segmentation where exact code/checkpoint licensing is admitted;
- OpenCV for deterministic mask morphology and geometry.

### 3.3 Firefly-class generative imaging

Harvested behavior:

- text/image-conditioned generation;
- generative expand;
- masked fill;
- instruction-based edit;
- object composite;
- variation/similarity workflows.

In-house route candidates:

- provider-neutral model adapter over Diffusers-compatible pipelines;
- Federation-hosted image-generation providers where separately authorised;
- model registry that records model/checkpoint identity, license, safety policy, cost class and proof requirements.

**Hard rule:** an open-source inference library does not grant a model license. `LOCAL_GENERATIVE` remains `LICENSE_HELD` until the exact selected model/checkpoint license is admitted.

### 3.4 Structured layered-document / Photoshop API parity

Harvested behavior:

- document/layer manifest;
- layer add/edit/delete/move/reorder;
- adjustment layers;
- masks and groups;
- smart-object-like linked/embedded assets;
- artboards;
- reusable action/script execution;
- composite/export.

Adobe Ω treats these as **document graph contracts**, not as a promise to reproduce the PSD engine internally on day one. The first sovereign implementation may use an internal normalized scene/layer graph with import/export adapters. Format-specific claims require round-trip fixtures and independent render checks.

### 3.5 Lightroom-class photo development

Harvested behavior:

- Auto Tone;
- auto straighten;
- named presets;
- XMP-style parameter interchange;
- exposure/color/HSL/vibrance adjustments;
- sharpening, noise reduction and optics correction.

The design deliberately separates non-destructive develop parameters from raster rendering so the same recipe can be evaluated across multiple engines.

### 3.6 Express-class design/template workflows

Harvested behavior:

- template search;
- design create/edit;
- fill/replace text;
- image replacement;
- background color;
- animation;
- resize/adapt/export;
- reusable brand assets.

Adobe Ω target:

- internal `DesignDocument` / scene-graph representation;
- template metadata index;
- deterministic text/image binding;
- export adapters;
- optional Canva/Express/provider adapters without authority inheritance.

### 3.7 Acrobat/PDF workflows

Harvested behavior:

- PDF creation;
- OCR;
- structured extraction to text/Markdown/tables/figures;
- Office export;
- compression;
- combine/split/reorder/rotate/delete;
- redact/highlight;
- visible edit/annotation;
- properties;
- accessibility tagging/structure.

In-house route candidates:

- `qpdf` for structure-preserving PDF transforms, merge/split/encryption/inspection;
- OCRmyPDF for searchable OCR text layers;
- `pikepdf`/PDF parser adapters where licensed and appropriate;
- renderer/text/table extraction adapters selected by capability-specific tests.

This family is the highest-confidence near-term sovereign target because its operations are deterministic and easy to verify with independent parsers.

### 3.8 Creative Cloud Libraries / asset estate

Harvested behavior:

- asset storage/search;
- libraries and reusable elements;
- metadata/thumbnails/renditions;
- versions and lineage;
- private/shared/public scopes;
- searchable provenance/rights metadata.

Adobe Ω target:

- content-addressed asset IDs;
- immutable origin hashes;
- version DAG;
- SQLite/PostgreSQL/object-store adapters;
- preview/rendition workers;
- rights/provenance manifest;
- capability-safe scope policies.

No stored reference grants access. Access scope must be evaluated at execution time.

### 3.9 Premiere/video and audio workflows

Harvested behavior:

- resize/transcode;
- smart reframe;
- scene detection;
- timeline operations;
- captions;
- audio enhancement/transcription;
- render/export.

In-house route candidates:

- FFmpeg/ffprobe for media processing and readback;
- OpenTimelineIO for provider-neutral editorial timeline interchange;
- PySceneDetect for scene/shot boundary detection;
- optional speech/audio model adapters with explicit model/license/provenance records.

### 3.10 Content provenance, rights and automation

Adobe Ω adds capabilities that should be stronger than a vendor-specific connector:

- content hashes;
- rights/license gate;
- provenance manifest;
- mission compiler;
- safe batch execution;
- failover;
- health/circuit state;
- semantic readback.

These are Federation-native control capabilities and should remain provider-neutral.

## 4. Backend architecture

`adobe_omega_v1.py` defines backends as capability adapters, not trust domains.

### Sovereign/local

- `LOCAL_RASTER`
- `LOCAL_SEGMENTATION`
- `LOCAL_GENERATIVE`
- `LOCAL_PDF`
- `LOCAL_VIDEO`
- `LOCAL_ASSET_CORE`

### Federation

- `FEDERATION_IMAGE_PROVIDER`

### Optional Adobe provider lanes

- `ADOBE_ACROBAT_NATIVE`
- `ADOBE_EXPRESS_NATIVE`
- `ADOBE_UNIFIED_NATIVE`

Provider state is never hard-coded as healthy. Fresh snapshots are injected by the execution surface.

## 5. Routing doctrine

For a requested capability:

1. resolve the typed capability contract;
2. require a fresh backend snapshot;
3. enforce the operation mode (`READ`, `TRANSFORM`, `GENERATE`, `MANAGE`);
4. reject held/unavailable/not-installed backends;
5. reject license-gated backends without explicit license admission;
6. if semantic proof is required, reject discovery-only/execution-only states;
7. prefer sovereign/local eligible routes;
8. fall back to Federation or provider routes only when permitted;
9. if no route remains, return `BUILD-AO-011:<capability_id>` rather than a false completion claim.

A provider outage therefore cannot block a capability that has a separately verified local implementation.

## 6. Proof ladder

Adobe Ω uses the following proof ladder:

`NONE → DISCOVERED → EXECUTED → SEMANTIC_READBACK → PERSISTENCE_ROLLBACK`

Examples:

- finding `qpdf` on `PATH` = `DISCOVERED`, **not** PDF capability verified;
- successfully running a transform = `EXECUTED`;
- independently reading back pages/content/output properties = `SEMANTIC_READBACK`;
- proving durable state and rollback where applicable = `PERSISTENCE_ROLLBACK`.

`FULL_PARITY` is denied unless every in-scope capability can be routed to a backend with semantic readback proof. It is intentionally impossible to obtain full parity merely by installing packages.

## 7. Local runtime qualification plan

### Wave A — deterministic foundation

1. PDF properties/combine/split/rotate/OCR.
2. Raster resize/crop/convert/tone.
3. Subject isolation/remove background.
4. Video transcode/probe/scene detection.
5. Content-addressed asset store + version metadata.

Each backend gets:

- dependency and version inventory;
- license record;
- golden input/output fixtures;
- positive and negative tests;
- idempotency/replay where relevant;
- semantic readback through a materially independent parser/inspection route;
- failure fingerprint and circuit-break behavior;
- resource/latency/cost telemetry.

### Wave B — structured creative documents

1. normalized scene/layer graph;
2. import/export adapters;
3. masks/groups/adjustment recipes;
4. template/brand document representation;
5. preview/rendition pipeline.

### Wave C — generative

1. model registry;
2. license/safety/cost admission;
3. text-to-image canary;
4. fill/expand/edit;
5. subject/object composite;
6. deterministic receipt with model/checkpoint/seed/config where exposed;
7. quality/semantic adjudication and rights metadata.

### Wave D — production hardening

- worker queues;
- sandboxed processors;
- asset/object storage;
- observability;
- retry/idempotency;
- cache/content deduplication;
- resource quotas;
- provenance;
- rollback;
- provider fallback;
- repeated cohort benchmark versus optional Adobe/Canva/provider lanes.

## 8. Security and legal boundary

This project is not intended to bypass Adobe licensing or access controls.

Prohibited:

- scraping or reconstructing proprietary source code;
- reverse engineering private authentication protocols to defeat access controls;
- copying private model weights or assets without rights;
- stripping DRM/access controls;
- treating a package license as a model/content license;
- storing secrets in source or receipts;
- silently uploading private material to external providers;
- claiming Adobe certification/endorsement;
- describing an untested format adapter as Photoshop/Acrobat-compatible.

Required:

- software bill of materials for runtime images;
- model/checkpoint license registry;
- content/asset rights metadata;
- minimum-necessary provider disclosure;
- sandboxing for untrusted media/parsers;
- size/decompression-bomb limits;
- path traversal/archive safety;
- MIME/type verification;
- no shell interpolation from user filenames/parameters;
- provider credentials through non-secret handles only.

## 9. Public benchmark references

The clean-room harvest is based on publicly documented product/API behavior, including:

- Adobe for ChatGPT / unified Adobe connector: https://helpx.adobe.com/firefly/web/app-integrations/adobe-connectors/adobe-for-chatgpt.html
- Adobe Photoshop API: https://developer.adobe.com/firefly-services/docs/photoshop/
- Adobe Firefly Services APIs: https://developer.adobe.com/firefly-services/docs/firefly-api/
- Adobe Express Embed SDK: https://developer.adobe.com/express/embed-sdk/
- Creative Cloud Libraries API: https://developer.adobe.com/creative-cloud-libraries/
- Adobe PDF Services: https://developer.adobe.com/document-services/
- libvips: https://www.libvips.org/
- ImageMagick: https://imagemagick.org/
- rembg: https://github.com/danielgatis/rembg
- Hugging Face Diffusers: https://github.com/huggingface/diffusers
- SAM 2: https://github.com/facebookresearch/sam2
- qpdf: https://github.com/qpdf/qpdf
- OCRmyPDF: https://github.com/ocrmypdf/OCRmyPDF
- FFmpeg: https://ffmpeg.org/
- OpenTimelineIO: https://github.com/AcademySoftwareFoundation/OpenTimelineIO
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect

These references establish feature ideas/interfaces and candidate implementation families. They do not transfer intellectual property, licenses, authority, credentials or runtime maturity.

## 10. Acceptance gates

### SOURCE_VERIFIED

Requires:

- registry validates;
- no duplicate/unknown capability references;
- deterministic tests pass;
- local-first/fallback/circuit/license/proof rules pass;
- Airlock, leak guard and repository provenance checks pass on the exact PR head;
- signed `main` readback after merge.

### LOCAL_BACKEND_VERIFIED

For each backend:

- exact dependency/version inventory;
- license gate passes;
- representative operation executes;
- independent semantic readback passes;
- failure/negative fixture passes;
- rollback/persistence proved where applicable.

### FULL_PARITY_CANDIDATE

Requires all in-scope capability IDs to have semantic-readback-qualified routes. Missing or held capabilities stay visible in the parity report. No score averaging may hide a hard capability gap.

### DEPLOYED

Requires an actual target runtime identity, health, persistence, observability and rollback proof. Source admission does not satisfy deployment.

## 11. Innovation delta over a vendor connector

Federation Adobe Ω is designed to provide several capabilities that a single provider connector cannot guarantee:

- provider independence and local-first execution;
- explicit license/model rights gates;
- per-capability proof rather than connector-level trust;
- circuit breaking and failover;
- content-addressed lineage;
- reproducible proof receipts;
- provider/local benchmark tournaments;
- no silent capability degradation;
- AO-CRA gaps for every missing operation;
- clean separation of source, dependency, runtime, semantic readback and deployment maturity.

The goal is not brand imitation. The goal is a sovereign, inspectable creative operating fabric that can use Adobe when Adobe is healthy and continue working through verified alternatives when it is not.
