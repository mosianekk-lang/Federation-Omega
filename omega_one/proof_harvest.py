"""Omega-One additive proof-harvest overlay for the 100-capability portfolio.

Purpose
-------
Reuse proven Federation lineage before building duplicate capability. This module maps
only exact capability/evidence matches into the maturity compiler. It never replaces the
Master Blueprint, never deletes capability, and never infers provider/deployment maturity
from source/CI evidence.

Zero-dilution rule: proof can be added to a preserved capability; a missing or held proof
can never delete or narrow that capability's full target semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from .maturity import CapabilityRecord, MaturityStage, ProofClaim


@dataclass(frozen=True)
class HarvestedProof:
    capability_id: str
    exact_mapping_reason: str
    maturity_ceiling: MaturityStage
    evidence_refs: tuple[str, ...]
    truth_boundary: str
    source_lineage: str
    provider_live_proven: bool = False
    deployment_proven: bool = False
    zero_dilution: bool = True

    def validate(self) -> "HarvestedProof":
        if not self.capability_id.startswith("CAP-"):
            raise ValueError("capability_id must be a CAP-* identity")
        if not self.exact_mapping_reason.strip() or not self.evidence_refs:
            raise ValueError("exact mapping reason and evidence refs are required")
        if self.maturity_ceiling > MaturityStage.CI_ADMITTED and not (
            self.deployment_proven or self.provider_live_proven
        ):
            raise ValueError("post-CI maturity requires explicit stronger proof")
        if self.provider_live_proven and self.maturity_ceiling < MaturityStage.PROVIDER_EXECUTED:
            raise ValueError("provider_live_proven conflicts with maturity ceiling")
        return self


# First bounded proof-harvest wave. Every entry below has an exact capability mapping and
# independently observed hosted proof. No provider-live or deployment state is inherited.
DEFAULT_PROOF_HARVEST: tuple[HarvestedProof, ...] = (
    HarvestedProof(
        capability_id="CAP-024",
        exact_mapping_reason=(
            "SchemaFirstAdapterCompiler automatically generates UniversalCapabilityContract "
            "objects from supported OpenAPI operations, and the v0.8.5 end-to-end court "
            "verifies schema -> UCC -> standards projection without semantic loss."
        ),
        maturity_ceiling=MaturityStage.CI_ADMITTED,
        evidence_refs=(
            "github:pr843:head:475a53742c71824cab580a496dfe0f5251325c9f",
            "github:airlock:run:33313664478:PASS",
            "github:proofos:manifest:ea89a083e4a55540fa1c2a3b93a8c73fc280da0a8d68ad1c20a7d83e01fc61d0",
            "github:proofos:report:74ca1626cb072dc12e0c799c04594ca9b11ead79e8762612a72e0e79d1bb5e42",
            "github:leak_guard:run:33313664482:PASS",
            "github:bubbles:run:33313664502:PASS",
        ),
        truth_boundary=(
            "Proves deterministic UCC generation and hosted admission for supported schema "
            "shapes. Does not prove arbitrary-provider compatibility or provider execution."
        ),
        source_lineage="omega_one/schema_adapter.py + omega_one/interop.py",
    ),
    HarvestedProof(
        capability_id="CAP-031",
        exact_mapping_reason=(
            "SchemaFirstAdapterCompiler is the OpenAPI 3.x -> Omega-One contract compiler, "
            "including local refs, request/response schemas, filters and deterministic IDs."
        ),
        maturity_ceiling=MaturityStage.CI_ADMITTED,
        evidence_refs=(
            "local:v0.8.3:schema-compiler:446-of-446-restored-pass",
            "github:pr843:head:475a53742c71824cab580a496dfe0f5251325c9f",
            "github:airlock:run:33313664478:PASS",
            "github:proofos:report:74ca1626cb072dc12e0c799c04594ca9b11ead79e8762612a72e0e79d1bb5e42",
        ),
        truth_boundary=(
            "OpenAPI compiler source/test/hosted-CI is proven. Live schema-derived provider "
            "conformance and complex-auth execution remain separate gates."
        ),
        source_lineage="OMEGA_ONE_v0.8.3 -> omega_one/schema_adapter.py",
    ),
    HarvestedProof(
        capability_id="CAP-033",
        exact_mapping_reason=(
            "The schema compiler strips credential examples/defaults, converts explicit API-key "
            "parameters to symbolic boundary references, and preserves sensitive business fields "
            "as secret-reference-required schema rather than deleting them."
        ),
        maturity_ceiling=MaturityStage.CI_ADMITTED,
        evidence_refs=(
            "local:v0.8.3:secret-sanitizer:restored-pass",
            "github:pr843:head:475a53742c71824cab580a496dfe0f5251325c9f",
            "github:airlock:run:33313664478:PASS",
            "github:leak_guard:run:33313664482:PASS",
        ),
        truth_boundary=(
            "Proves source/test/hosted-CI secret-field sanitization. It does not prove every "
            "provider-specific credential flow or complex authentication mechanism."
        ),
        source_lineage="OMEGA_ONE_v0.8.3 -> omega_one/schema_adapter.py",
    ),
    HarvestedProof(
        capability_id="CAP-053",
        exact_mapping_reason=(
            "Merged OpenRouter Processor Mesh v1 implements PINNED/AUTO/FUSION/NITRO/FLOOR/"
            "FALLBACK processor strategies, provider envelopes, capability matching and proof "
            "isolation while retaining SOVARA effect authority."
        ),
        maturity_ceiling=MaturityStage.CI_ADMITTED,
        evidence_refs=(
            "github:pr818:merged:true",
            "github:pr818:head:65ef2e3a52684c07259f03eef3279c416d51015f",
            "github:pr818:merge:6fbfa373e284f274ba2d05e8439743357bcdffc8",
            "github:airlock:run:33295536989:PASS",
            "github:leak_guard:run:33295536998:PASS",
            "github:bubbles:run:33295536987:PASS",
        ),
        truth_boundary=(
            "Source and hosted CI prove processor-mesh planning/proof isolation only. The known "
            "OpenRouter executor secret-binding gap means provider execution is not inherited."
        ),
        source_lineage="sovara/creative/openrouter_processor_mesh.py",
    ),
    HarvestedProof(
        capability_id="CAP-099",
        exact_mapping_reason=(
            "Merged ChatBridge Omega4.9 implements full-fidelity multi-path/multi-stream capture, "
            "hash-chained replay, exact/bounded restore modes, conflict quarantine and zero-loss "
            "handoff semantics for observable conversation state."
        ),
        maturity_ceiling=MaturityStage.CI_ADMITTED,
        evidence_refs=(
            "github:pr535:merged:true",
            "github:pr535:head:240325a33d8454ea614ff00e9c71855fb4577899",
            "github:pr535:merge:e7a8cebce21ddc1042439f45466803b42858582a",
            "github:airlock:run:31984768260:PASS",
            "github:leak_guard:run:31984768265:PASS",
            "github:bubbles:run:31984768331:PASS",
        ),
        truth_boundary=(
            "Source/CI prove full-fidelity handoff mechanics for events delivered by authorised "
            "adapters. Universal native-chat capture and provider binding remain separate gates."
        ),
        source_lineage="bubbles/chatbridge_omega4 Omega4.9",
    ),
)


def _claims_through(entry: HarvestedProof) -> tuple[ProofClaim, ...]:
    entry.validate()
    return tuple(
        ProofClaim(
            stage=stage,
            proven=True,
            evidence_refs=entry.evidence_refs,
            note=f"HARVESTED_EXACT_MAPPING:{entry.source_lineage}",
        )
        for stage in MaturityStage
        if stage <= entry.maturity_ceiling
    )


def harvest_index(
    harvested: Iterable[HarvestedProof] = DEFAULT_PROOF_HARVEST,
) -> Mapping[str, HarvestedProof]:
    index: dict[str, HarvestedProof] = {}
    for entry in harvested:
        entry.validate()
        if entry.capability_id in index:
            raise ValueError(f"duplicate harvested proof: {entry.capability_id}")
        index[entry.capability_id] = entry
    return index


def apply_proof_harvest(
    records: Iterable[CapabilityRecord],
    harvested: Iterable[HarvestedProof] = DEFAULT_PROOF_HARVEST,
) -> tuple[CapabilityRecord, ...]:
    """Add exact harvested proof without deleting or downgrading baseline claims."""
    index = harvest_index(harvested)
    output: list[CapabilityRecord] = []
    seen: set[str] = set()
    for record in records:
        seen.add(record.capability_id)
        entry = index.get(record.capability_id)
        if entry is None:
            output.append(record)
            continue
        existing_by_stage = {claim.stage: claim for claim in record.claims}
        for claim in _claims_through(entry):
            prior = existing_by_stage.get(claim.stage)
            if prior is None:
                existing_by_stage[claim.stage] = claim
                continue
            # Never discard existing proof. Merge refs and preserve the original note.
            existing_by_stage[claim.stage] = ProofClaim(
                stage=claim.stage,
                proven=prior.proven or claim.proven,
                evidence_refs=tuple(sorted(set(prior.evidence_refs) | set(claim.evidence_refs))),
                note=" | ".join(x for x in (prior.note, claim.note) if x),
            )
        metadata = dict(record.metadata)
        metadata.update(
            {
                "preservation_state": metadata.get("preservation_state", "PRESERVED_FULL_CAPABILITY"),
                "zero_dilution": "true",
                "proof_harvest_source": entry.source_lineage,
                "proof_harvest_truth_boundary": entry.truth_boundary,
                "proof_harvest_exact_mapping": "true",
            }
        )
        output.append(
            replace(
                record,
                claims=tuple(existing_by_stage[stage] for stage in sorted(existing_by_stage)),
                metadata=metadata,
            )
        )
    missing = sorted(set(index) - seen)
    if missing:
        raise ValueError(f"harvest references missing capability identities: {missing}")
    return tuple(output)
